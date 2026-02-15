import logging
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from src.models import Article

logger = logging.getLogger(__name__)

_PL_KEYWORDS = [
    "premier league",
    "arsenal", "aston villa", "bournemouth", "brentford", "brighton",
    "chelsea", "crystal palace", "everton", "fulham", "ipswich",
    "leicester", "liverpool", "manchester city", "manchester united",
    "man city", "man utd", "newcastle", "nottingham forest",
    "southampton", "tottenham", "spurs", "west ham", "wolves",
]


def _is_premier_league(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in _PL_KEYWORDS)


def collect_articles(
    rss_url: str, now: datetime | None = None, hours: int = 48
) -> list[Article]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    resp = httpx.get(rss_url, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    articles = []

    for entry in feed.entries:
        try:
            published = parsedate_to_datetime(entry.get("published", ""))
        except Exception:
            continue

        if published < cutoff:
            continue

        title = entry.get("title", "")
        summary = entry.get("description", entry.get("summary", ""))

        if not _is_premier_league(title, summary):
            continue

        articles.append(
            Article(
                title=title,
                link=entry.get("link", ""),
                summary=summary,
                published=published,
            )
        )

    logger.info("Collected %d Premier League articles from RSS", len(articles))
    return articles
