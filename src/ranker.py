import logging
import re

from src.llm import LLMClient
from src.models import Article

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a Premier League football news editor.
Given a list of articles with their titles, summaries, and publish dates, select the {top_n} most important ones.

Criteria for importance:
- Freshness: strongly prefer articles published in the last 24 hours
- Major match results and their implications
- Transfer news with credible sources
- Tactical/strategic analysis with depth
- Injury updates for key players
- Title race / relegation battle impact

Return ONLY a comma-separated list of article indices (0-based), ordered by importance (most important first).
Example: 3,1,7,0,5"""


def rank_articles(
    articles: list[Article], llm: LLMClient, top_n: int = 5
) -> list[Article]:
    if len(articles) <= top_n:
        return articles

    article_list = "\n".join(
        f"[{i}] ({a.published.strftime('%Y-%m-%d')}) {a.title}"
        + (f"\n    {a.summary}" if a.summary != a.title else "")
        for i, a in enumerate(articles)
    )

    response = llm.complete(
        _SYSTEM_PROMPT.format(top_n=top_n),
        f"Select the top {top_n} from these articles:\n\n{article_list}",
    )

    indices = _parse_indices(response, len(articles), top_n)
    result = [articles[i] for i in indices]
    logger.debug("Ranker LLM prompt:\n%s", article_list)
    logger.debug("Ranker LLM response: %s", response)
    for a in result:
        logger.info("  Selected: [%s] %s", a.published.strftime("%Y-%m-%d"), a.title)
    logger.info("Ranked %d articles, selected top %d", len(articles), len(result))
    return result


def _parse_indices(response: str, total: int, top_n: int) -> list[int]:
    numbers = re.findall(r"\d+", response)
    seen = set()
    indices = []
    for n in numbers:
        idx = int(n)
        if 0 <= idx < total and idx not in seen:
            seen.add(idx)
            indices.append(idx)
        if len(indices) >= top_n:
            break
    return indices
