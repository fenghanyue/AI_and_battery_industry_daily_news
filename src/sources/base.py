# -*- coding: utf-8 -*-
"""
数据源层 - 公共基类与工具函数

设计目标：把「从哪里拿新闻」和「拿到之后怎么处理」解耦。

每个 Source 只做一件事：返回候选文章列表。统一结构（与原 gmail_fetcher 保持一致）：

    {
        "title":     str,   # 标题（必填）
        "summary":   str,   # 摘要片段，可为空字符串
        "link":      str,   # 原文链接（必填，用于去重）
        "source":    str,   # 来源名，如 "electrive" / "36氪快讯"
        "published": str,   # 发布日期 YYYY/MM/DD
        "raw_date":  str,   # 采集日期 YYYY/MM/DD
    }

分类、AI 筛选、排版都不属于数据源的职责。
"""

import abc
import html as _html
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (compatible; IndustryDailyBot/1.0; "
    "+https://github.com/fenghanyue/AI_and_battery_industry_daily_news)"
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TITLE_KEY_RE = re.compile(r"[\s\W_]+")


class Source(abc.ABC):
    """数据源抽象基类。子类只需实现 fetch()。"""

    #: 在 SOURCES 配置中使用的名字
    name: str = "base"

    @abc.abstractmethod
    def fetch(self, categories: List[Dict], lookback_days: int = 7,
              alert_subjects: Optional[List[str]] = None) -> List[Dict]:
        """
        返回本源的候选文章（未分类）。

        约定：抓取失败时直接抛异常，由调度层（news_fetcher）捕获隔离，
        不要返回空列表来掩盖错误。
        """
        raise NotImplementedError

    @staticmethod
    def today() -> str:
        return datetime.now().strftime("%Y/%m/%d")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} name={self.name!r}>"


def clean_text(raw) -> str:
    """去 HTML 标签、反转义实体、压缩空白。"""
    if not raw:
        return ""
    text = _html.unescape(str(raw))
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def http_get(url: str, timeout: int = 15,
             headers: Optional[Dict[str, str]] = None) -> bytes:
    """极简 HTTP GET，仅用标准库，避免为抓取引入额外依赖。"""
    req = Request(url, headers=headers or {"User-Agent": DEFAULT_UA})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def title_key(title: str) -> str:
    """标题归一化，用于跨源去重（忽略空格/标点/大小写）。"""
    return _TITLE_KEY_RE.sub("", (title or "").lower())[:60]


def extract_keywords(categories: List[Dict],
                     alert_subjects: Optional[List[str]] = None,
                     min_len: int = 2) -> List[str]:
    """
    从行业配置抽取关键词集合，用于判定一条新闻是否属于本行业。

    取 CATEGORIES 的 queries（按空格拆词、去掉 OR）+ ALERT_SUBJECTS。
    Google Alerts 是靠搜索词在邮件到达前就做了过滤；RSS / 搜索源没有这一
    层，需要在本地补上，否则通用媒体的科技/财经新闻会大量涌进分类。
    """
    keywords = set()
    for cat in categories or []:
        for query in cat.get("queries", []):
            for word in str(query).split():
                w = word.strip()
                if w and w.upper() != "OR" and len(w) >= min_len:
                    keywords.add(w)
    for kw in alert_subjects or []:
        w = str(kw).strip()
        if w:
            keywords.add(w)
    return sorted(keywords)


def is_relevant(text: str, keywords: List[str]) -> bool:
    """标题+摘要命中任一关键词即视为相关；未配置关键词时不筛。"""
    if not keywords:
        return True
    low = (text or "").lower()
    return any(kw.lower() in low for kw in keywords)


def dedup_articles(articles: List[Dict]) -> List[Dict]:
    """
    跨源去重：先按链接精确匹配，再按标题归一化模糊匹配。保持原始顺序。

    多源聚合时同一件事常被多家转载，标题措辞不同但归一化后一致，故两层都用。
    """
    seen_links, seen_titles, kept = set(), set(), []
    for art in articles:
        link = (art.get("link") or "").strip()
        tkey = title_key(art.get("title", ""))
        if link and link in seen_links:
            continue
        if tkey and tkey in seen_titles:
            continue
        if link:
            seen_links.add(link)
        if tkey:
            seen_titles.add(tkey)
        kept.append(art)
    if len(kept) != len(articles):
        logger.info("跨源去重：%d → %d 条", len(articles), len(kept))
    return kept
