import logging
from datetime import date

import httpx

from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)

def format_digest(
    articles: list[AnalyzedArticle],
    today: date | None = None,
    title_prefix: str = "英超每日精选",
) -> tuple[str, str]:
    today = today or date.today()
    title = f"{title_prefix} - {today}"

    sections = []
    for i, a in enumerate(articles, 1):
        stars = "⭐" * a.importance
        section = f"""## {i}. {a.title_cn}
**原标题：** {a.title_original}
**类型：** {a.article_type}
**重要性：** {stars}

### 文章概述
{a.overview}

### 详细内容
{a.detail}

### 关键人物与数据
{a.key_people_and_data}

### 影响与展望
{a.impact}

🔗 [阅读原文]({a.link})"""
        sections.append(section)

    body = f"# ⚽ {title}\n\n" + "\n\n---\n\n".join(sections)
    return title, body


def notify(
    articles: list[AnalyzedArticle],
    serverchan_key: str,
    today: date | None = None,
    title_prefix: str = "英超每日精选",
) -> bool:
    title, body = format_digest(articles, today, title_prefix=title_prefix)

    url = f"https://sctapi.ftqq.com/{serverchan_key}.send"
    resp = httpx.post(url, data={"title": title, "desp": body}, timeout=30)
    resp.raise_for_status()

    result = resp.json()
    if result.get("code") == 0:
        logger.info("Push notification sent successfully")
        return True

    logger.error("Server酱 push failed: %s", result)
    return False
