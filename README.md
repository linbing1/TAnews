# TAnews

Scrapes The Athletic Premier League articles, runs LLM analysis in Chinese, and pushes a daily digest to WeChat via Server酱. Optionally generates an audio broadcast via Edge-TTS.

Pipelines:
- **Digest** (`main.py`, 07:30 Beijing): LLM selects top-N articles → analyze → push
- **Hot** (`main_hot.py`, 07:30 Beijing): sort by comment count → analyze → push
- **World Cup** (`main_world_cup.py`, 12:00 Beijing): LLM selects top-N World Cup articles → analyze → push

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ATHLETIC_COOKIES` | Yes | — | Cookie-Editor JSON export |
| `LLM_API_KEY` | Yes | — | LLM API key |
| `SERVERCHAN_KEY` | Yes | — | Server酱 SendKey |
| `LLM_BASE_URL` | No | `https://open.bigmodel.cn/api/coding/paas/v4` | LLM endpoint |
| `LLM_MODEL` | No | `deepseek-chat` | Model name |
| `TOP_N` | No | `5` | Articles to select |
| `WORLD_CUP_PAGE_URL` | No | `https://www.nytimes.com/athletic/football/world-cup/` | World Cup page URL |
| `AUDIO_ENABLED` | No | `true` | Toggle audio generation |
| `AUDIO_VOICE` | No | `zh-CN-YunjianNeural` | Edge-TTS voice |
| `AUDIO_KEEP_RELEASES` | No | `7` | GitHub Releases to retain |

## Tests

```bash
pytest tests/ -v
```
