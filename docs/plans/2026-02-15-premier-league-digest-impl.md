# Premier League Daily Digest - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an automated daily pipeline that collects Premier League news via RSS, ranks articles with AI, scrapes top 5 full texts, generates detailed Chinese analysis, and pushes to WeChat.

**Architecture:** 5-stage pipeline (Collector → Ranker → Scraper → Analyzer → Notifier) orchestrated by `main.py`, scheduled via GitHub Actions cron. RSS for discovery, Playwright for on-demand full-text scraping, LLM for ranking and analysis, Server酱 for WeChat push.

**Tech Stack:** Python 3.12, httpx, feedparser, playwright, Server酱 API. LLM provider abstracted (claude/openai/deepseek).

**Design doc:** `docs/plans/2026-02-15-premier-league-digest-design.md`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `src/__init__.py`
- Create: `src/models.py`
- Create: `src/config.py`
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create requirements.txt**

```
httpx>=0.27,<1
feedparser>=6.0,<7
playwright>=1.49,<2
pytest>=8.0,<9
pytest-asyncio>=0.24,<1
respx>=0.22,<1
```

**Step 2: Create data models (`src/models.py`)**

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    title: str
    link: str
    summary: str
    published: datetime
    full_text: str = ""


@dataclass
class AnalyzedArticle:
    title_cn: str
    title_original: str
    article_type: str
    importance: int
    overview: str
    detail: str
    key_people_and_data: str
    impact: str
    link: str
```

**Step 3: Create config (`src/config.py`)**

```python
import json
import os


def get_config():
    return {
        "rss_url": os.environ.get(
            "RSS_URL", "https://www.nytimes.com/athletic/rss/news/"
        ),
        "athletic_cookies": json.loads(os.environ.get("ATHLETIC_COOKIES", "[]")),
        "llm_provider": os.environ.get("LLM_PROVIDER", "claude"),
        "llm_api_key": os.environ.get("LLM_API_KEY", ""),
        "serverchan_key": os.environ.get("SERVERCHAN_KEY", ""),
        "top_n": int(os.environ.get("TOP_N", "5")),
    }
```

**Step 4: Create `src/__init__.py`, `tests/__init__.py`, `tests/conftest.py`**

`src/__init__.py` and `tests/__init__.py`: empty files.

`tests/conftest.py`:
```python
import pytest
```

**Step 5: Install dependencies and verify**

Run: `cd /Users/linbing/Project/github/TAnews && pip install -r requirements.txt`
Expected: All packages install successfully.

Run: `python -c "from src.models import Article, AnalyzedArticle; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add src/ tests/ requirements.txt
git commit -m "feat: project scaffolding with models, config, and dependencies"
```

---

### Task 2: LLM Abstraction Layer

**Files:**
- Create: `src/llm.py`
- Create: `tests/test_llm.py`

**Step 1: Write the failing test**

`tests/test_llm.py`:
```python
import os
from unittest.mock import patch, MagicMock

from src.llm import create_llm_client, LLMClient


class TestCreateLLMClient:
    def test_creates_claude_client(self):
        client = create_llm_client("claude", "test-key")
        assert isinstance(client, LLMClient)

    def test_creates_openai_client(self):
        client = create_llm_client("openai", "test-key")
        assert isinstance(client, LLMClient)

    def test_creates_deepseek_client(self):
        client = create_llm_client("deepseek", "test-key")
        assert isinstance(client, LLMClient)

    def test_unknown_provider_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm_client("unknown", "test-key")


class TestLLMClientComplete:
    @patch("httpx.post")
    def test_claude_complete(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "response text"}]
        }
        mock_post.return_value = mock_response

        client = create_llm_client("claude", "test-key")
        result = client.complete("system prompt", "user message")

        assert result == "response text"
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_openai_complete(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response text"}}]
        }
        mock_post.return_value = mock_response

        client = create_llm_client("openai", "test-key")
        result = client.complete("system prompt", "user message")

        assert result == "response text"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL (import errors)

**Step 3: Write implementation**

`src/llm.py`:
```python
from dataclasses import dataclass

import httpx


@dataclass
class LLMClient:
    provider: str
    api_key: str
    base_url: str
    model: str

    def complete(self, system: str, user: str) -> str:
        if self.provider == "claude":
            return self._claude_complete(system, user)
        return self._openai_compatible_complete(system, user)

    def _claude_complete(self, system: str, user: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 4096,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    def _openai_compatible_complete(self, system: str, user: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


_PROVIDERS = {
    "claude": ("https://api.anthropic.com", "claude-sonnet-4-5-20250929"),
    "openai": ("https://api.openai.com", "gpt-4o"),
    "deepseek": ("https://api.deepseek.com", "deepseek-chat"),
}


def create_llm_client(provider: str, api_key: str) -> LLMClient:
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider}")
    base_url, model = _PROVIDERS[provider]
    return LLMClient(provider=provider, api_key=api_key, base_url=base_url, model=model)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/llm.py tests/test_llm.py
git commit -m "feat: add LLM abstraction layer with claude/openai/deepseek support"
```

---

### Task 3: Collector (RSS Fetch and Filter)

**Files:**
- Create: `src/collector.py`
- Create: `tests/test_collector.py`
- Create: `tests/fixtures/sample_rss.xml`

**Step 1: Create RSS fixture**

`tests/fixtures/sample_rss.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The Athletic</title>
    <item>
      <title>Premier League title race: How Arsenal's midfield evolution changes everything</title>
      <link>https://www.nytimes.com/athletic/12345/premier-league-title-race/</link>
      <description>Arsenal's tactical shift in midfield has created a new dynamic in the title race.</description>
      <pubDate>Sun, 15 Feb 2026 06:00:00 GMT</pubDate>
    </item>
    <item>
      <title>NBA Playoffs: Lakers dominate Game 3</title>
      <link>https://www.nytimes.com/athletic/99999/nba-lakers/</link>
      <description>The Lakers took a commanding lead in the series.</description>
      <pubDate>Sun, 15 Feb 2026 05:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Manchester United transfer: New signing imminent</title>
      <link>https://www.nytimes.com/athletic/12346/man-utd-transfer/</link>
      <description>United are close to completing a deal for a new midfielder.</description>
      <pubDate>Sat, 14 Feb 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Premier League old article from last week</title>
      <link>https://www.nytimes.com/athletic/11111/old-article/</link>
      <description>This article is from last week.</description>
      <pubDate>Sun, 08 Feb 2026 06:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
```

**Step 2: Write the failing test**

`tests/test_collector.py`:
```python
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.collector import collect_articles
from src.models import Article


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_rss.xml"


class TestCollectArticles:
    @patch("src.collector.httpx.get")
    def test_filters_premier_league_articles(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = FIXTURE_PATH.read_text()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        articles = collect_articles("http://fake-rss", now=now)

        # Should include 2 Premier League articles from last 24h, exclude NBA and old article
        titles = [a.title for a in articles]
        assert len(articles) == 2
        assert any("Arsenal" in t for t in titles)
        assert any("Manchester United" in t for t in titles)
        assert not any("NBA" in t or "Lakers" in t for t in titles)
        assert not any("old article" in t for t in titles)

    @patch("src.collector.httpx.get")
    def test_returns_empty_on_no_matches(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = """<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>NBA news</title><link>http://x</link>
        <description>Basketball</description><pubDate>Sun, 15 Feb 2026 06:00:00 GMT</pubDate>
        </item></channel></rss>"""
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        articles = collect_articles("http://fake-rss", now=now)
        assert articles == []
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_collector.py -v`
Expected: FAIL (import error)

**Step 4: Write implementation**

`src/collector.py`:
```python
import logging
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from src.models import Article

logger = logging.getLogger(__name__)

_PL_KEYWORDS = [
    "premier league",
    "arsenal", "aston villa", "bournemouth", "brentford", "brighton",
    "chelsea", "crystal palace", "everton", "fulham", "ipswich",
    "leicester", "liverpool", "manchester city", "manchester united",
    "man city", "man utd", "newcastle", "nottingham forest",
    "southampton", "tottenham", "spurs", "west ham", "wolves",
]


def _is_premier_league(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in _PL_KEYWORDS)


def collect_articles(
    rss_url: str, now: datetime | None = None, hours: int = 24
) -> list[Article]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    resp = httpx.get(rss_url, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    articles = []

    for entry in feed.entries:
        try:
            published = parsedate_to_datetime(entry.get("published", ""))
        except Exception:
            continue

        if published < cutoff:
            continue

        title = entry.get("title", "")
        summary = entry.get("description", entry.get("summary", ""))

        if not _is_premier_league(title, summary):
            continue

        articles.append(
            Article(
                title=title,
                link=entry.get("link", ""),
                summary=summary,
                published=published,
            )
        )

    logger.info("Collected %d Premier League articles from RSS", len(articles))
    return articles
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_collector.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/collector.py tests/test_collector.py tests/fixtures/
git commit -m "feat: add RSS collector with Premier League filtering"
```

---

### Task 4: Ranker (LLM-based Article Ranking)

**Files:**
- Create: `src/ranker.py`
- Create: `tests/test_ranker.py`

**Step 1: Write the failing test**

`tests/test_ranker.py`:
```python
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.models import Article
from src.ranker import rank_articles


def _make_articles(n: int) -> list[Article]:
    return [
        Article(
            title=f"Article {i}",
            link=f"https://example.com/{i}",
            summary=f"Summary of article {i}",
            published=datetime(2026, 2, 15, i, 0, 0, tzinfo=timezone.utc),
        )
        for i in range(n)
    ]


class TestRankArticles:
    def test_returns_top_n(self):
        mock_llm = MagicMock()
        # LLM returns indices of top 3 articles
        mock_llm.complete.return_value = "2,0,4"
        articles = _make_articles(6)

        result = rank_articles(articles, mock_llm, top_n=3)

        assert len(result) == 3
        assert result[0].title == "Article 2"
        assert result[1].title == "Article 0"
        assert result[2].title == "Article 4"

    def test_fewer_than_top_n_returns_all(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "1,0"
        articles = _make_articles(2)

        result = rank_articles(articles, mock_llm, top_n=5)

        assert len(result) == 2

    def test_skips_llm_when_articles_lte_top_n(self):
        mock_llm = MagicMock()
        articles = _make_articles(3)

        result = rank_articles(articles, mock_llm, top_n=5)

        assert len(result) == 3
        mock_llm.complete.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ranker.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/ranker.py`:
```python
import logging
import re

from src.llm import LLMClient
from src.models import Article

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a Premier League football news editor.
Given a list of articles with their titles and summaries, select the {top_n} most important ones.

Criteria for importance:
- Major match results and their implications
- Transfer news with credible sources
- Tactical/strategic analysis with depth
- Injury updates for key players
- Title race / relegation battle impact

Return ONLY a comma-separated list of article indices (0-based), ordered by importance (most important first).
Example: 3,1,7,0,5"""


def rank_articles(
    articles: list[Article], llm: LLMClient, top_n: int = 5
) -> list[Article]:
    if len(articles) <= top_n:
        return articles

    article_list = "\n".join(
        f"[{i}] {a.title}\n    {a.summary}" for i, a in enumerate(articles)
    )

    response = llm.complete(
        _SYSTEM_PROMPT.format(top_n=top_n),
        f"Select the top {top_n} from these articles:\n\n{article_list}",
    )

    indices = _parse_indices(response, len(articles), top_n)
    result = [articles[i] for i in indices]
    logger.info("Ranked %d articles, selected top %d", len(articles), len(result))
    return result


def _parse_indices(response: str, total: int, top_n: int) -> list[int]:
    numbers = re.findall(r"\d+", response)
    seen = set()
    indices = []
    for n in numbers:
        idx = int(n)
        if 0 <= idx < total and idx not in seen:
            seen.add(idx)
            indices.append(idx)
        if len(indices) >= top_n:
            break
    return indices
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_ranker.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ranker.py tests/test_ranker.py
git commit -m "feat: add LLM-based article ranker"
```

---

### Task 5: Scraper (Playwright Full-text Extraction)

**Files:**
- Create: `src/scraper.py`
- Create: `tests/test_scraper.py`

**Step 1: Write the failing test**

`tests/test_scraper.py`:
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.models import Article
from src.scraper import scrape_full_texts


def _make_article(title="Test", link="https://example.com/1") -> Article:
    return Article(
        title=title,
        link=link,
        summary="A summary",
        published=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )


class TestScrapeFullTexts:
    @pytest.mark.asyncio
    @patch("src.scraper._scrape_one")
    async def test_populates_full_text(self, mock_scrape_one):
        mock_scrape_one.return_value = "Full article content here."
        articles = [_make_article()]

        result = await scrape_full_texts(articles, cookies=[])

        assert result[0].full_text == "Full article content here."
        mock_scrape_one.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.scraper._scrape_one")
    async def test_falls_back_to_summary_on_failure(self, mock_scrape_one):
        mock_scrape_one.side_effect = Exception("Cookie expired")
        articles = [_make_article()]

        result = await scrape_full_texts(articles, cookies=[])

        assert result[0].full_text == articles[0].summary
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/scraper.py`:
```python
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
            if not text or len(text) < 100:
                logger.warning("Short/empty text for %s, using summary", article.link)
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

        # The Athletic article body is in <article> or main content area
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scraper.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "feat: add Playwright scraper with cookie auth and fallback"
```

---

### Task 6: Analyzer (LLM Deep Analysis)

**Files:**
- Create: `src/analyzer.py`
- Create: `tests/test_analyzer.py`

**Step 1: Write the failing test**

`tests/test_analyzer.py`:
```python
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.models import Article, AnalyzedArticle
from src.analyzer import analyze_articles


def _make_article(title="Arsenal dominate", full_text="Full analysis...") -> Article:
    return Article(
        title=title,
        link="https://example.com/1",
        summary="Summary",
        published=datetime(2026, 2, 15, tzinfo=timezone.utc),
        full_text=full_text,
    )


class TestAnalyzeArticles:
    def test_returns_analyzed_articles(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps([
            {
                "title_cn": "阿森纳主导比赛",
                "title_original": "Arsenal dominate",
                "article_type": "深度分析",
                "importance": 5,
                "overview": "阿森纳在比赛中展现了统治力。",
                "detail": "详细的战术分析内容...",
                "key_people_and_data": "萨卡：2球1助攻",
                "impact": "阿森纳升至榜首。",
                "link": "https://example.com/1",
            }
        ])

        articles = [_make_article()]
        result = analyze_articles(articles, mock_llm)

        assert len(result) == 1
        assert result[0].title_cn == "阿森纳主导比赛"
        assert result[0].importance == 5

    def test_handles_malformed_llm_response(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "This is not JSON"

        articles = [_make_article()]
        result = analyze_articles(articles, mock_llm)

        # Should return empty list on parse failure
        assert result == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_analyzer.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/analyzer.py`:
```python
import json
import logging

from src.llm import LLMClient
from src.models import Article, AnalyzedArticle

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是一位资深英超足球记者和分析师。请对以下英超文章进行深度中文分析。

对每篇文章，返回一个 JSON 数组，每个元素包含：
- title_cn: 中文标题翻译
- title_original: 英文原标题
- article_type: 文章类型（深度分析/新闻报道/战术解读/转会动态/赛后分析）
- importance: 重要性 1-5
- overview: 2-3 句话概述核心论点（中文）
- detail: 详细转述文章关键论据和分析逻辑，保留数据、引用、战术细节。深度分析类 300-500 字，普通新闻 150-200 字（中文）
- key_people_and_data: 涉及的关键人物和数据（中文）
- impact: 影响分析与展望（中文）
- link: 原文链接

仅返回 JSON 数组，不要添加任何其他文字。"""


def analyze_articles(
    articles: list[Article], llm: LLMClient
) -> list[AnalyzedArticle]:
    article_texts = "\n\n---\n\n".join(
        f"Title: {a.title}\nLink: {a.link}\nContent:\n{a.full_text}"
        for a in articles
    )

    response = llm.complete(_SYSTEM_PROMPT, article_texts)

    try:
        # Strip markdown code fences if present
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        data = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.error("Failed to parse LLM response as JSON: %s", response[:200])
        return []

    result = []
    for item in data:
        try:
            result.append(
                AnalyzedArticle(
                    title_cn=item["title_cn"],
                    title_original=item["title_original"],
                    article_type=item["article_type"],
                    importance=item["importance"],
                    overview=item["overview"],
                    detail=item["detail"],
                    key_people_and_data=item["key_people_and_data"],
                    impact=item["impact"],
                    link=item["link"],
                )
            )
        except KeyError as e:
            logger.warning("Skipping article with missing field: %s", e)

    return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_analyzer.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/analyzer.py tests/test_analyzer.py
git commit -m "feat: add LLM analyzer for deep Chinese article analysis"
```

---

### Task 7: Notifier (Server酱 Push)

**Files:**
- Create: `src/notifier.py`
- Create: `tests/test_notifier.py`

**Step 1: Write the failing test**

`tests/test_notifier.py`:
```python
from unittest.mock import patch, MagicMock
from datetime import date

from src.models import AnalyzedArticle
from src.notifier import notify, format_digest


def _make_analyzed() -> AnalyzedArticle:
    return AnalyzedArticle(
        title_cn="阿森纳争冠分析",
        title_original="Arsenal title race analysis",
        article_type="深度分析",
        importance=5,
        overview="阿森纳在本赛季展现了强大的争冠实力。",
        detail="详细的战术分析...",
        key_people_and_data="萨卡、厄德高",
        impact="对争冠形势产生重大影响。",
        link="https://example.com/1",
    )


class TestFormatDigest:
    def test_formats_markdown(self):
        articles = [_make_analyzed()]
        title, body = format_digest(articles, date(2026, 2, 15))

        assert "英超每日精选" in title
        assert "2026-02-15" in title
        assert "阿森纳争冠分析" in body
        assert "深度分析" in body
        assert "⭐⭐⭐⭐⭐" in body


class TestNotify:
    @patch("src.notifier.httpx.post")
    def test_sends_to_serverchan(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "message": "success"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        articles = [_make_analyzed()]
        result = notify(articles, "test-key")

        assert result is True
        mock_post.assert_called_once()
        call_data = mock_post.call_args
        assert "test-key" in call_data[0][0]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_notifier.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/notifier.py`:
```python
import logging
from datetime import date

import httpx

from src.models import AnalyzedArticle

logger = logging.getLogger(__name__)

_STARS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}


def format_digest(
    articles: list[AnalyzedArticle], today: date | None = None
) -> tuple[str, str]:
    today = today or date.today()
    title = f"英超每日精选 - {today}"

    sections = []
    for i, a in enumerate(articles, 1):
        stars = _STARS.get(a.importance, "⭐" * a.importance)
        section = f"""## {i}. {a.title_cn}
**原标题：** {a.title_original}
**类型：** {a.article_type}
**重要性：** {stars}

### 文章概述
{a.overview}

### 详细内容
{a.detail}

### 关键人物与数据
{a.key_people_and_data}

### 影响与展望
{a.impact}

🔗 [阅读原文]({a.link})"""
        sections.append(section)

    body = f"# ⚽ {title}\n\n" + "\n\n---\n\n".join(sections)
    return title, body


def notify(
    articles: list[AnalyzedArticle],
    serverchan_key: str,
    today: date | None = None,
) -> bool:
    title, body = format_digest(articles, today)

    url = f"https://sctapi.ftqq.com/{serverchan_key}.send"
    resp = httpx.post(url, data={"title": title, "desp": body}, timeout=30)
    resp.raise_for_status()

    result = resp.json()
    if result.get("code") == 0:
        logger.info("Push notification sent successfully")
        return True

    logger.error("Server酱 push failed: %s", result)
    return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_notifier.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat: add Server酱 notifier with Markdown formatting"
```

---

### Task 8: Main Pipeline Orchestration

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

**Step 1: Write the failing test**

`tests/test_main.py`:
```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from src.models import Article, AnalyzedArticle


class TestMainPipeline:
    @patch("main.notify")
    @patch("main.analyze_articles")
    @patch("main.scrape_full_texts", new_callable=AsyncMock)
    @patch("main.rank_articles")
    @patch("main.collect_articles")
    @patch("main.get_config")
    def test_full_pipeline(
        self, mock_config, mock_collect, mock_rank, mock_scrape, mock_analyze, mock_notify
    ):
        mock_config.return_value = {
            "rss_url": "http://rss",
            "athletic_cookies": [],
            "llm_provider": "claude",
            "llm_api_key": "key",
            "serverchan_key": "sc-key",
            "top_n": 5,
        }

        article = Article(
            title="Test", link="http://x", summary="S",
            published=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        mock_collect.return_value = [article]
        mock_rank.return_value = [article]
        mock_scrape.return_value = [article]

        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="Test", article_type="新闻",
            importance=5, overview="概述", detail="详情",
            key_people_and_data="数据", impact="影响", link="http://x",
        )
        mock_analyze.return_value = [analyzed]
        mock_notify.return_value = True

        from main import run
        import asyncio
        asyncio.run(run())

        mock_collect.assert_called_once()
        mock_rank.assert_called_once()
        mock_scrape.assert_called_once()
        mock_analyze.assert_called_once()
        mock_notify.assert_called_once()

    @patch("main.notify")
    @patch("main.collect_articles")
    @patch("main.get_config")
    def test_no_articles_sends_no_notification(self, mock_config, mock_collect, mock_notify):
        mock_config.return_value = {
            "rss_url": "http://rss",
            "athletic_cookies": [],
            "llm_provider": "claude",
            "llm_api_key": "key",
            "serverchan_key": "sc-key",
            "top_n": 5,
        }
        mock_collect.return_value = []

        from main import run
        import asyncio
        asyncio.run(run())

        mock_notify.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL

**Step 3: Write implementation**

`main.py`:
```python
import asyncio
import logging
import sys

from src.collector import collect_articles
from src.ranker import rank_articles
from src.scraper import scrape_full_texts
from src.analyzer import analyze_articles
from src.notifier import notify
from src.llm import create_llm_client
from src.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run():
    config = get_config()

    # Step 1: Collect articles from RSS
    logger.info("Step 1: Collecting articles from RSS...")
    articles = collect_articles(config["rss_url"])
    if not articles:
        logger.info("No Premier League articles found. Exiting.")
        return

    logger.info("Found %d articles", len(articles))

    # Step 2: Rank and select top N
    llm = create_llm_client(config["llm_provider"], config["llm_api_key"])
    logger.info("Step 2: Ranking articles...")
    top_articles = rank_articles(articles, llm, top_n=config["top_n"])
    logger.info("Selected top %d articles", len(top_articles))

    # Step 3: Scrape full texts
    logger.info("Step 3: Scraping full texts...")
    top_articles = await scrape_full_texts(top_articles, config["athletic_cookies"])

    # Step 4: Analyze with LLM
    logger.info("Step 4: Analyzing articles...")
    analyzed = analyze_articles(top_articles, llm)
    if not analyzed:
        logger.error("Analysis failed, no results to push")
        return

    # Step 5: Push to WeChat
    logger.info("Step 5: Pushing to WeChat...")
    success = notify(analyzed, config["serverchan_key"])
    if success:
        logger.info("Daily digest sent successfully!")
    else:
        logger.error("Failed to send digest")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add main pipeline orchestration"
```

---

### Task 9: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/daily.yml`

**Step 1: Write workflow file**

`.github/workflows/daily.yml`:
```yaml
name: Daily Premier League Digest

on:
  schedule:
    - cron: '0 23 * * *'  # UTC 23:00 = Beijing 07:00
  workflow_dispatch: {}

jobs:
  digest:
    runs-on: ubuntu-latest
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
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_PROVIDER: ${{ vars.LLM_PROVIDER }}
          SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}
```

**Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml'))" 2>/dev/null || python -c "print('Install pyyaml to validate')" `

**Step 3: Commit**

```bash
git add .github/workflows/daily.yml
git commit -m "ci: add GitHub Actions daily cron workflow"
```

---

### Task 10: Run Full Test Suite and Final Verification

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 2: Verify project structure is correct**

Run: `find . -type f -not -path './.git/*' | sort`
Expected output should match the project structure from the design doc.

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```
