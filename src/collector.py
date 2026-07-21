import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone

from playwright.async_api import async_playwright

from src.models import Article
from src.scraper import convert_cookies

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

_PL_KEYWORD_PATTERNS = [
    re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)
    for keyword in _PL_KEYWORDS
]

_ARTICLE_URL_PATTERN = re.compile(r"/athletic/\d+/(\d{4})/(\d{2})/(\d{2})/")


def _parse_date_from_url(url: str) -> datetime | None:
    m = _ARTICLE_URL_PATTERN.search(url)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return datetime(y, mo, d, tzinfo=timezone.utc)


ArticleFilter = Callable[[str], bool]


def is_premier_league_article(text: str) -> bool:
    return any(pattern.search(text) for pattern in _PL_KEYWORD_PATTERNS)


async def _extract_summary(link, title: str) -> str:
    try:
        parent = await link.evaluate_handle("el => el.parentElement")
        parent_text = (await parent.inner_text()).strip()
        lines = [line.strip() for line in parent_text.split("\n") if line.strip()]
        extra = [line for line in lines if line != title and len(line) > 15]
        if extra:
            return extra[0]
    except Exception:
        pass
    return title


async def _extract_comment_count(link) -> int:
    try:
        nowrap = await link.query_selector("span[class*='Content_NoWrap']")
        if nowrap:
            nowrap_text = (await nowrap.inner_text()).strip()
            match = re.search(r"\d+", nowrap_text)
            if match:
                return int(match.group())
    except Exception:
        pass
    return 0


async def collect_articles(
    page_url: str,
    cookies: list[dict],
    *,
    article_filter: ArticleFilter | None = is_premier_league_article,
) -> list[Article]:
    """Scrape an Athletic listing page for article titles and links."""
    pw_cookies = convert_cookies(cookies)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        if pw_cookies:
            await context.add_cookies(pw_cookies)

        page = await context.new_page()
        await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("a[href*='/athletic/']", state="attached", timeout=15000)

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

            if article_filter and not article_filter(title):
                continue

            pub_date = _parse_date_from_url(href) or datetime.now(timezone.utc)

            summary = await _extract_summary(link, title)
            comment_count = await _extract_comment_count(link)

            articles.append(
                Article(
                    title=title,
                    link=href,
                    summary=summary,
                    published=pub_date,
                    comment_count=comment_count,
                )
            )

        for a in articles:
            logger.info("  [%s] %s (comments: %d)", a.published.strftime("%Y-%m-%d"), a.title, a.comment_count)
            logger.debug("    link=%s summary=%s", a.link, a.summary)

        await browser.close()

    logger.info("Collected %d articles from listing page", len(articles))
    return articles
