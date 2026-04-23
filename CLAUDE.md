# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TAnews is an automated Premier League Daily Digest pipeline that scrapes The Athletic, uses LLM to select/rank top articles, performs deep Chinese analysis, and pushes formatted digests to WeChat via Server酱.

**Digest pipeline:** Collector → Ranker (LLM top-N selection) → Scraper → Analyzer (LLM Chinese analysis) → Audio Scripter (optional) → Audio Synth (optional) → Notifier

**Hot pipeline (`main_hot.py`):** Collector (with comment counts) → sort by comment count → Scraper → Analyzer → Audio Scripter (optional) → Audio Synth (optional) → Notifier. Skips LLM ranking entirely.

## Commands

```bash
# Setup
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium

# Run pipelines (requires env vars)
python main.py        # daily digest
python main_hot.py    # hot discussion digest

# Tests
pytest tests/ -v
pytest tests/test_collector.py          # single file
pytest tests/test_collector.py -k test_name  # single test
```

## Architecture

```
main.py              # Digest pipeline: collect → rank → scrape → analyze → optional audio → notify
main_hot.py          # Hot pipeline: collect (sorted by comments) → scrape → analyze → optional audio → notify
src/
  config.py          # Loads env vars into config dict (no Pydantic)
  models.py          # Dataclasses: Article, AnalyzedArticle
  collector.py       # Playwright scrapes listing page; filters by 24 PL keywords; extracts comment counts
  ranker.py          # LLM selects top N; skips LLM if articles ≤ top_n
  scraper.py         # Playwright + cookies; 4-selector fallback chain; returns (articles, has_fallbacks)
  analyzer.py        # LLM deep Chinese analysis per article; returns structured JSON
  audio_scripter.py  # LLM turns analyzed digest items into a spoken Chinese script
  audio_synth.py     # Edge-TTS synth + GitHub Release upload/retention for MP3 output
  llm.py             # OpenAI-compatible client; 3 retries on transient network errors
  notifier.py        # Formats Markdown digest; appends cookie warning if has_fallbacks
tests/               # pytest + pytest-asyncio; Playwright/LLM/HTTP mocked via AsyncMock
output/{date}/       # Intermediate JSON snapshots saved per step for debugging
```

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ATHLETIC_COOKIES` | Yes | `[]` | JSON array of browser cookies (Cookie-Editor export format) |
| `LLM_API_KEY` | Yes | - | LLM API key |
| `SERVERCHAN_KEY` | Yes | - | Server酱 SendKey for WeChat |
| `LLM_BASE_URL` | No | `https://open.bigmodel.cn/api/coding/paas/v4` | LLM endpoint (智谱 default) |
| `LLM_MODEL` | No | `deepseek-chat` | Model name |
| `PAGE_URL` | No | `https://www.nytimes.com/athletic/football/premier-league/` | Listing page URL |
| `TOP_N` | No | `5` | Number of articles to select |
| `AUDIO_ENABLED` | No | `true` | Toggle optional audio script/synthesis branch |
| `AUDIO_VOICE` | No | `zh-CN-YunjianNeural` | Edge-TTS voice used for MP3 generation |
| `AUDIO_KEEP_RELEASES` | No | `7` | Number of most recent audio GitHub Releases to retain per pipeline |

## Key Patterns

- All I/O is async (`async/await` with Playwright and httpx)
- LLM client retries up to 3 times (5s delay) on `RemoteProtocolError`, `ConnectError`, `ReadTimeout`; HTTP 4xx/5xx propagate immediately
- Scraper tries CSS selectors in order: `.article-container` → `[class*='ArticleWrapper']` → `main article` → `main`; falls back to article summary if <100 chars extracted, sets `has_fallbacks=True`
- Analyzer processes articles one-by-one (not batched); handles LLM returning either a JSON object or single-element array
- Ranker parses LLM response as comma-separated 0-based indices via regex; validates bounds
- Cookies: browser export (Cookie-Editor) format; SameSite "unspecified"/"no_restriction" normalized to "None"
- Only notifier failure triggers `sys.exit(1)`; analyzer/scraper failures degrade gracefully
- Audio is best-effort: synthesis/upload failures leave `audio_url=None` and the text push still proceeds
- Audio release tags use `audio-digest-*` and `audio-hot-*`; retention keeps only the most recent `AUDIO_KEEP_RELEASES` releases per prefix
- CI runs daily: digest at UTC 23:00, hot digest at UTC 23:30 (`.github/workflows/daily.yml`)
