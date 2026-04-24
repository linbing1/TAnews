import logging
from datetime import date
from pathlib import Path

from src.llm import LLMClient
from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "audio_scripter.md").read_text(encoding="utf-8")


def build_audio_script(
    articles: list[AnalyzedArticle],
    llm: LLMClient,
    today: date,
    title_prefix: str = "英超早报",
) -> str:
    if not articles:
        raise ValueError("no articles")

    sections = [
        f"title_prefix: {title_prefix}",
        f"year: {today.year}",
        f"month: {today.month}",
        f"day: {today.day}",
        "articles:",
    ]

    for index, article in enumerate(articles, start=1):
        sections.extend(
            [
                f"- article {index}",
                f"title_cn: {article.title_cn}",
                f"title_original: {article.title_original}",
                f"article_type: {article.article_type}",
                f"importance: {article.importance}",
                f"overview: {article.overview}",
                f"detail: {article.detail}",
                f"link: {article.link}",
            ]
        )

    user_text = "\n".join(sections)
    logger.info("Building audio script for %d articles", len(articles))
    return llm.complete(_SYSTEM_PROMPT, user_text, operation="build_audio_script").strip()
