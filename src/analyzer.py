import json
import logging

from src.llm import LLMClient
from src.models import Article, AnalyzedArticle

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是一位资深英超足球记者和分析师。请对以下英超文章进行深度中文分析。

对每篇文章，返回一个 JSON 数组，每个元素包含：
- title_cn: 中文标题翻译
- title_original: 英文原标题
- article_type: 文章类型（深度分析/新闻报道/战术解读/转会动态/赛后分析）
- importance: 重要性 1-5
- overview: 2-3 句话概述核心论点（中文）
- detail: 详细转述文章关键论据和分析逻辑，保留数据、引用、战术细节。深度分析类 300-500 字，普通新闻 150-200 字（中文）
- key_people_and_data: 涉及的关键人物和数据（中文）
- impact: 影响分析与展望（中文）
- link: 原文链接

仅返回 JSON 数组，不要添加任何其他文字。"""


def analyze_articles(
    articles: list[Article], llm: LLMClient
) -> list[AnalyzedArticle]:
    article_texts = "\n\n---\n\n".join(
        f"Title: {a.title}\nLink: {a.link}\nContent:\n{a.full_text}"
        for a in articles
    )

    response = llm.complete(_SYSTEM_PROMPT, article_texts)
    logger.debug("Analyzer LLM response:\n%s", response[:500])

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        data = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.error("Failed to parse LLM response as JSON: %s", response[:200])
        return []

    result = []
    for item in data:
        try:
            result.append(
                AnalyzedArticle(
                    title_cn=item["title_cn"],
                    title_original=item["title_original"],
                    article_type=item["article_type"],
                    importance=item["importance"],
                    overview=item["overview"],
                    detail=item["detail"],
                    key_people_and_data=item["key_people_and_data"],
                    impact=item["impact"],
                    link=item["link"],
                )
            )
        except KeyError as e:
            logger.warning("Skipping article with missing field: %s", e)

    logger.info("Analyzed %d articles successfully", len(result))
    return result
