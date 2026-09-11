# -*- coding: utf-8 -*-
"""
数据源 - 多源 RSS/Atom 聚合

用 Python 标准库实现（urllib + xml.etree），不需要 API key，也不新增依赖。
RSS 源彼此独立，不受单一平台限流或封禁影响，适合作为 Google Alerts 的补充或替代。

订阅列表来自行业配置的 RSS_FEEDS：

    RSS_FEEDS = [
        {"name": "36氪快讯", "url": "https://www.36kr.com/feed-newsflash", "region": "cn"},
        {"name": "electrive", "url": "https://www.electrive.com/feed/", "region": "global"},
    ]

也支持用环境变量 RSS_FEEDS（JSON 数组）覆盖，便于在 CI 里不改代码就换源。
"""

import json
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

from src.sources.base import (Source, clean_text, extract_keywords, http_get,
                              is_relevant)

logger = logging.getLogger(__name__)

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _node_text(node: ET.Element, tag: str, is_atom: bool) -> str:
    name = f"{ATOM_NS}{tag}" if is_atom else tag
    el = node.find(name)
    return (el.text or "").strip() if el is not None and el.text else ""


def _node_link(node: ET.Element, is_atom: bool) -> str:
    """取出条目链接。RSS 在 <link> 文本里，Atom 在 <link href> 属性里。"""
    if is_atom:
        for el in node.findall(f"{ATOM_NS}link"):
            href = el.get("href", "")
            if href:
                return href
        return ""
    el = node.find("link")
    return (el.text or "").strip() if el is not None and el.text else ""


def _parse_date(raw: str) -> Optional[datetime]:
    """兼容 RSS 的 RFC822 与 Atom 的 ISO8601 两种时间格式。"""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def parse_feed(xml_bytes: bytes) -> List[Dict]:
    """解析 RSS 2.0 或 Atom feed，返回中间结构（含未格式化的 _dt）。"""
    root = ET.fromstring(xml_bytes)

    nodes = root.findall(".//item")
    is_atom = False
    if not nodes:
        nodes = root.findall(f".//{ATOM_NS}entry")
        is_atom = True

    out: List[Dict] = []
    for node in nodes:
        title = clean_text(_node_text(node, "title", is_atom))
        if not title:
            continue
        raw_date = (_node_text(node, "pubDate", is_atom)
                    or _node_text(node, "published", is_atom)
                    or _node_text(node, "updated", is_atom))
        summary = clean_text(
            _node_text(node, "description", is_atom)
            or _node_text(node, "summary", is_atom)
            or _node_text(node, "content", is_atom)
        )
        out.append({
            "title": title,
            "summary": summary[:400],
            "link": _node_link(node, is_atom),
            "_dt": _parse_date(raw_date),
        })
    return out


def _env_feeds() -> Optional[List[Dict]]:
    """环境变量 RSS_FEEDS（JSON 数组）优先级最高，方便 CI 里换源。"""
    raw = os.environ.get("RSS_FEEDS", "").strip()
    if not raw:
        return None
    try:
        feeds = json.loads(raw)
        if isinstance(feeds, list) and feeds:
            return feeds
    except Exception as exc:
        logger.warning("RSS_FEEDS 环境变量解析失败，已忽略：%s", exc)
    return None


class RSSSource(Source):
    """聚合多个 RSS/Atom 订阅源。"""

    name = "rss"

    def __init__(self, feeds: Optional[List[Dict]] = None, timeout: int = 15):
        self._feeds = feeds
        self.timeout = timeout

    @property
    def feeds(self) -> List[Dict]:
        return _env_feeds() or self._feeds or []

    def fetch(self, categories: List[Dict], lookback_days: int = 7,
              alert_subjects: Optional[List[str]] = None) -> List[Dict]:
        feeds = self.feeds
        if not feeds:
            raise ValueError(
                "RSSSource 未配置订阅源：请在 config/<profile>.py 里设置 RSS_FEEDS，"
                "或设置环境变量 RSS_FEEDS（JSON 数组）"
            )

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        today = self.today()
        # 通用媒体的 RSS 不是行业频道，先按行业关键词预筛，替代 Google Alerts 上游的搜索词过滤
        keywords = extract_keywords(categories, alert_subjects)
        articles: List[Dict] = []
        failed: List[str] = []
        raw_total = 0
        attempted = 0

        for feed in feeds:
            name, url = feed.get("name") or feed.get("url", ""), feed.get("url", "")
            if not url:
                continue
            attempted += 1
            try:
                entries = parse_feed(http_get(url, timeout=self.timeout))
            except Exception as exc:
                # 单个源失败不影响其他源
                logger.warning("  订阅源「%s」抓取失败：%s", name, exc)
                failed.append(name)
                continue

            kept = 0
            for ent in entries:
                raw_total += 1
                dt = ent.get("_dt")
                # 没有日期的条目视为当期（部分源不提供时间），保留
                if dt is not None and dt < cutoff:
                    continue
                if not is_relevant(f"{ent['title']} {ent['summary']}", keywords):
                    continue
                articles.append({
                    "title": ent["title"],
                    "summary": ent["summary"],
                    "link": ent["link"],
                    "source": name,
                    "published": dt.strftime("%Y/%m/%d") if dt else today,
                    "raw_date": today,
                })
                kept += 1
            logger.info("  订阅源「%s」%d 条（窗口内 %d 条）", name, len(entries), kept)

        if failed:
            logger.warning("RSSSource: %d/%d 个源失败：%s",
                           len(failed), len(feeds), ", ".join(failed))
        # 所有源都挂了 → 大声报错，不要让上层误以为“今天没新闻”
        if not articles and failed and len(failed) == attempted:
            raise RuntimeError(f"RSSSource: {attempted} 个订阅源全部抓取失败：{', '.join(failed)}")
        logger.info("RSSSource: 行业相关预筛 %d → %d 条（关键词 %d 个）",
                    raw_total, len(articles), len(keywords))
        return articles
