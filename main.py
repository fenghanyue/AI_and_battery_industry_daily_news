# -*- coding: utf-8 -*-
"""
行业日报/周报 - 主程序（多行业 + 多周期版）
用法：
    python main.py --profile ai --period daily     # AI 行业日报（每天）
    python main.py --profile ai --period weekly    # AI 行业周报（每周）
    python main.py --profile battery --period daily
    python main.py --profile ai --period weekly --dry-run
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from config.settings    import load_profile, load_period
from src.news_fetcher   import fetch_all
from src.sources        import available_sources
from src.ai_summarizer  import summarize_all
from src.html_generator import generate_html
from src.email_sender   import send_report

Path("logs").mkdir(exist_ok=True)
Path("cache").mkdir(exist_ok=True)
Path("output").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/report.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main(profile_name="ai", period_name="daily", dry_run=False, no_fetch=False,
         sources=None):
    # ── 加载行业配置 + 周期配置 ──
    profile    = load_profile(profile_name)
    period     = load_period(period_name)
    categories = profile.CATEGORIES
    title      = f"{profile.REPORT_TITLE}{period['label']}"   # 如「AI 行业日报」/「AI 行业周报」
    alert_subjects = getattr(profile, "ALERT_SUBJECTS", None)

    # 缓存按 profile + period 区分，避免日报/周报互相串数据
    cache_file = Path(f"cache/last_{profile_name}_{period_name}.json")

    start = datetime.now()
    logger.info("=" * 50)
    logger.info("开始生成 %s [%s] profile=%s period=%s",
                title, start.strftime("%Y-%m-%d %H:%M:%S"), profile_name, period_name)
    logger.info("=" * 50)

    if no_fetch and cache_file.exists():
        logger.info("使用缓存数据: %s", cache_file)
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
        summarized = cache["summarized"]
    else:
        # Step 1: 抓取回溯期内新闻
        logger.info("Step 1/3: 抓取最近 %d 天新闻...", period["lookback_days"])
        raw_news = fetch_all(categories, lookback_days=period["lookback_days"],
                             alert_subjects=alert_subjects,
                             sources=sources, profile=profile)

        # Step 2: 豆包筛选摘要
        logger.info("Step 2/3: 豆包筛选摘要...")
        summarized = summarize_all(categories, raw_news, period)

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"summarized": summarized}, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in summarized.values())
    logger.info("共保留 %d 条新闻", total)

    if total == 0:
        logger.warning("没有有效新闻，跳过生成")
        return

    # Step 3: 生成 HTML
    logger.info("Step 3/3: 生成 HTML...")
    html_path = generate_html(categories, summarized,
                              report_title=title, profile=profile_name, period=period)
    logger.info("已保存: %s", html_path)

    # 发送邮件
    if dry_run:
        logger.info("dry-run，跳过邮件发送，HTML 文件在: %s", html_path)
    else:
        logger.info("发送邮件...")
        send_report(html_path, report_title=title, period=period)

    logger.info("完成！耗时 %d 秒", (datetime.now() - start).seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="行业日报/周报生成器")
    parser.add_argument("--profile",  default="ai",
                        choices=["ai", "battery"],
                        help="行业配置：ai=AI行业, battery=电池行业")
    parser.add_argument("--period",   default="daily",
                        choices=["daily", "weekly"],
                        help="报告周期：daily=日报(回溯1天), weekly=周报(回溯7天)")
    parser.add_argument("--dry-run",  action="store_true", help="不发邮件，只生成 HTML")
    parser.add_argument("--no-fetch", action="store_true", help="用缓存数据，不重新抓取")
    parser.add_argument("--sources",  default=None,
                        help="启用的数据源，逗号分隔（可选：%s；默认取环境变量 SOURCES / 行业配置，未配置时只有 gmail）"
                             % ", ".join(available_sources()))
    args = parser.parse_args()
    main(profile_name=args.profile, period_name=args.period,
         dry_run=args.dry_run, no_fetch=args.no_fetch, sources=args.sources)