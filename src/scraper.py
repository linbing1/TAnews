import logging

from playwright.async_api import async_playwright

from src.models import Article

logger = logging.getLogger(__name__)


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
            await context.add_cookies(cookies)

        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        selectors = [
            "article .article-body",
            "article [data-testid='article-body']",
            "article .article-content",
            ".article-body",
            "article",
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
