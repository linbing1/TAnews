import json
import logging
import os
from datetime import date

logger = logging.getLogger(__name__)


def _get_env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value == "" or value is None else value


def get_config():
    cookie_raw = os.environ.get("ATHLETIC_COOKIES", "[]")
    try:
        cookies = json.loads(cookie_raw)
    except json.JSONDecodeError:
        logger.error("ATHLETIC_COOKIES is not valid JSON, using empty list")
        cookies = []

    return {
        "page_url": os.environ.get(
            "PAGE_URL", "https://www.nytimes.com/athletic/football/premier-league/"
        ),
        "athletic_cookies": cookies,
        "llm_base_url": os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"),
        "llm_api_key": os.environ.get("LLM_API_KEY", ""),
        "llm_model": os.environ.get("LLM_MODEL", "deepseek-chat"),
        "serverchan_key": os.environ.get("SERVERCHAN_KEY", ""),
        "top_n": int(os.environ.get("TOP_N", "5")),
        "audio_enabled": _get_env_or_default("AUDIO_ENABLED", "true").lower() != "false",
        "audio_voice": _get_env_or_default("AUDIO_VOICE", "zh-CN-YunjianNeural"),
        "audio_keep_releases": int(_get_env_or_default("AUDIO_KEEP_RELEASES", "7")),
    }


def save_step(name: str, data, output_dir: str | None = None):
    if output_dir is None:
        output_dir = os.path.join("output", str(date.today()))
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Saved %s to %s", name, path)
