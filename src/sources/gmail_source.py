# -*- coding: utf-8 -*-
"""
数据源 - Gmail + Google Alerts（原有抓取方式，包装为 Source 实现）

行为与改造前完全一致，只是把入口从 news_fetcher 内部移到 Source 层，
使其与其他数据源（rss / search）可以用同一套接口并联。
"""

import logging
import os
from typing import Dict, List, Optional

from src.sources.base import Source

logger = logging.getLogger(__name__)


class GmailSource(Source):
    """通过 IMAP 读取 Gmail 中的 Google Alerts 邮件并解析。"""

    name = "gmail"

    def fetch(self, categories: List[Dict], lookback_days: int = 7,
              alert_subjects: Optional[List[str]] = None) -> List[Dict]:
        addr = os.environ.get("GMAIL_ADDRESS", "")
        pwd = os.environ.get("GMAIL_APP_PASSWORD", "")
        if not addr or not pwd:
            raise ValueError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD 未设置")

        from src.gmail_fetcher import fetch_alerts_from_gmail

        logger.info("GmailSource: 连接 %s，回溯 %d 天", addr, lookback_days)
        articles = fetch_alerts_from_gmail(
            gmail_address=addr,
            gmail_password=pwd,
            lookback_days=lookback_days,
            alert_subjects=alert_subjects,
        )
        logger.info("GmailSource: 解析出 %d 条", len(articles or []))
        return articles or []
