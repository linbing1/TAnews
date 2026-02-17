import logging

from src.collector import collect_articles
from src.models import Article

logger = logging.getLogger(__name__)


async def collect_hot_articles(
    page_url: str, cookies: list[dict], top_n: int = 5
) -> list[Article]:
    """Collect articles and return top N sorted by comment count."""
    articles = await collect_articles(page_url, cookies)

    articles.sort(key=lambda a: a.comment_count, reverse=True)
    result = articles[:top_n]

    logger.info("Top %d by comments:", len(result))
    for a in result:
        logger.info("  [%d comments] %s", a.comment_count, a.title[:60])

    return result
