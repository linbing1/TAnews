# Hot Comments Digest Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a second daily push (Beijing 07:30) that sends the top 5 most-commented Premier League articles from The Athletic, analyzed by LLM and pushed to WeChat.

**Architecture:** New `src/hot_collector.py` collects all PL articles from the listing page, opens each article page to scrape comment count, sorts by comments descending, returns top 5. New `main_hot.py` orchestrates: hot_collector → scraper → analyzer → notifier. Reuses existing scraper, analyzer, notifier modules. New GitHub Actions job at UTC 23:30.

**Tech Stack:** Python 3.12, Playwright, pytest, pytest-asyncio

---

### Task 1: Add `comment_count` field to Article model

**Files:**
- Modify: `src/models.py:6-11`
- Test: `tests/test_collector.py` (verify existing tests still pass)

**Step 1: Add the field**

In `src/models.py`, add `comment_count: int = 0` after `full_text`:

```python
@dataclass
class Article:
    title: str
    link: str
    summary: str
    published: datetime
    full_text: str = ""
    comment_count: int = 0
```

**Step 2: Run existing tests to verify nothing breaks**

Run: `pytest tests/ -v`
Expected: ALL PASS (22 tests). The new field has a default so all existing code continues to work.

**Step 3: Commit**

```
feat: add comment_count field to Article model
```

---

### Task 2: Add `title_prefix` parameter to notifier

**Files:**
- Modify: `src/notifier.py:13-17` (`format_digest`), `src/notifier.py:46-51` (`notify`)
- Test: `tests/test_notifier.py`

**Step 1: Write failing test**

Add to `tests/test_notifier.py::TestFormatDigest`:

```python
    def test_custom_title_prefix(self):
        articles = [_make_analyzed()]
        title, body = format_digest(articles, date(2026, 2, 16), title_prefix="英超热议文章")
        assert "英超热议文章" in title
        assert "2026-02-16" in title
        assert "英超每日精选" not in title
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_notifier.py::TestFormatDigest::test_custom_title_prefix -v`
Expected: FAIL — `format_digest() got an unexpected keyword argument 'title_prefix'`

**Step 3: Add `title_prefix` parameter**

In `src/notifier.py`, update `format_digest`:

```python
def format_digest(
    articles: list[AnalyzedArticle],
    today: date | None = None,
    title_prefix: str = "英超每日精选",
) -> tuple[str, str]:
    today = today or date.today()
    title = f"{title_prefix} - {today}"
```

Update `notify` to pass through the parameter:

```python
def notify(
    articles: list[AnalyzedArticle],
    serverchan_key: str,
    today: date | None = None,
    title_prefix: str = "英超每日精选",
) -> bool:
    title, body = format_digest(articles, today, title_prefix=title_prefix)
```

**Step 4: Run all notifier tests**

Run: `pytest tests/test_notifier.py -v`
Expected: ALL PASS.

**Step 5: Commit**

```
feat: add title_prefix parameter to notifier
```

---

### Task 3: Create page structure probe script for comment count

**Files:**
- Create: `test_comment_structure.py`

This is an exploratory task — we need to find the CSS selector for comment count on article pages before we can implement `hot_collector`. This script is a manual test (not in `tests/`).

**Step 1: Create the probe script**

```python
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

            # Search for comment-related text/elements
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
```

**Step 2: Commit**

```
chore: add comment count probe script
```

**Step 3: Run manually (requires env vars)**

Run: `python test_comment_structure.py`

Document the CSS selector that works in a comment at top of `src/hot_collector.py` (next task). If no selector works, fall back to searching page text with regex `(\d+)\s*comment`.

---

### Task 4: Implement `hot_collector.py`

**Files:**
- Create: `src/hot_collector.py`
- Create: `tests/test_hot_collector.py`

**Step 1: Write failing tests**

Create `tests/test_hot_collector.py`:

```python
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from src.models import Article
from src.hot_collector import collect_hot_articles, _extract_comment_count


class TestExtractCommentCount:
    def test_parses_comment_text(self):
        assert _extract_comment_count("42 comments") == 42
        assert _extract_comment_count("1 comment") == 1
        assert _extract_comment_count("Comments (108)") == 108

    def test_returns_zero_on_no_match(self):
        assert _extract_comment_count("No data") == 0
        assert _extract_comment_count("") == 0


class TestCollectHotArticles:
    @pytest.mark.asyncio
    @patch("src.hot_collector.async_playwright")
    async def test_returns_top_n_by_comment_count(self, mock_pw):
        mock_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_listing_page = AsyncMock()
        mock_article_page = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        # First call returns listing page, subsequent calls return article page
        mock_context.new_page.return_value = mock_listing_page

        # Listing page links
        async def make_link(href, text):
            link = AsyncMock()
            link.get_attribute.return_value = href
            link.inner_text.return_value = text
            return link

        links = [
            await make_link("/athletic/1/2026/02/16/arsenal-win/", "Arsenal win big"),
            await make_link("/athletic/2/2026/02/16/liverpool-draw/", "Liverpool draw with Chelsea"),
            await make_link("/athletic/3/2026/02/16/spurs-loss/", "Spurs suffer defeat"),
        ]
        mock_listing_page.query_selector_all.return_value = links

        # Mock _get_comment_count to return different counts
        with patch("src.hot_collector._get_comment_count", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [10, 50, 30]

            articles = await collect_hot_articles("http://fake", cookies=[], top_n=2)

        assert len(articles) == 2
        assert articles[0].title == "Liverpool draw with Chelsea"  # 50 comments
        assert articles[0].comment_count == 50
        assert articles[1].title == "Spurs suffer defeat"  # 30 comments
        assert articles[1].comment_count == 30

    @pytest.mark.asyncio
    @patch("src.hot_collector.async_playwright")
    async def test_returns_empty_when_no_articles(self, mock_pw):
        mock_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.query_selector_all.return_value = []

        articles = await collect_hot_articles("http://fake", cookies=[], top_n=5)
        assert articles == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_hot_collector.py -v`
Expected: FAIL — module not found.

**Step 3: Implement `src/hot_collector.py`**

```python
import logging
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright, BrowserContext

from src.collector import _is_premier_league, _ARTICLE_URL_PATTERN, _parse_date_from_url
from src.models import Article
from src.scraper import _convert_cookies

logger = logging.getLogger(__name__)

# CSS selectors to try for comment count (update after running probe script)
_COMMENT_SELECTORS = [
    "[data-testid*='comment']",
    "[class*='comment-count']",
    "[class*='CommentCount']",
    "button:has-text('comment')",
    "a:has-text('comment')",
]


def _extract_comment_count(text: str) -> int:
    """Extract comment count from text like '42 comments' or 'Comments (108)'."""
    m = re.search(r"(\d+)\s*comment", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"comment\w*\s*\(?(\d+)\)?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0


async def _get_comment_count(context: BrowserContext, url: str) -> int:
    """Open an article page and extract comment count."""
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=60000)

        for selector in _COMMENT_SELECTORS:
            els = await page.query_selector_all(selector)
            for el in els:
                text = (await el.inner_text()).strip()
                count = _extract_comment_count(text)
                if count > 0:
                    return count

        # Fallback: search full page text
        body_text = await page.inner_text("body")
        for match in re.finditer(r"(\d+)\s*comment", body_text, re.IGNORECASE):
            count = int(match.group(1))
            if count > 0:
                return count

        return 0
    finally:
        await page.close()


async def collect_hot_articles(
    page_url: str, cookies: list[dict], top_n: int = 5
) -> list[Article]:
    """Collect PL articles sorted by comment count, return top N."""
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
        candidates = []

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
            candidates.append((href, title, pub_date))

        await page.close()

        logger.info("Found %d PL article candidates, fetching comment counts...", len(candidates))

        # Fetch comment count for each candidate
        articles = []
        for href, title, pub_date in candidates:
            count = await _get_comment_count(context, href)
            logger.info("  [%d comments] %s", count, title[:60])
            articles.append(
                Article(
                    title=title,
                    link=href,
                    summary=title,
                    published=pub_date,
                    comment_count=count,
                )
            )

        await browser.close()

    # Sort by comment count descending, take top N
    articles.sort(key=lambda a: a.comment_count, reverse=True)
    result = articles[:top_n]

    logger.info("Top %d by comments:", len(result))
    for a in result:
        logger.info("  [%d comments] %s", a.comment_count, a.title[:60])

    return result
```

**Step 4: Run tests**

Run: `pytest tests/test_hot_collector.py -v`
Expected: ALL PASS.

**Step 5: Run full suite**

Run: `pytest tests/ -v`
Expected: ALL PASS.

**Step 6: Commit**

```
feat: add hot_collector for most-commented articles
```

---

### Task 5: Create `main_hot.py` pipeline entry point

**Files:**
- Create: `main_hot.py`
- Create: `tests/test_main_hot.py`

**Step 1: Write failing test**

Create `tests/test_main_hot.py`:

```python
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from src.models import Article, AnalyzedArticle


class TestHotPipeline:
    @patch("main_hot._save_step")
    @patch("main_hot.notify")
    @patch("main_hot.analyze_articles")
    @patch("main_hot.scrape_full_texts", new_callable=AsyncMock)
    @patch("main_hot.collect_hot_articles", new_callable=AsyncMock)
    @patch("main_hot.get_config")
    def test_full_pipeline(
        self, mock_config, mock_collect, mock_scrape, mock_analyze, mock_notify, mock_save
    ):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
        }

        article = Article(
            title="Test", link="http://x", summary="S",
            published=datetime(2026, 2, 16, tzinfo=timezone.utc),
            comment_count=42,
        )
        mock_collect.return_value = [article]
        mock_scrape.return_value = [article]

        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="Test", article_type="新闻",
            importance=5, overview="概述", detail="详情",
            key_people_and_data="数据", impact="影响", link="http://x",
        )
        mock_analyze.return_value = [analyzed]
        mock_notify.return_value = True

        from main_hot import run
        asyncio.run(run())

        mock_collect.assert_called_once()
        mock_scrape.assert_called_once()
        mock_analyze.assert_called_once()
        mock_notify.assert_called_once()
        # Verify title_prefix is passed
        notify_kwargs = mock_notify.call_args
        assert notify_kwargs[1]["title_prefix"] == "英超热议文章"

    @patch("main_hot._save_step")
    @patch("main_hot.notify")
    @patch("main_hot.collect_hot_articles", new_callable=AsyncMock)
    @patch("main_hot.get_config")
    def test_no_articles_sends_no_notification(
        self, mock_config, mock_collect, mock_notify, mock_save
    ):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
        }
        mock_collect.return_value = []

        from main_hot import run
        asyncio.run(run())

        mock_notify.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main_hot.py -v`
Expected: FAIL — `main_hot` not found.

**Step 3: Implement `main_hot.py`**

```python
import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import date

from src.hot_collector import collect_hot_articles
from src.scraper import scrape_full_texts
from src.analyzer import analyze_articles
from src.notifier import notify
from src.llm import LLMClient
from src.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _save_step(name: str, data, output_dir: str | None = None):
    if output_dir is None:
        output_dir = os.path.join("output", "hot", str(date.today()))
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Saved %s to %s", name, path)


async def run():
    config = get_config()

    # Step 1: Collect articles by comment count
    logger.info("Step 1: Collecting most-commented articles...")
    articles = await collect_hot_articles(
        config["page_url"], config["athletic_cookies"], top_n=config["top_n"]
    )
    if not articles:
        logger.info("No articles found. Exiting.")
        return

    logger.info("Found %d hot articles", len(articles))
    _save_step("step1_hot_collected", [asdict(a) for a in articles])

    # Step 2: Scrape full texts
    logger.info("Step 2: Scraping full texts...")
    articles = await scrape_full_texts(articles, config["athletic_cookies"])
    _save_step("step2_scraped", [
        {**asdict(a), "full_text": a.full_text[:200] + "..."} for a in articles
    ])

    # Step 3: Analyze with LLM
    llm = LLMClient(
        base_url=config["llm_base_url"],
        api_key=config["llm_api_key"],
        model=config["llm_model"],
    )
    logger.info("Step 3: Analyzing articles...")
    analyzed = analyze_articles(articles, llm)
    _save_step("step3_analyzed", [asdict(a) for a in analyzed])
    if not analyzed:
        logger.error("Analysis failed, no results to push")
        return

    # Step 4: Push to WeChat
    logger.info("Step 4: Pushing to WeChat...")
    success = notify(analyzed, config["serverchan_key"], title_prefix="英超热议文章")
    if success:
        logger.info("Hot digest sent successfully!")
    else:
        logger.error("Failed to send hot digest")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
```

**Step 4: Run tests**

Run: `pytest tests/test_main_hot.py -v`
Expected: ALL PASS.

**Step 5: Run full suite**

Run: `pytest tests/ -v`
Expected: ALL PASS.

**Step 6: Commit**

```
feat: add main_hot.py pipeline for hot comments digest
```

---

### Task 6: Add GitHub Actions job for hot digest

**Files:**
- Modify: `.github/workflows/daily.yml`

**Step 1: Add the hot-digest job**

Add a second job to `.github/workflows/daily.yml`. The full file should be:

```yaml
name: Daily Premier League Digest

on:
  schedule:
    - cron: '0 23 * * *'   # UTC 23:00 = Beijing 07:00
    - cron: '30 23 * * *'  # UTC 23:30 = Beijing 07:30
  workflow_dispatch:
    inputs:
      pipeline:
        description: 'Which pipeline to run'
        required: true
        default: 'both'
        type: choice
        options:
          - both
          - digest
          - hot

jobs:
  digest:
    runs-on: ubuntu-latest
    if: >-
      github.event_name == 'schedule' && github.event.schedule == '0 23 * * *'
      || github.event_name == 'workflow_dispatch' && (github.event.inputs.pipeline == 'both' || github.event.inputs.pipeline == 'digest')
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install Playwright browsers
        run: playwright install --with-deps chromium

      - name: Run digest pipeline
        run: python main.py
        env:
          ATHLETIC_COOKIES: ${{ secrets.ATHLETIC_COOKIES }}
          LLM_BASE_URL: ${{ vars.LLM_BASE_URL }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_MODEL: ${{ vars.LLM_MODEL }}
          SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}

  hot-digest:
    runs-on: ubuntu-latest
    if: >-
      github.event_name == 'schedule' && github.event.schedule == '30 23 * * *'
      || github.event_name == 'workflow_dispatch' && (github.event.inputs.pipeline == 'both' || github.event.inputs.pipeline == 'hot')
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install Playwright browsers
        run: playwright install --with-deps chromium

      - name: Run hot digest pipeline
        run: python main_hot.py
        env:
          ATHLETIC_COOKIES: ${{ secrets.ATHLETIC_COOKIES }}
          LLM_BASE_URL: ${{ vars.LLM_BASE_URL }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_MODEL: ${{ vars.LLM_MODEL }}
          SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}
```

**Step 2: Commit**

```
ci: add hot-digest job at UTC 23:30
```

---

### Task 7: Final verification

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS.

**Step 2: Verify file structure**

Run: `ls src/hot_collector.py main_hot.py tests/test_hot_collector.py tests/test_main_hot.py test_comment_structure.py`
Expected: All files exist.

**Step 3: Run probe script locally (optional, needs env vars)**

Run: `python test_comment_structure.py`
Update `_COMMENT_SELECTORS` in `src/hot_collector.py` based on results if needed.
