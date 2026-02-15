# Premier League Daily Digest - Design Document

## Overview

A daily automated system that collects Premier League news from The Athletic, uses AI to select and deeply analyze the top 5 articles, and pushes a detailed Chinese-language digest to WeChat via Server酱.

## Architecture (Approach C: RSS + On-demand Full-text Scraping)

```
GitHub Actions (Cron UTC 23:00 = Beijing 07:00)
  │
  ▼
1. Collector (RSS + httpx)
   - Fetch The Athletic RSS feed
   - Filter by "Premier League" keywords
   - Keep articles from last 24h
   - Output: List[Article] (title, summary, link, time)
  │
  ▼
2. Ranker (LLM API - 1st call)
   - Input: all article titles + summaries
   - Task: rank by importance, select Top 5
   - Output: Top 5 article links
  │
  ▼
3. Scraper (Playwright + Cookie)
   - Only scrape Top 5 full texts (minimize scraping)
   - Launch Chromium, inject login cookie
   - Extract article body content
  │
  ▼
4. Analyzer (LLM API - 2nd call)
   - Input: Top 5 full texts
   - Output: detailed Chinese structured analysis per article
  │
  ▼
5. Notifier (Server酱)
   - Format as Markdown, push to WeChat
```

## Tech Stack

- **Language:** Python 3.12
- **RSS Parsing:** `httpx` + `feedparser`
- **Browser Automation:** Playwright (Python)
- **LLM:** Abstracted interface, switchable via `LLM_PROVIDER` env var (claude / openai / deepseek)
- **Push Notification:** Server酱 Turbo (`sctapi.ftqq.com`)
- **Scheduling:** GitHub Actions cron

## Project Structure

```
TAnews/
├── src/
│   ├── __init__.py
│   ├── collector.py      # RSS fetch and filter
│   ├── ranker.py          # LLM ranking to select Top 5
│   ├── scraper.py         # Playwright full-text scraping
│   ├── analyzer.py        # LLM deep analysis, Chinese output
│   ├── notifier.py        # Server酱 push
│   ├── llm.py             # LLM abstraction layer
│   └── config.py          # Config from env vars
├── main.py                # Entry point, orchestrates pipeline
├── requirements.txt
├── .github/
│   └── workflows/
│       └── daily.yml
└── docs/
    └── plans/
```

## Module Specifications

| Module | Input | Output | Dependencies |
|--------|-------|--------|-------------|
| `collector` | RSS URL | `List[Article]` (title, summary, link, time) | `httpx`, `feedparser` |
| `ranker` | `List[Article]` | `List[Article]` Top 5 | `llm` |
| `scraper` | Top 5 links + Cookie | `List[Article]` (with full text) | `playwright` |
| `analyzer` | Top 5 full texts | `List[Summary]` (Chinese structured) | `llm` |
| `notifier` | `List[Summary]` | Push result | `httpx` |
| `llm` | system prompt + user message | LLM response string | Provider SDK |

## LLM Abstraction

- Unified interface: `complete(system, user) -> str`
- Provider switched via `LLM_PROVIDER` env var
- Each provider is a simple adapter implementing the interface

## Push Message Format

```markdown
# ⚽ 英超每日精选 - 2026-02-15

## 1. [中文标题翻译]
**原标题：** The original English title
**类型：** 深度分析 | 新闻报道 | 战术解读 | 转会动态
**重要性：** ⭐⭐⭐⭐⭐

### 文章概述
2-3 sentences summarizing the core argument and conclusion.

### 详细内容
- Deep retelling of the article's key arguments and analytical logic (3-5 paragraphs)
- Preserve original data, quotes, tactical details
- For tactical analysis: formation changes, key player roles, data support
- For transfer news: source credibility, deal details, party attitudes
- For post-match analysis: key moment reconstruction, performance evaluation, data comparison

### 关键人物与数据
- Players/coaches involved, key statistics

### 影响与展望
Impact analysis and future developments to watch.

🔗 [阅读原文](link)

---
(5 articles total)
```

**Content depth guidelines for Analyzer:**
- In-depth analysis articles: 300-500 Chinese characters per article
- Regular news: 150-200 Chinese characters per article
- Always preserve data points, quotes, and tactical details

## Error Handling

- **RSS fetch failure:** Retry 3 times, then send error notification
- **Cookie expired (Playwright returns login page):** Skip full-text scraping, use RSS summaries as fallback, notify user to update cookie
- **LLM call failure:** Retry 2 times
- **Server酱 push failure:** Log to GitHub Actions output

## GitHub Actions Configuration

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
      - run: pip install -r requirements.txt
      - run: playwright install --with-deps chromium
      - run: python main.py
        env:
          ATHLETIC_COOKIES: ${{ secrets.ATHLETIC_COOKIES }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
          LLM_PROVIDER: ${{ vars.LLM_PROVIDER }}
          SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}
```

## Secrets (GitHub Actions Secrets)

- `ATHLETIC_COOKIES`: Login cookie JSON exported from browser
- `LLM_API_KEY`: LLM service API key
- `SERVERCHAN_KEY`: Server酱 SendKey

## Known Risks

1. **Cookie expiration:** The Athletic session cookies expire periodically. User must manually update `ATHLETIC_COOKIES` secret when this happens. The system will detect expired cookies and notify the user.
2. **GitHub Actions cron delay:** Cron jobs may be delayed by minutes to ~30 minutes. Not an issue for a daily digest.
3. **Repo inactivity:** GitHub disables scheduled workflows after 60 days of no activity. Mitigation: occasional manual trigger or a keepalive workflow.
4. **RSS feed changes:** The Athletic may change their RSS feed structure. The collector module should handle parsing errors gracefully.
