# -*- coding: utf-8 -*-
"""
邮件发送 - HTML 正文 + HTML 附件（多行业通用版）
"""

import os
import smtplib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import make_msgid, formatdate

logger = logging.getLogger(__name__)

SENDER_EMAIL    = os.environ.get("OUTLOOK_EMAIL", "")
SENDER_PASSWORD = os.environ.get("OUTLOOK_PASSWORD", "")
RECIPIENTS      = [r.strip() for r in os.environ.get("RECIPIENT_EMAILS", "").split(",") if r.strip()]
SMTP_HOST       = "smtp.163.com"
SMTP_PORT       = 465


def send_report(html_path: str, report_title: str = "AI 行业日报", period: dict = None):
    """
    发送报告邮件（日报 / 周报通用）。
    report_title: 邮件标题前缀，如 "AI 行业日报" / "电池行业周报"
    period: 周期配置 dict（含 lookback_days/label），缺省按日报处理
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise ValueError("OUTLOOK_EMAIL / OUTLOOK_PASSWORD 未设置")
    if not RECIPIENTS:
        raise ValueError("RECIPIENT_EMAILS 未设置")

    if period is None:
        period = {"lookback_days": 1, "label": "日报"}

    today     = datetime.now().strftime("%Y年%m月%d日")
    lookback  = period["lookback_days"]
    start_str = (datetime.now() - timedelta(days=lookback)).strftime("%Y年%m月%d日")
    # 日报 → 单日；周报 → 区间
    date_disp = start_str if lookback <= 1 else f"{start_str} - {today}"
    subject   = f"{report_title} · {date_disp}"

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    plain_text = f"{report_title} · {date_disp}\n\n请下载附件用浏览器打开查看完整{period['label']}。"

    msg = MIMEMultipart("mixed")
    msg["From"]       = SENDER_EMAIL
    msg["To"]         = ", ".join(RECIPIENTS)
    msg["Subject"]    = subject
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    body = MIMEMultipart("alternative")
    body.attach(MIMEText(plain_text, "plain", "utf-8"))
    body.attach(MIMEText(html_content, "html", "utf-8"))
    msg.attach(body)

    filename = Path(html_path).name
    with open(html_path, "rb") as f:
        part = MIMEBase("text", "html")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    logger.info("发送邮件至: %s", RECIPIENTS)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENTS, msg.as_string())
    logger.info("邮件发送成功")
