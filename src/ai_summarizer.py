# -*- coding: utf-8 -*-
"""
AI 摘要 - 豆包对每个分类的文章进行筛选、压缩摘要
（时效性由 Google Alerts 保证，不再做日期校验）
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
DOUBAO_API_KEY  = os.environ.get("DOUBAO_API_KEY", "")
DOUBAO_MODEL    = os.environ.get("DOUBAO_MODEL", "")


def _parse_json(text: str):
    text = text.strip()
    if "```" in text:
        for p in text.split("```"):
            t = p[4:] if p.startswith("json") else p
            if "{" in t or "[" in t:
                text = t
                break
    start = min((text.find("{") if "{" in text else 9999),
                (text.find("[") if "[" in text else 9999))
    end   = max(text.rfind("}"), text.rfind("]")) + 1
    if start < end:
        text = text[start:end]
    return json.loads(text.strip())


def _chat(messages: list, max_tokens: int = 3000, temperature: float = 0.2) -> str:
    resp = requests.post(
        DOUBAO_BASE_URL,
        headers={"Authorization": f"Bearer {DOUBAO_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": DOUBAO_MODEL, "messages": messages,
              "max_tokens": max_tokens, "temperature": temperature},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def summarize_category(cat: Dict, articles: List[Dict], date_phrase: str,
                       min_items: int, max_items: int) -> List[Dict]:
    if not articles:
        return []

    news_text = ""
    for i, a in enumerate(articles):
        news_text += (
            f"[{i}] 来源：{a['source']}\n"
            f"    标题：{a['title']}\n"
            f"    链接：{a['link']}\n"
            f"    摘要：{a['summary'][:120]}\n\n"
        )

    prompt = f"""你是行业编辑，正在整理【{cat['name']}】分类{date_phrase}的新闻。

以下是候选文章（共 {len(articles)} 条，来自已配置的新闻源，时效性已确认）：

{news_text}

=== 任务 ===

从中选出最值得关注的 {min_items}-{max_items} 条，内容高度重复的合并成一条。

每条输出：
- headline：重写标题，20字以内，主语+事件，简洁有力
- digest：120字左右的摘要（不少于100字，不超过140字），写清楚：
  1. 具体发生了什么（谁、做了什么、关键数据）
  2. 为什么重要或有什么影响
  3. 背景补充（如果有）
- importance：重要/关注/一般
- source：来源媒体名
- link：从文章的"链接："字段原样复制，一字不改
- tags：2-4个关键词，逗号分隔

只输出 JSON，不要其他文字：
{{
  "items": [
    {{
      "headline": "标题",
      "digest": "120字左右的摘要",
      "importance": "重要/关注/一般",
      "source": "来源",
      "link": "原始链接原样复制",
      "tags": "标签1,标签2"
    }}
  ]
}}

如果没有值得收录的文章，输出：{{"items": []}}"""

    for attempt in range(3):
        try:
            raw    = _chat([{"role": "user", "content": prompt}], max_tokens=3000)
            parsed = _parse_json(raw)
            items  = parsed.get("items", [])
            logger.info("  [%s] AI 返回 %d 条（原 %d 条）", cat["name"], len(items), len(articles))
            return items
        except Exception as e:
            logger.warning("  [%s] 第%d次失败: %s", cat["name"], attempt + 1, e)
            if attempt < 2:
                import time; time.sleep(10)
    logger.error("  [%s] 3次重试均失败，跳过", cat["name"])
    return []


def summarize_all(categories: List[Dict], raw_news: Dict[str, List[Dict]],
                  period: Dict) -> Dict[str, List[Dict]]:
    today     = datetime.now().strftime("%Y年%m月%d日")
    lookback  = period["lookback_days"]
    start_str = (datetime.now() - timedelta(days=lookback)).strftime("%Y年%m月%d日")
    # 日报 → 昨日单日；周报 → 过去一周区间
    if lookback <= 1:
        date_phrase = f"昨日（{start_str}）"
    else:
        date_phrase = f"过去一周（{start_str} 至 {today}）"
    min_items = period["min_items"]
    max_items = period["max_items"]

    result = {}
    for cat in categories:
        cat_id   = cat["id"]
        articles = raw_news.get(cat_id, [])
        logger.info("豆包处理: [%s] %d 条候选", cat["name"], len(articles))
        result[cat_id] = summarize_category(cat, articles, date_phrase, min_items, max_items)

    return result