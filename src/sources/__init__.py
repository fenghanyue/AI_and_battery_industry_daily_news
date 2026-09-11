# -*- coding: utf-8 -*-
"""
数据源注册表

新增一种来源 = 新增一个 Source 子类 + 在 REGISTRY 里登记一行，
不需要改动 news_fetcher 主流程。

启用的源由 resolve_source_names() 解析，优先级：
    1. 显式传入的 sources 参数（main.py --sources）
    2. 环境变量 SOURCES（如 SOURCES=gmail,rss）
    3. 行业配置里的 SOURCES（config/<profile>.py）
    4. DEFAULT_SOURCES（保持向后兼容：只启用 gmail）
"""

import logging
import os
from typing import Dict, Iterable, List, Optional, Type

from src.sources.base import Source, clean_text, dedup_articles, http_get, title_key
from src.sources.gmail_source import GmailSource
from src.sources.rss_source import RSSSource
from src.sources.search_source import SearchSource

logger = logging.getLogger(__name__)

#: name -> Source 类
REGISTRY: Dict[str, Type[Source]] = {
    "gmail": GmailSource,
    "rss": RSSSource,
    "search": SearchSource,
}

#: 未做任何配置时的默认值——与改造前行为一致（只走 Gmail Google Alerts）
DEFAULT_SOURCES = ("gmail",)

__all__ = [
    "Source", "GmailSource", "RSSSource", "SearchSource",
    "REGISTRY", "DEFAULT_SOURCES",
    "parse_names", "resolve_source_names", "build_sources", "available_sources",
    "clean_text", "dedup_articles", "http_get", "title_key",
]


def available_sources() -> List[str]:
    """列出所有已注册的数据源名。"""
    return sorted(REGISTRY)


def parse_names(spec) -> List[str]:
    """把 "gmail,rss" / ["gmail","rss"] / None 统一成名字列表。"""
    if not spec:
        return []
    if isinstance(spec, str):
        raw: Iterable[str] = spec.replace("，", ",").split(",")
    else:
        raw = spec
    names, seen = [], set()
    for item in raw:
        name = str(item).strip().lower()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def resolve_source_names(sources=None, profile=None) -> List[str]:
    """按优先级解析出要启用的数据源名列表。"""
    for candidate, origin in (
        (sources, "参数 --sources"),
        (os.environ.get("SOURCES", ""), "环境变量 SOURCES"),
        (getattr(profile, "SOURCES", None), "行业配置 SOURCES"),
        (DEFAULT_SOURCES, "默认值"),
    ):
        names = parse_names(candidate)
        if not names:
            continue
        unknown = [n for n in names if n not in REGISTRY]
        if unknown:
            logger.warning("忽略未注册的数据源 %s（可选：%s）",
                           unknown, ", ".join(available_sources()))
            names = [n for n in names if n in REGISTRY]
        if names:
            logger.debug("数据源来自 %s: %s", origin, names)
            return names
    return []


def build_sources(names: List[str], profile=None) -> List[Source]:
    """按名字实例化数据源，并把行业配置透传进去（RSS_FEEDS / SEARCH_QUERIES）。"""
    built: List[Source] = []
    for name in names:
        cls = REGISTRY.get(name)
        if cls is None:
            continue
        if name == "rss":
            built.append(cls(feeds=getattr(profile, "RSS_FEEDS", None) if profile else None))
        elif name == "search":
            built.append(cls(queries=getattr(profile, "SEARCH_QUERIES", None) if profile else None))
        else:
            built.append(cls())
    return built
