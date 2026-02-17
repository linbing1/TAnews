import json
import logging

from src.llm import LLMClient
from src.models import Article, AnalyzedArticle

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是一位资深英超足球记者和分析师。请对以下英超文章进行深度中文分析。

核心原则：尽量保留原文的丰富内容，不要过度精简。读者希望通过你的分析获取接近原文的信息量，而不仅仅是摘要。

对每篇文章，返回一个 JSON 数组，每个元素包含：
- title_cn: 中文标题翻译
- title_original: 英文原标题
- article_type: 文章类型（深度分析/新闻报道/战术解读/转会动态/赛后分析）
- importance: 重要性 1-5
- overview: 3-5 句话概述核心论点，包含关键结论和背景（中文）
- detail: 深度转述原文内容，要求：（1）保留原文中所有重要论据、数据、直接引语、战术细节和具体事例；（2）按原文逻辑结构组织，不要遗漏关键段落；（3）深度分析类 800-1200 字，普通新闻 400-600 字（中文）
- key_people_and_data: 涉及的关键人物和数据，列出所有被提及的人名、具体数据和统计（中文）
- impact: 影响分析与展望，包含短期和中长期影响（中文）
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
