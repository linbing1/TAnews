import logging

from playwright.async_api import async_playwright, Page

from src.models import Article

logger = logging.getLogger(__name__)


def convert_cookies(raw_cookies: list[dict]) -> list[dict]:
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


_ARTICLE_SELECTORS = [
    ".article-container",
    "[class*='ArticleWrapper']",
    "main article",
    "main",
]


async def _scrape_page(page: Page, url: str) -> str:
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)

    text = ""
    for selector in _ARTICLE_SELECTORS:
        try:
            await page.wait_for_selector(selector, timeout=10000)
        except Exception:
            continue
        element = await page.query_selector(selector)
        if element:
            text = await element.inner_text()
            if len(text) > 100:
                break

    return text.strip()


async def scrape_full_texts(
    articles: list[Article], cookies: list[dict]
) -> list[Article]:
    pw_cookies = convert_cookies(cookies) if cookies else []
    has_fallbacks = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        if pw_cookies:
            await context.add_cookies(pw_cookies)

        for article in articles:
            page = await context.new_page()
            try:
                text = await _scrape_page(page, article.link)
                if not text:
                    logger.warning("Empty text for %s, using summary", article.link)
                    article.full_text = article.summary
                    has_fallbacks = True
                else:
                    article.full_text = text
                    logger.info("  Scraped %s: %d chars", article.title[:50], len(text))
            except Exception:
                logger.exception("Failed to scrape %s, falling back to summary", article.link)
                article.full_text = article.summary
                has_fallbacks = True
            finally:
                await page.close()

        await browser.close()

    if has_fallbacks:
        logger.warning("Some articles fell back to summary - cookies may be expired")

    return articles, has_fallbacks
