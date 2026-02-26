"""Test cookie loading and Athletic article scraping."""
import asyncio
import json
import os
import sys

from src.scraper import _convert_cookies
from playwright.async_api import async_playwright


async def main():
    cookie_json = os.environ.get("ATHLETIC_COOKIES", "[]")
    raw_cookies = json.loads(cookie_json)
    print(f"Loaded {len(raw_cookies)} raw cookies")

    if not raw_cookies:
        print("ERROR: No cookies found. Set ATHLETIC_COOKIES env var.")
        sys.exit(1)

    cookies = _convert_cookies(raw_cookies)
    print(f"Converted {len(cookies)} cookies for Playwright")

    # Use a real Athletic article URL from RSS
    import httpx
    import feedparser
    resp = httpx.get("https://www.nytimes.com/athletic/rss/news/", timeout=30, follow_redirects=True)
    feed = feedparser.parse(resp.text)

    # Find first article with /athletic/ in the link
    article_url = None
    for entry in feed.entries:
        link = entry.get("link", "")
        title = entry.get("title", "")
        if "/athletic/" in link and link.count("/") > 4:
            article_url = link
            print(f"Testing article: {title}")
            print(f"URL: {article_url}")
            break

    if not article_url:
        print("ERROR: No article found in RSS")
        sys.exit(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies(cookies)

        page = await context.new_page()
        print("Navigating...")
        await page.goto(article_url, wait_until="domcontentloaded", timeout=30000)

        for selector in ["article .article-body", ".article-body", "article"]:
            el = await page.query_selector(selector)
            if el:
                text = await el.inner_text()
                if len(text) > 100:
                    print(f"\nSUCCESS: Got {len(text)} chars from '{selector}'")
                    print(f"Preview:\n{text[:300]}...")
                    await browser.close()
                    return

        print("\nFAILED: Could not extract article text")
        print(f"Page title: {await page.title()}")
        # Dump page HTML snippet for debugging
        body = await page.inner_text("body")
        print(f"Body preview: {body[:500]}...")
        await browser.close()


asyncio.run(main())
