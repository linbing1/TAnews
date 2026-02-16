"""Probe The Athletic article pages to find comment count elements."""
import asyncio
import json
import os
import re

from playwright.async_api import async_playwright
from src.scraper import _convert_cookies


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

        # Get listing page for article URLs
        await page.goto(
            "https://www.nytimes.com/athletic/football/premier-league/",
            wait_until="networkidle", timeout=60000,
        )

        all_links = await page.query_selector_all("a[href]")
        urls = []
        for link in all_links:
            href = await link.get_attribute("href") or ""
            if re.search(r"/athletic/\d+/\d{4}/\d{2}/\d{2}/", href):
                if not href.startswith("http"):
                    href = f"https://www.nytimes.com{href}"
                if href not in urls:
                    urls.append(href)
            if len(urls) >= 3:
                break

        # Probe each article for comment-related elements
        for url in urls:
            print(f"\n=== {url} ===")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            for selector in [
                "[data-testid*='comment']",
                "[class*='comment']",
                "[class*='Comment']",
                "[aria-label*='comment']",
                "button:has-text('comment')",
                "a:has-text('comment')",
                "span:has-text('comment')",
            ]:
                els = await page.query_selector_all(selector)
                if els:
                    for el in els[:3]:
                        text = (await el.inner_text()).strip()
                        tag = await el.evaluate("e => e.tagName")
                        cls = await el.evaluate("e => e.className")
                        print(f"  {selector}: <{tag} class='{cls}'> {text[:100]}")

            # Also search page text for numbers near "comment"
            body_text = await page.inner_text("body")
            for match in re.finditer(r'(\d+)\s*comment', body_text, re.IGNORECASE):
                print(f"  Text match: '{match.group(0)}' at pos {match.start()}")

        await browser.close()


asyncio.run(main())
