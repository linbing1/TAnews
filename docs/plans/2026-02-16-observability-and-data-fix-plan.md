# Observability & Data Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add pipeline observability (logging + JSON file output) and fix data loss in collector/ranker so news quality can be diagnosed and improved.

**Architecture:** Enhance collector to parse real publish dates from URLs and extract summaries from parent elements. Enrich ranker prompt with time and summary context. Add detailed logging at every pipeline step. Save intermediate results as JSON files in `output/YYYY-MM-DD/`.

**Tech Stack:** Python 3.12, Playwright, pytest, pytest-asyncio

---

### Task 1: Collector — parse real publish date from URL

**Files:**
- Modify: `src/collector.py:22` (regex), `src/collector.py:49-75` (article construction)
- Test: `tests/test_collector.py`

**Step 1: Write failing test for date parsing**

Add to `tests/test_collector.py`:

```python
from src.collector import _parse_date_from_url

class TestParseDateFromUrl:
    def test_extracts_date(self):
        url = "/athletic/123/2026/02/15/arsenal-win/"
        result = _parse_date_from_url(url)
        assert result == datetime(2026, 2, 15, tzinfo=timezone.utc)

    def test_returns_none_for_no_date(self):
        url = "/athletic/news/"
        result = _parse_date_from_url(url)
        assert result is None
```

Add missing imports at top: `from datetime import datetime, timezone`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector.py::TestParseDateFromUrl -v`
Expected: FAIL — `_parse_date_from_url` not importable.

**Step 3: Implement `_parse_date_from_url` in `src/collector.py`**

Update the regex to use capturing groups and add the helper:

```python
_ARTICLE_URL_PATTERN = re.compile(r"/athletic/\d+/(\d{4})/(\d{2})/(\d{2})/")

def _parse_date_from_url(url: str) -> datetime | None:
    m = _ARTICLE_URL_PATTERN.search(url)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return datetime(y, mo, d, tzinfo=timezone.utc)
```

Then update the article construction in `collect_articles` (around line 68-75). Replace:

```python
            articles.append(
                Article(
                    title=title,
                    link=href,
                    summary=title,
                    published=datetime.now(timezone.utc),
                )
            )
```

With:

```python
            pub_date = _parse_date_from_url(href) or datetime.now(timezone.utc)

            articles.append(
                Article(
                    title=title,
                    link=href,
                    summary=title,
                    published=pub_date,
                )
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_collector.py -v`
Expected: ALL PASS (new tests + existing tests).

**Step 5: Commit**

```
feat: parse real publish date from article URL
```

---

### Task 2: Collector — extract summary from parent element

**Files:**
- Modify: `src/collector.py:48-76` (article loop body)
- Test: `tests/test_collector.py`

**Step 1: Write failing test for summary extraction**

Add to `tests/test_collector.py::TestCollectArticles`:

```python
    @pytest.mark.asyncio
    @patch("src.collector.async_playwright")
    async def test_extracts_summary_from_parent(self, mock_pw):
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_instance = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # Simulate a link element whose parent has extra text
        link = AsyncMock()
        link.get_attribute.return_value = "/athletic/123/2026/02/15/arsenal-win/"
        link.inner_text.return_value = "Arsenal dominate in 3-0 victory"

        parent = AsyncMock()
        parent.inner_text.return_value = "Arsenal dominate in 3-0 victory\nSaka scores twice as Gunners go top"
        link.evaluate_handle.return_value = parent

        mock_page.query_selector_all.return_value = [link]

        articles = await collect_articles("http://fake-url", cookies=[])

        assert len(articles) == 1
        assert articles[0].summary == "Saka scores twice as Gunners go top"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_collector.py::TestCollectArticles::test_extracts_summary_from_parent -v`
Expected: FAIL — summary will equal title (current behavior).

**Step 3: Implement summary extraction**

In `collect_articles`, after extracting title (around line 61), add summary extraction logic:

```python
            # Try to extract summary from parent element
            summary = title
            try:
                parent = await link.evaluate_handle("el => el.parentElement")
                parent_text = (await parent.inner_text()).strip()
                # Parent text often contains title + extra text; extract the extra
                lines = [l.strip() for l in parent_text.split("\n") if l.strip()]
                extra = [l for l in lines if l != title and len(l) > 15]
                if extra:
                    summary = extra[0]
            except Exception:
                pass
```

Then update the Article construction to use `summary` variable instead of `title`:

```python
            articles.append(
                Article(
                    title=title,
                    link=href,
                    summary=summary,
                    published=pub_date,
                )
            )
```

**Step 4: Run all tests**

Run: `pytest tests/test_collector.py -v`
Expected: ALL PASS.

**Step 5: Commit**

```
feat: extract article summary from parent element
```

---

### Task 3: Collector — add detailed logging

**Files:**
- Modify: `src/collector.py` (add logging lines in `collect_articles`)

**Step 1: Add logging to `collect_articles`**

After the article loop completes and before `await browser.close()`, add:

```python
        for a in articles:
            logger.info("  [%s] %s", a.published.strftime("%Y-%m-%d"), a.title)
            logger.debug("    link=%s summary=%s", a.link, a.summary)
```

No new test needed — this is logging-only.

**Step 2: Run existing tests to verify nothing breaks**

Run: `pytest tests/test_collector.py -v`
Expected: ALL PASS.

**Step 3: Commit**

```
feat: add detailed logging to collector
```

---

### Task 4: Ranker — enhance prompt with time context and summary

**Files:**
- Modify: `src/ranker.py:9-20` (system prompt), `src/ranker.py:29-31` (article formatting)
- Test: `tests/test_ranker.py`

**Step 1: Write test that verifies time and summary are sent to LLM**

Add to `tests/test_ranker.py`:

```python
    def test_sends_date_and_summary_to_llm(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "0,1"
        articles = [
            Article(
                title="Arsenal win",
                link="https://example.com/1",
                summary="Saka scores twice in dominant display",
                published=datetime(2026, 2, 16, 10, 0, 0, tzinfo=timezone.utc),
            ),
            Article(
                title="Liverpool draw",
                link="https://example.com/2",
                summary="Liverpool draw",
                published=datetime(2026, 2, 15, 8, 0, 0, tzinfo=timezone.utc),
            ),
        ]
        rank_articles(articles, mock_llm, top_n=2)

        call_args = mock_llm.complete.call_args
        user_prompt = call_args[0][1]
        # Date should appear in the prompt
        assert "2026-02-16" in user_prompt
        # Non-duplicate summary should appear
        assert "Saka scores twice" in user_prompt
```

Add missing import: `from src.models import Article`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ranker.py::TestRankArticles::test_sends_date_and_summary_to_llm -v`
Expected: FAIL — current prompt does not contain date.

**Step 3: Update ranker prompt and article formatting**

In `src/ranker.py`, update `_SYSTEM_PROMPT`:

```python
_SYSTEM_PROMPT = """You are a Premier League football news editor.
Given a list of articles with their titles, summaries, and publish dates, select the {top_n} most important ones.

Criteria for importance:
- Freshness: strongly prefer articles published in the last 24 hours
- Major match results and their implications
- Transfer news with credible sources
- Tactical/strategic analysis with depth
- Injury updates for key players
- Title race / relegation battle impact

Return ONLY a comma-separated list of article indices (0-based), ordered by importance (most important first).
Example: 3,1,7,0,5"""
```

Update the article formatting in `rank_articles`:

```python
    article_list = "\n".join(
        f"[{i}] ({a.published.strftime('%Y-%m-%d')}) {a.title}"
        + (f"\n    {a.summary}" if a.summary != a.title else "")
        for i, a in enumerate(articles)
    )
```

**Step 4: Add logging**

After `result = [articles[i] for i in indices]`, add:

```python
    logger.debug("Ranker LLM prompt:\n%s", article_list)
    logger.debug("Ranker LLM response: %s", response)
    for a in result:
        logger.info("  Selected: [%s] %s", a.published.strftime("%Y-%m-%d"), a.title)
```

**Step 5: Run all tests**

Run: `pytest tests/test_ranker.py -v`
Expected: ALL PASS.

**Step 6: Commit**

```
feat: enhance ranker with time context, summary, and logging
```

---

### Task 5: Scraper & Analyzer — add logging

**Files:**
- Modify: `src/scraper.py:38-56` (scrape loop)
- Modify: `src/analyzer.py:27-64` (analyze function)

**Step 1: Add logging to scraper**

In `scrape_full_texts`, after setting `article.full_text`, add:

```python
                logger.info("  Scraped %s: %d chars", article.title[:50], len(text))
```

In the fallback paths (empty text and exception), the existing `logger.warning` lines are sufficient.

**Step 2: Add logging to analyzer**

In `analyze_articles`, after the LLM call (line 33), add:

```python
    logger.debug("Analyzer LLM response:\n%s", response[:500])
```

After building the result list, add:

```python
    logger.info("Analyzed %d articles successfully", len(result))
```

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS.

**Step 4: Commit**

```
feat: add logging to scraper and analyzer
```

---

### Task 6: Pipeline — intermediate JSON output

**Files:**
- Modify: `main.py`
- Modify: `.gitignore`
- Test: `tests/test_main.py`

**Step 1: Write test for `_save_step` helper**

Add to `tests/test_main.py`:

```python
import json
import os
from datetime import date
from main import _save_step

class TestSaveStep:
    def test_creates_output_dir_and_file(self, tmp_path):
        data = [{"title": "Test"}]
        _save_step("step1_collected", data, output_dir=str(tmp_path))
        path = tmp_path / "step1_collected.json"
        assert path.exists()
        assert json.loads(path.read_text()) == data
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py::TestSaveStep -v`
Expected: FAIL — `_save_step` not importable.

**Step 3: Implement `_save_step` and add calls to `run()`**

At the top of `main.py`, add:

```python
import json
import os
from dataclasses import asdict
from datetime import date
```

Add the helper function before `async def run()`:

```python
def _save_step(name: str, data, output_dir: str | None = None):
    if output_dir is None:
        output_dir = os.path.join("output", str(date.today()))
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Saved %s to %s", name, path)
```

In `run()`, add after each step:

After Step 1 (`articles = await collect_articles(...)`):
```python
    _save_step("step1_collected", [asdict(a) for a in articles])
```

After Step 2 (`top_articles = rank_articles(...)`):
```python
    _save_step("step2_ranked", [asdict(a) for a in top_articles])
```

After Step 3 (`top_articles = await scrape_full_texts(...)`):
```python
    _save_step("step3_scraped", [
        {**asdict(a), "full_text": a.full_text[:200] + "..."} for a in top_articles
    ])
```

After Step 4 (`analyzed = analyze_articles(...)`):
```python
    _save_step("step4_analyzed", [asdict(a) for a in analyzed])
```

**Step 4: Update `.gitignore`**

Add `output/` to `.gitignore`.

**Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS. The existing `test_full_pipeline` may need `_save_step` patched — if it fails, add `@patch("main._save_step")` to the existing test methods in `TestMainPipeline`.

**Step 6: Commit**

```
feat: save intermediate pipeline results to output/ JSON files
```

---

### Task 7: Final verification

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS.

**Step 2: Verify locally with `--log-cli-level=DEBUG` (optional, no env vars needed)**

Run: `pytest tests/ -v --log-cli-level=DEBUG`
Expected: See debug log output from ranker and analyzer.

**Step 3: Commit any final fixes if needed**
