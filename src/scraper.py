import logging

from playwright.async_api import async_playwright

from src.models import Article

logger = logging.getLogger(__name__)


def _convert_cookies(raw_cookies: list[dict]) -> list[dict]:
    """Convert Cookie-Editor export format to Playwright format."""
    converted = []
    for c in raw_cookies:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
        }
        same_site = c.get("sameSite", "Lax")
        if same_site in ("unspecified", "no_restriction"):
            same_site = "None"
        elif same_site not in ("Strict", "Lax", "None"):
            same_site = "Lax"
        cookie["sameSite"] = same_site

        if "expirationDate" in c:
            cookie["expires"] = c["expirationDate"]

        converted.append(cookie)
    return converted


async def scrape_full_texts(
    articles: list[Article], cookies: list[dict]
) -> list[Article]:
    cookie_expired = False

    for article in articles:
        try:
            text = await _scrape_one(article.link, cookies)
            if not text:
                logger.warning("Empty text for %s, using summary", article.link)
                article.full_text = article.summary
                cookie_expired = True
            else:
                article.full_text = text
                logger.info("  Scraped %s: %d chars", article.title[:50], len(text))
        except Exception:
            logger.exception("Failed to scrape %s, falling back to summary", article.link)
            article.full_text = article.summary
            cookie_expired = True

    if cookie_expired:
        logger.warning("Cookie may be expired - some articles fell back to summary")

    return articles


async def _scrape_one(url: str, cookies: list[dict]) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        if cookies:
            await context.add_cookies(_convert_cookies(cookies))

        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)

        selectors = [
            ".article-container",
            "[class*='ArticleWrapper']",
            "main article",
            "main",
        ]

        text = ""
        for selector in selectors:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                if len(text) > 100:
                    break

        await browser.close()
        return text.strip()
