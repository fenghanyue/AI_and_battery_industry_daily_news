# -*- coding: utf-8 -*-
"""
Gmail 抓取器 - 通过 IMAP 读取 Google Alerts 邮件，解析出新闻条目
"""

import os
import re
import imaplib
import email
import email.message        # 显式导入：否则未先导入 http.client 时 email.message 属性不存在
import logging
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs, unquote
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
ALERTS_SENDER = "googlealerts-noreply@google.com"


# ═══════════════════════════════════════════════════
#  Google Alerts HTML 解析器
# ═══════════════════════════════════════════════════

class _GoogleAlertsParser(HTMLParser):
    """
    解析 Google Alerts 邮件的 HTML，提取文章列表。
    Google Alerts 邮件结构：
      - 每条新闻是一个 <a> 链接，href 是 google.com/url?...&url=真实链接
      - 链接文字就是标题
      - 紧跟着的文本是摘要片段
      - 来源通常在摘要后面
    """

    def __init__(self):
        super().__init__()
        self.articles: List[Dict] = []
        self._current_link: Optional[str] = None
        self._current_title = ""
        self._in_link = False
        self._texts: List[str] = []       # 收集所有文本片段
        self._all_links: List[Dict] = []   # 所有带 google redirect 的链接

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            real_url = self._extract_real_url(href)
            if real_url:
                self._in_link = True
                self._current_link = real_url
                self._current_title = ""

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            self._in_link = False
            if self._current_link and self._current_title.strip():
                self._all_links.append({
                    "title": self._current_title.strip(),
                    "link":  self._current_link,
                    "pos":   len(self._texts),  # 记录位置，用于后续提取摘要
                })
            self._current_link = None

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._in_link:
            self._current_title += data
        self._texts.append(text)

    def _extract_real_url(self, href: str) -> Optional[str]:
        """从 Google 跳转链接中提取真实 URL"""
        if "google.com/url" not in href:
            return None
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        url = params.get("url", params.get("q", [None]))[0]
        if url:
            url = unquote(url)
            # 过滤掉 Google 自身的链接和支持页面
            if "support.google.com" in url or "accounts.google.com" in url:
                return None
            return url
        return None

    def get_articles(self) -> List[Dict]:
        """整理解析结果，为每条新闻附加摘要"""
        articles = []
        for i, link_info in enumerate(self._all_links):
            title = link_info["title"]
            url   = link_info["link"]
            pos   = link_info["pos"]

            # 摘要：取链接后面的文本片段（通常紧跟着就是摘要）
            snippet_parts = []
            next_link_pos = (self._all_links[i + 1]["pos"]
                            if i + 1 < len(self._all_links)
                            else len(self._texts))

            for j in range(pos, min(pos + 5, next_link_pos)):
                if j < len(self._texts):
                    t = self._texts[j].strip()
                    # 跳过标题本身、过短的文本、标记性文本
                    if t == title or len(t) < 4:
                        continue
                    if t.lower() in ("flag as irrelevant", "标记为不相关"):
                        continue
                    snippet_parts.append(t)

            snippet = " ".join(snippet_parts)[:300]

            # 尝试从摘要末尾提取来源（通常是最后一段短文本）
            source = ""
            if snippet_parts:
                last = snippet_parts[-1]
                # 来源通常很短（媒体名称）
                if len(last) < 30 and len(snippet_parts) > 1:
                    source = last
                    snippet = " ".join(snippet_parts[:-1])[:300]

            articles.append({
                "title":   title,
                "summary": snippet,
                "link":    url,
                "source":  source,
            })

        return articles


def _decode_mime_str(s: str) -> str:
    """解码 MIME 编码的邮件头"""
    if not s:
        return ""
    parts = decode_header(s)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _get_email_html(msg: email.message.Message) -> str:
    """从邮件对象中提取 HTML 正文"""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
    else:
        if msg.get_content_type() == "text/html":
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


# ═══════════════════════════════════════════════════
#  主要接口
# ═══════════════════════════════════════════════════

def fetch_alerts_from_gmail(
    gmail_address: str = "",
    gmail_password: str = "",
    lookback_days: int = 7,
    alert_subjects: Optional[List[str]] = None,
) -> List[Dict]:
    """
    连接 Gmail IMAP，读取最近 lookback_days 天内的 Google Alerts 邮件，
    解析出所有新闻条目。

    alert_subjects: 只处理邮件标题中包含这些关键词的邮件。
                    Google Alerts 邮件标题格式为 "Google 快讯 - 固态电池 最新进展"，
                    传入 ["固态电池", "钠离子电池"] 就只处理这两个 Alert 的邮件。
                    为 None 或空列表时处理所有 Alerts 邮件。

    返回: [{title, summary, link, source, raw_date, published}, ...]
    """
    addr = gmail_address or os.environ.get("GMAIL_ADDRESS", "")
    pwd  = gmail_password or os.environ.get("GMAIL_APP_PASSWORD", "")

    if not addr or not pwd:
        raise ValueError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD 未设置")

    # 计算搜索日期范围
    since_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
    today_str  = datetime.now().strftime("%Y/%m/%d")

    logger.info("连接 Gmail IMAP: %s", addr)
    logger.info("搜索 %s 以来的 Google Alerts 邮件", since_date)

    conn = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
    try:
        conn.login(addr, pwd)
        # 选择收件箱（也可以用标签，如 "google-alerts"）
        conn.select("INBOX", readonly=True)

        # 搜索条件：发件人是 Google Alerts + 日期范围
        search_criteria = (
            f'(FROM "{ALERTS_SENDER}" SINCE {since_date})'
        )
        status, msg_ids = conn.search(None, search_criteria)
        if status != "OK" or not msg_ids[0]:
            logger.warning("未找到 Google Alerts 邮件")
            return []

        id_list = msg_ids[0].split()
        logger.info("找到 %d 封 Google Alerts 邮件", len(id_list))

        all_articles = []
        seen_links   = set()

        for mid in id_list:
            status, msg_data = conn.fetch(mid, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # 获取邮件日期
            email_date = msg.get("Date", "")
            subject    = _decode_mime_str(msg.get("Subject", ""))

            # ── 按标题过滤：只处理属于当前行业的 Alert ──
            if alert_subjects:
                matched = any(kw in subject for kw in alert_subjects)
                if not matched:
                    logger.debug("  跳过不匹配的邮件: %s", subject[:50])
                    continue

            # 解析 HTML 正文
            html_body = _get_email_html(msg)
            if not html_body:
                logger.debug("邮件无 HTML 正文，跳过: %s", subject)
                continue

            parser = _GoogleAlertsParser()
            parser.feed(html_body)
            articles = parser.get_articles()

            logger.info("  邮件「%s」解析出 %d 条新闻", subject[:40], len(articles))

            for art in articles:
                link = art["link"]
                if link in seen_links:
                    continue
                seen_links.add(link)

                art["raw_date"]  = today_str  # Alerts 每日发送，视为当天新闻
                art["published"] = today_str
                all_articles.append(art)

        logger.info("Gmail 共解析出 %d 条不重复新闻", len(all_articles))
        return all_articles

    finally:
        try:
            conn.logout()
        except Exception:
            pass


def assign_to_categories(
    articles: List[Dict],
    categories: List[Dict],
) -> Dict[str, List[Dict]]:
    """
    将文章按关键词匹配分配到各分类。
    一篇文章可以匹配多个分类。
    没有匹配到任何分类的文章放入第一个分类（通常是"要闻"）。

    categories: 配置文件中的 CATEGORIES 列表
    返回: {cat_id: [articles]}
    """
    result: Dict[str, List[Dict]] = {cat["id"]: [] for cat in categories}

    # 为每个分类构建关键词集合（从 queries 中提取）
    cat_keywords: Dict[str, List[str]] = {}
    for cat in categories:
        keywords = set()
        for query in cat.get("queries", []):
            # 分词：按空格拆开，去掉 OR 等连接词
            for word in query.split():
                w = word.strip()
                if w and w.upper() != "OR" and len(w) >= 2:
                    keywords.add(w)
        cat_keywords[cat["id"]] = list(keywords)

    # 匹配
    for art in articles:
        text = f"{art.get('title', '')} {art.get('summary', '')}"
        matched = False

        for cat in categories:
            cat_id = cat["id"]
            kws = cat_keywords[cat_id]
            # 文章标题或摘要中包含该分类的任意关键词即匹配
            for kw in kws:
                if kw in text:
                    result[cat_id].append(art)
                    matched = True
                    break  # 一个分类只匹配一次
            if matched:
                break

        # 未匹配任何分类 → 放入第一个分类（兜底）
        if not matched and categories:
            result[categories[0]["id"]].append(art)

    for cat in categories:
        logger.info("  [%s] 分配到 %d 条", cat["id"], len(result[cat["id"]]))

    return result