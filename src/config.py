import json
import os


def get_config():
    return {
        "rss_url": os.environ.get(
            "RSS_URL", "https://www.nytimes.com/athletic/rss/news/"
        ),
        "athletic_cookies": json.loads(os.environ.get("ATHLETIC_COOKIES", "[]")),
        "llm_base_url": os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
        "llm_api_key": os.environ.get("LLM_API_KEY", ""),
        "llm_model": os.environ.get("LLM_MODEL", "deepseek-chat"),
        "serverchan_key": os.environ.get("SERVERCHAN_KEY", ""),
        "top_n": int(os.environ.get("TOP_N", "5")),
    }
