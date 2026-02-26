"""Inspect The Athletic PL page and article structure."""
import asyncio
import json
import os
import re

from src.scraper import _convert_cookies
from playwright.async_api import async_playwright


async def main():
    cookie_json = os.environ.get("ATHLETIC_COOKIES", "[]")
    raw_cookies = json.loads(cookie_json)
    cookies = _convert_cookies(raw_cookies)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()

        # 1. PL listing page
        print("=== PL LISTING PAGE ===")
        await page.goto(
            "https://www.nytimes.com/athletic/football/premier-league/",
            wait_until="networkidle", timeout=60000,
        )

        # Find all links that look like articles (have date pattern in URL)
        all_links = await page.query_selector_all("a[href]")
        article_links = []
        for link in all_links:
            href = await link.get_attribute("href") or ""
            text = (await link.inner_text()).strip()
            # Article URLs: /athletic/DIGITS/YYYY/MM/DD/slug/
            if re.search(r"/athletic/\d+/\d{4}/\d{2}/\d{2}/", href) and text:
                if not href.startswith("http"):
                    href = f"https://www.nytimes.com{href}"
                article_links.append((href, text))

        print(f"Found {len(article_links)} article links")
        for href, text in article_links[:10]:
            print(f"  {text[:80]}")
            print(f"    {href}")

        # 2. Test first PL article
        if article_links:
            print("\n=== ARTICLE PAGE ===")
            url = article_links[0][0]
            print(f"URL: {url}")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Dump page HTML tag structure around main content
            main_el = await page.query_selector("main")
            if main_el:
                # Get the HTML structure (first 3000 chars)
                html = await main_el.evaluate("e => e.innerHTML.substring(0, 3000)")
                # Extract class names and data-testid from the HTML
                classes = set(re.findall(r'class="([^"]+)"', html))
                testids = set(re.findall(r'data-testid="([^"]+)"', html))
                print(f"\nClasses found: {classes}")
                print(f"\ndata-testid found: {testids}")

                text = await main_el.inner_text()
                print(f"\n<main> total text: {len(text)} chars")
                print(f"Preview:\n{text[:500]}")

            # Try to find content with various approaches
            print("\n--- Selector tests ---")
            for selector in [
                "main p", "main div p",
                "[data-testid]",
                "main > div > div",
                "main section",
            ]:
                els = await page.query_selector_all(selector)
                if els:
                    total = sum(len(await e.inner_text()) for e in els[:20])
                    first_text = (await els[0].inner_text())[:100]
                    print(f"'{selector}': {len(els)} els, ~{total} chars, first: {first_text}")

        await browser.close()


asyncio.run(main())
