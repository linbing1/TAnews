# TAnews

Automated Premier League daily digest pipeline. Scrapes The Athletic, uses an LLM to select and rank articles, generates deep Chinese analysis, produces an optional audio broadcast, and pushes the result to WeChat via Server酱.

## Pipelines

| Pipeline | Entry | Schedule (Beijing) | Behaviour |
|----------|-------|--------------------|-----------|
| Digest | `main.py` | 07:00 daily | LLM selects top-N articles → scrape → analyze → audio → WeChat |
| Hot | `main_hot.py` | 07:30 daily | Sort by comment count → scrape → analyze → audio → WeChat |

```
Digest:  Collector → Ranker (LLM) → Scraper → Analyzer → Audio Scripter* → Audio Synth* → Notifier
Hot:     Collector (comment count) → sort → Scraper → Analyzer → Audio Scripter* → Audio Synth* → Notifier
```

`*` Optional — controlled by `AUDIO_ENABLED`.

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

Copy your Athletic cookies via [Cookie-Editor](https://cookie-editor.com/) browser extension (Export → JSON) and set the environment variables below.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ATHLETIC_COOKIES` | Yes | `[]` | JSON array of browser cookies (Cookie-Editor export format) |
| `LLM_API_KEY` | Yes | — | LLM API key |
| `SERVERCHAN_KEY` | Yes | — | Server酱 SendKey for WeChat push |
| `LLM_BASE_URL` | No | `https://api.deepseek.com/v1` | LLM endpoint |
| `LLM_MODEL` | No | `deepseek-chat` | Model name |
| `PAGE_URL` | No | NYT Athletic PL listing URL | Listing page to scrape |
| `TOP_N` | No | `5` | Number of articles to select |
| `AUDIO_ENABLED` | No | `true` | Toggle audio script / synthesis branch |
| `AUDIO_VOICE` | No | `zh-CN-YunjianNeural` | Edge-TTS voice for MP3 generation |
| `AUDIO_KEEP_RELEASES` | No | `7` | Number of recent audio GitHub Releases to retain |

## Running Locally

```bash
source .venv/bin/activate
export ATHLETIC_COOKIES='[...]'
export LLM_API_KEY='sk-...'
export SERVERCHAN_KEY='...'

python main.py        # digest pipeline
python main_hot.py    # hot discussion pipeline
```

## Tests

```bash
pytest tests/ -v
pytest tests/test_collector.py              # single file
pytest tests/test_collector.py -k test_name # single test
```

## Architecture

```
main.py              # Digest entry: calls run_pipeline(mode="digest")
main_hot.py          # Hot entry:    calls run_pipeline(mode="hot")
src/
  config.py          # Loads env vars into config dict
  pipeline.py        # Unified pipeline; mode routes collect/rank/prefix differences
  models.py          # Dataclasses: Article, AnalyzedArticle
  collector.py       # Playwright scrapes listing page; filters by 24 PL keywords; extracts comment counts
  hot_collector.py   # Same as collector but sorts by comment count and returns top-N
  ranker.py          # LLM selects top N; skips LLM if articles ≤ top_n
  scraper.py         # Playwright + cookies; 4-selector fallback chain; returns (articles, has_fallbacks)
  analyzer.py        # LLM deep Chinese analysis per article; returns structured JSON
  audio_scripter.py  # LLM converts analyzed digest into a spoken Chinese broadcast script
  audio_synth.py     # Edge-TTS synthesis + GitHub Release upload/retention for MP3 output
  llm.py             # OpenAI-compatible client; exponential backoff on transient errors
  notifier.py        # Formats Markdown digest; pushes to WeChat via Server酱
  prompts/
    analyzer.md      # System prompt for the analyzer LLM call
    audio_scripter.md # System prompt for the audio scripter LLM call
tests/               # pytest + pytest-asyncio; Playwright/LLM/HTTP mocked via AsyncMock
output/{date}/       # Intermediate JSON snapshots saved per step for debugging
docs/
  audio-player.html  # Static player page for GitHub-hosted audio releases
.github/workflows/
  daily.yml          # Scheduled CI: digest at UTC 23:00, hot at UTC 23:30
```

## Key Implementation Notes

- All I/O is async (`async/await` with Playwright and httpx)
- LLM client retries up to 3 times with exponential backoff on `RemoteProtocolError`, `ConnectError`, `ReadTimeout`, `WriteError`, `PoolTimeout`; HTTP 429/5xx also retried; 4xx propagates immediately
- Scraper tries CSS selectors in order: `.article-container` → `[class*='ArticleWrapper']` → `main article` → `main`; falls back to article summary if <100 chars extracted, sets `has_fallbacks=True`
- Analyzer processes articles one-by-one; handles LLM returning either a JSON object or single-element array
- Ranker parses LLM response as comma-separated 0-based indices via regex; validates bounds
- Audio script is stripped of Markdown symbols before TTS synthesis to prevent literal reading of `**` etc.
- Audio is best-effort: synthesis/upload failures leave `audio_url=None` and the text push still proceeds
- Only notifier failure triggers `sys.exit(1)`; all other failures degrade gracefully
- Cookies: Cookie-Editor browser export format; `SameSite` values `"unspecified"/"no_restriction"` are normalized to `"None"`
- Audio release tags use `audio-digest-*` and `audio-hot-*`; retention keeps the most recent `AUDIO_KEEP_RELEASES` releases per prefix
