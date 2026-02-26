# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `src/`, with one module per pipeline stage:
- `collector.py` / `hot_collector.py`: scrape listing data from The Athletic
- `ranker.py`, `scraper.py`, `analyzer.py`, `notifier.py`: ranking, full-text scraping, analysis, and push
- `config.py`, `llm.py`, `models.py`: config, API client, dataclasses

Entry points are `main.py` (daily digest) and `main_hot.py` (hot-comment digest).  
Tests are under `tests/` (`test_*.py`, plus `tests/fixtures/`).  
Planning docs are in `docs/plans/`. Runtime artifacts are written to `output/`.

## Build, Test, and Development Commands
- `python3.12 -m venv .venv && source .venv/bin/activate`: create and activate local env
- `pip install -r requirements.txt`: install dependencies
- `playwright install --with-deps chromium`: install browser runtime required by scrapers
- `python main.py`: run the daily digest pipeline
- `python main_hot.py`: run the hot-comment pipeline
- `pytest tests/ -v`: run full automated test suite
- `pytest tests/test_collector.py -k test_name -v`: run one targeted test

## Coding Style & Naming Conventions
Use Python 3.12 style with 4-space indentation and PEP 8 naming:
- `snake_case` for functions/variables/modules
- `PascalCase` for dataclasses/types (`Article`, `AnalyzedArticle`)
- keep async I/O explicit (`async def`, `await`) for Playwright/httpx paths

No repo-level formatter config is committed; match existing import ordering and concise logging patterns.

## Testing Guidelines
Frameworks: `pytest`, `pytest-asyncio`, `respx`, `unittest.mock`.  
Add or update tests in `tests/test_<module>.py` for each behavior change.  
Prefer unit tests with mocked network/browser dependencies; avoid live external calls in CI-facing tests.  
No fixed coverage gate is defined, but PRs should include tests for changed logic and failure paths.

## Commit & Pull Request Guidelines
Follow Conventional Commit style seen in history: `feat: ...`, `fix: ...`, `refactor: ...`, `ci: ...`, optional scope (for example `fix(analyzer): ...`).  
Keep commits focused and messages one line, imperative, and specific.

PRs should include:
- What changed and why
- Linked issue/task (if available)
- Test evidence (exact `pytest` command/results)
- Any env/config/workflow impact (`LLM_*`, `ATHLETIC_COOKIES`, `SERVERCHAN_KEY`, cron changes)

## Security & Configuration Tips
Never commit secrets or cookie payloads. Use environment variables and GitHub Secrets for credentials.  
When sharing logs, redact API keys, cookies, and notification tokens.
