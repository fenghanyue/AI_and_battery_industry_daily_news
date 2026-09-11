# -*- coding: utf-8 -*-
"""
新闻抓取调度层

把「从哪里拿新闻」抽象为可插拔的 Source（见 src/sources/），本模块只做四件事：

  1. 解析本轮启用哪些数据源
  2. 逐个抓取——单个源失败只记日志，不影响其他源
  3. 合并 + 跨源去重
  4. 按关键词分配到各分类

向后兼容：fetch_all() 签名保持不变；未配置 SOURCES 时默认只启用 gmail，
行为与改造前完全一致。

启用方式（三选一，优先级从高到低）：
    python main.py --profile battery --period daily --sources gmail,rss
    SOURCES=rss                     # .env / GitHub Secrets
    config/battery.py: SOURCES = ["gmail", "rss"]
"""

import logging
from typing import Dict, List, Optional

from src.gmail_fetcher import assign_to_categories
from src.sources import build_sources, resolve_source_names
from src.sources.base import dedup_articles

logger = logging.getLogger(__name__)


def fetch_all(categories: List[Dict], lookback_days: int = 7,
              alert_subjects: Optional[List[str]] = None,
              sources=None, profile=None) -> Dict[str, List[Dict]]:
    """
    抓取所有分类的新闻，返回 {cat_id: [articles]}。

    categories:     配置文件中的 CATEGORIES 列表
    lookback_days:  向前回溯天数
    alert_subjects: GmailSource 用，按邮件标题过滤行业
    sources:        启用的数据源，如 "gmail,rss" 或 ["gmail", "rss"]；
                    留空则按 环境变量 SOURCES → profile.SOURCES → 默认 gmail 解析
    profile:        行业配置模块，用于读取 RSS_FEEDS / SEARCH_QUERIES
    """
    empty = {cat["id"]: [] for cat in categories}

    names = resolve_source_names(sources, profile)
    if not names:
        logger.warning("未启用任何数据源，返回空结果")
        return empty

    logger.info("启用数据源: %s", ", ".join(names))

    articles: List[Dict] = []
    errors: List[tuple] = []

    for src in build_sources(names, profile):
        try:
            got = src.fetch(categories, lookback_days=lookback_days,
                            alert_subjects=alert_subjects)
            logger.info("  [%-6s] 抓到 %d 条", src.name, len(got or []))
            articles.extend(got or [])
        except Exception as exc:                      # 失败隔离：不中断全链
            logger.error("  [%-6s] 抓取失败（已跳过）：%s", src.name, exc)
            errors.append((src.name, exc))

    if not articles:
        # 一条都没拿到：保持原有「失败要吵」的行为，方便定位配置问题
        if errors:
            raise errors[0][1]
        logger.warning("所有数据源都没有内容")
        return empty

    merged = dedup_articles(articles)
    result = assign_to_categories(merged, categories)
    logger.info("合并去重后共 %d 条候选新闻", sum(len(v) for v in result.values()))
    return result
