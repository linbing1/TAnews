import asyncio
import json
import logging
from dataclasses import fields
from pathlib import Path

from src.llm import LLMClient
from src.models import AnalyzedArticle, Article

logger = logging.getLogger(__name__)

_ANALYZED_FIELDS = {f.name for f in fields(AnalyzedArticle)}

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "analyzer.md").read_text(encoding="utf-8")


def _parse_response(response: str) -> dict | None:
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM response as JSON:\n%s", response)
        return None


async def _analyze_one(i: int, total: int, a: Article, llm: LLMClient) -> AnalyzedArticle | None:
    user_text = f"Title: {a.title}\nLink: {a.link}\nContent:\n{a.full_text}"
    logger.info("Analyzing article %d/%d: %s (%d chars)", i, total, a.title, len(user_text))

    try:
        response = await asyncio.to_thread(llm.complete, _SYSTEM_PROMPT, user_text, operation="analyze_articles")
    except Exception:
        logger.exception("LLM request failed for article: %s", a.title)
        return None

    item = _parse_response(response)
    if item is None:
        return None

    if isinstance(item, list):
        item = item[0] if item else None
    if not isinstance(item, dict):
        logger.warning("Unexpected response type for article: %s", a.title)
        return None

    try:
        filtered = {k: v for k, v in item.items() if k in _ANALYZED_FIELDS}
        filtered["link"] = filtered.get("link") or a.link
        filtered["importance"] = int(filtered["importance"])
        return AnalyzedArticle(**filtered)
    except (TypeError, ValueError, KeyError) as e:
        logger.warning("Skipping article with invalid analyzed fields: %s", e)
        return None


async def analyze_articles(
    articles: list[Article], llm: LLMClient
) -> list[AnalyzedArticle]:
    tasks = [_analyze_one(i, len(articles), a, llm) for i, a in enumerate(articles, 1)]
    results = await asyncio.gather(*tasks)
    result = [r for r in results if r is not None]
    logger.info("Analyzed %d/%d articles successfully", len(result), len(articles))
    return result
