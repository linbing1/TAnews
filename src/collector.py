import logging
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright

from src.models import Article
from src.scraper import _convert_cookies

logger = logging.getLogger(__name__)

_PL_KEYWORDS = [
    "premier league",
    "arsenal", "aston villa", "bournemouth", "brentford", "brighton",
    "chelsea", "crystal palace", "everton", "fulham", "ipswich",
    "leicester", "liverpool", "manchester city", "manchester united",
    "man city", "man utd", "newcastle", "nottingham forest",
    "southampton", "tottenham", "spurs", "west ham", "wolves",
    "salah", "haaland", "saka", "palmer", "son",
]

_ARTICLE_URL_PATTERN = re.compile(r"/athletic/\d+/(\d{4})/(\d{2})/(\d{2})/")


def _parse_date_from_url(url: str) -> datetime | None:
    m = _ARTICLE_URL_PATTERN.search(url)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return datetime(y, mo, d, tzinfo=timezone.utc)


def _is_premier_league(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _PL_KEYWORDS)


async def collect_articles(
    page_url: str, cookies: list[dict]
) -> list[Article]:
    """Scrape the Athletic PL listing page for article titles and links."""
    pw_cookies = _convert_cookies(cookies) if cookies else []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        if pw_cookies:
            await context.add_cookies(pw_cookies)

        page = await context.new_page()
        await page.goto(page_url, wait_until="networkidle", timeout=60000)

        all_links = await page.query_selector_all("a[href]")
        seen_urls = set()
        articles = []

        for link in all_links:
            href = await link.get_attribute("href") or ""
            if not _ARTICLE_URL_PATTERN.search(href):
                continue

            if not href.startswith("http"):
                href = f"https://www.nytimes.com{href}"

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = (await link.inner_text()).strip()
            if not title or len(title) < 10:
                continue

            if not _is_premier_league(title):
                continue

            pub_date = _parse_date_from_url(href) or datetime.now(timezone.utc)

            articles.append(
                Article(
                    title=title,
                    link=href,
                    summary=title,  # listing page has no separate summary
                    published=pub_date,
                )
            )

        await browser.close()

    logger.info("Collected %d Premier League articles from listing page", len(articles))
    return articles
