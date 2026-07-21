import logging

from src.collector import collect_articles
from src.models import Article

logger = logging.getLogger(__name__)


async def collect_hot_articles(
    page_url: str, cookies: list[dict], top_n: int = 5, exclude_links: set[str] | None = None
) -> list[Article]:
    """Return the most discussed articles, preferring links not used by the digest."""
    articles = await collect_articles(page_url, cookies)

    articles.sort(key=lambda a: a.comment_count, reverse=True)
    result = articles[:top_n]
    if exclude_links:
        fresh = [a for a in articles if a.link not in exclude_links]
        repeated = [a for a in articles if a.link in exclude_links]
        result = fresh[:top_n]
        logger.info("Excluded %d articles already in digest", len(repeated))

        if len(result) < top_n:
            backfill = repeated[:top_n - len(result)]
            result.extend(backfill)
            if backfill:
                logger.info(
                    "Backfilled %d digest articles to reach requested count",
                    len(backfill),
                )

    logger.info("Top %d by comments:", len(result))
    for a in result:
        logger.info("  [%d comments] %s", a.comment_count, a.title[:60])

    return result
