import logging
from datetime import date

from src.llm import LLMClient
from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """
你是一名中文足球音频节目撰稿人。请根据给定资讯整理成自然、流畅、适合直接口播的中文播报稿。

要求：
1. 包含开场、转场和结尾。
2. 保留英文人名、队名、赛事名和比分，尤其是英文人名、队名和比分，不要误译或省略。
3. 不要使用 Markdown、项目符号或 URL，避免“概述/详情/影响”等书面标签。
4. 语言要像主播在说话，简洁自然，不要写成文章或报告。
5. 总长度控制在 1500-2500 个汉字。
""".strip()


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
                f"key_people_and_data: {article.key_people_and_data}",
                f"impact: {article.impact}",
                f"link: {article.link}",
            ]
        )

    user_text = "\n".join(sections)
    logger.info("Building audio script for %d articles", len(articles))
    return llm.complete(_SYSTEM_PROMPT, user_text).strip()
