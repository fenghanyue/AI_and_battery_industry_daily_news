# -*- coding: utf-8 -*-
"""
数据源 - 搜索 API 兜底

有些垂媒既没有可用 RSS，又受 WAF 保护（直接请求拿不到内容）。
这类源用搜索 API 按检索式补，作为 rss / gmail 之后的第三类来源。

检索式来源（优先级从高到低）：
  1. 构造参数 queries
  2. 环境变量 SEARCH_QUERIES（逗号分隔）
  3. 行业配置里的 SEARCH_QUERIES
  4. 兜底：取 CATEGORIES 里前 N 个分类的第一个 query

Provider（环境变量 SEARCH_PROVIDER 选择）：
  generic  默认。GET SEARCH_API_URL（支持 {query} / {count} 占位符），
           用 SEARCH_API_KEY 走 Bearer 头。
  tavily   内置适配器，POST https://api.tavily.com/search。

结果 JSON 路径默认按 "results" 数组解析，取 title / url / content 三个字段。
"""

import json
import logging
import os
import urllib.parse
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

from src.sources.base import DEFAULT_UA, Source, clean_text

logger = logging.getLogger(__name__)

TAVILY_ENDPOINT = "https://api.tavily.com/search"


def _env_queries() -> List[str]:
    raw = os.environ.get("SEARCH_QUERIES", "").strip()
    return [q.strip() for q in raw.split(",") if q.strip()] if raw else []


def _fallback_queries(categories: List[Dict], limit: int = 3) -> List[str]:
    """没配检索式时，用分类配置里的关键词兜底，保证零配置也能跑。"""
    queries: List[str] = []
    for cat in categories or []:
        for q in cat.get("queries", []):
            if q and q not in queries:
                queries.append(q)
            if len(queries) >= limit:
                return queries
        if len(queries) >= limit:
            break
    return queries


def _post_json(url: str, payload: Dict, timeout: int = 25,
               headers: Optional[Dict[str, str]] = None) -> Dict:
    hdrs = {"Content-Type": "application/json", "User-Agent": DEFAULT_UA}
    hdrs.update(headers or {})
    req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=hdrs)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, timeout: int = 25,
              headers: Optional[Dict[str, str]] = None) -> Dict:
    hdrs = {"User-Agent": DEFAULT_UA, "Accept": "application/json"}
    hdrs.update(headers or {})
    req = Request(url, headers=hdrs)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class SearchSource(Source):
    """用搜索 API 按检索式补新闻。默认不启用（SOURCES 里要显式写 "search"）。"""

    name = "search"

    def __init__(self, queries: Optional[List[str]] = None,
                 provider: Optional[str] = None, timeout: int = 25,
                 results_per_query: int = 8):
        self._queries = queries
        self._provider = provider
        self.timeout = timeout
        self.results_per_query = results_per_query

    @property
    def queries(self) -> List[str]:
        return self._queries or _env_queries()

    @property
    def provider(self) -> str:
        return (self._provider or os.environ.get("SEARCH_PROVIDER") or "generic").lower()

    # ── provider 实现 ──────────────────────────────────────────
    def _search_tavily(self, query: str, lookback_days: int) -> List[Dict]:
        api_key = os.environ.get("SEARCH_API_KEY", "") or os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            raise ValueError("SEARCH_PROVIDER=tavily 需要 SEARCH_API_KEY / TAVILY_API_KEY")
        data = _post_json(TAVILY_ENDPOINT, {
            "api_key": api_key,
            "query": query,
            "max_results": self.results_per_query,
            "days": max(lookback_days, 1),
            "search_depth": "basic",
        }, timeout=self.timeout)
        return self._normalize(data.get("results", []))

    def _search_generic(self, query: str, lookback_days: int) -> List[Dict]:
        endpoint = os.environ.get("SEARCH_API_URL", "").strip()
        if not endpoint:
            raise ValueError("SEARCH_PROVIDER=generic 需要 SEARCH_API_URL")
        url = (endpoint
               .replace("{query}", urllib.parse.quote(query))
               .replace("{count}", str(self.results_per_query))
               .replace("{days}", str(max(lookback_days, 1))))
        headers = {}
        api_key = os.environ.get("SEARCH_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        data = _get_json(url, timeout=self.timeout, headers=headers)

        path = os.environ.get("SEARCH_API_RESULTS_PATH", "results")
        results = data
        for seg in path.split("."):
            if isinstance(results, dict) and seg in results:
                results = results[seg]
            else:
                results = []
                break
        field_map = {
            "title": os.environ.get("SEARCH_API_TITLE_FIELD", "title"),
            "link": os.environ.get("SEARCH_API_URL_FIELD", "url"),
            "summary": os.environ.get("SEARCH_API_SNIPPET_FIELD", "content"),
        }
        return self._normalize(results, field_map)

    @staticmethod
    def _normalize(results, field_map=None) -> List[Dict]:
        fm = field_map or {"title": "title", "link": "url", "summary": "content"}
        out = []
        for item in results or []:
            if not isinstance(item, dict):
                continue
            title = clean_text(item.get(fm["title"], ""))
            link = (item.get(fm["link"], "") or "").strip()
            if not (title and link):
                continue
            out.append({
                "title": title,
                "summary": clean_text(item.get(fm["summary"], ""))[:400],
                "link": link,
            })
        return out

    # ── 出口 ──────────────────────────────────────────────────
    def fetch(self, categories: List[Dict], lookback_days: int = 7,
              alert_subjects: Optional[List[str]] = None) -> List[Dict]:
        queries = self.queries or _fallback_queries(categories)
        if not queries:
            raise ValueError("SearchSource 没有可用的检索式")

        today = self.today()
        provider = self.provider
        logger.info("SearchSource: provider=%s，检索式 %d 条", provider, len(queries))

        articles: List[Dict] = []
        errors: List[Exception] = []
        for query in queries:
            try:
                if provider == "tavily":
                    hits = self._search_tavily(query, lookback_days)
                else:
                    hits = self._search_generic(query, lookback_days)
            except Exception as exc:
                logger.warning("  检索式「%s」失败：%s", query, exc)
                errors.append(exc)
                continue

            for hit in hits:
                articles.append({
                    "title": hit["title"],
                    "summary": hit["summary"],
                    "link": hit["link"],
                    "source": f"搜索:{query}",
                    "published": today,
                    "raw_date": today,
                })
            logger.info("  检索式「%s」命中 %d 条", query, len(hits))

        # 每条检索式都失败 → 抛错（通常是 API Key / Endpoint 没配），不要静默返回空
        if not articles and errors and len(errors) == len(queries):
            raise errors[0]
        logger.info("SearchSource: 合计 %d 条候选", len(articles))
        return articles
