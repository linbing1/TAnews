import json
import logging
from dataclasses import fields

from src.llm import LLMClient
from src.models import AnalyzedArticle, Article

logger = logging.getLogger(__name__)

_ANALYZED_FIELDS = {f.name for f in fields(AnalyzedArticle)}

_SYSTEM_PROMPT = """你是一位资深英超足球记者和分析师。请对以下英超文章进行深度中文分析。

核心原则：尽量保留原文的丰富内容，不要过度精简。读者希望通过你的分析获取接近原文的信息量，而不仅仅是摘要。

返回一个 JSON 对象，包含：
- title_cn: 中文标题翻译
- title_original: 英文原标题
- article_type: 文章类型（深度分析/新闻报道/战术解读/转会动态/赛后分析）
- importance: 重要性 1-5
- overview: 3-5 句话概述核心论点，包含关键结论和背景（中文）
- detail: 深度转述原文内容，要求：（1）保留原文中所有重要论据、数据、直接引语、战术细节和具体事例；（2）按原文逻辑结构组织，不要遗漏关键段落；（3）深度分析类 800-1200 字，普通新闻 400-600 字（中文）
- key_people_and_data: 涉及的关键人物和数据，列出所有被提及的人名、具体数据和统计（中文）
- impact: 影响分析与展望，包含短期和中长期影响（中文）
- link: 原文链接

仅返回 JSON 对象，不要添加任何其他文字。"""


def _parse_response(response: str) -> dict | None:
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.error("Failed to parse LLM response as JSON: %s", response[:200])
        return None


def analyze_articles(
    articles: list[Article], llm: LLMClient
) -> list[AnalyzedArticle]:
    result = []
    for i, a in enumerate(articles, 1):
        user_text = f"Title: {a.title}\nLink: {a.link}\nContent:\n{a.full_text}"
        logger.info("Analyzing article %d/%d: %s (%d chars)", i, len(articles), a.title, len(user_text))

        try:
            response = llm.complete(_SYSTEM_PROMPT, user_text)
        except Exception:
            logger.exception("LLM request failed for article: %s", a.title)
            continue

        item = _parse_response(response)
        if item is None:
            continue

        # handle case where LLM returns a list with one element
        if isinstance(item, list):
            item = item[0] if item else None
        if not isinstance(item, dict):
            logger.warning("Unexpected response type for article: %s", a.title)
            continue

        try:
            filtered = {k: v for k, v in item.items() if k in _ANALYZED_FIELDS}
            result.append(AnalyzedArticle(**filtered))
        except TypeError as e:
            logger.warning("Skipping article with missing field: %s", e)

    logger.info("Analyzed %d/%d articles successfully", len(result), len(articles))
    return result
