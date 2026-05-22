import logging

from src.collector import collect_articles
from src.models import Article

logger = logging.getLogger(__name__)


async def collect_hot_articles(
    page_url: str, cookies: list[dict], top_n: int = 5, exclude_links: set[str] | None = None
) -> list[Article]:
    """Collect articles and return top N sorted by comment count, excluding given links."""
    articles = await collect_articles(page_url, cookies)

    articles.sort(key=lambda a: a.comment_count, reverse=True)
    if exclude_links:
        before = len(articles)
        articles = [a for a in articles if a.link not in exclude_links]
        logger.info("Excluded %d articles already in digest", before - len(articles))
    result = articles[:top_n]

    logger.info("Top %d by comments:", len(result))
    for a in result:
        logger.info("  [%d comments] %s", a.comment_count, a.title[:60])

    return result
