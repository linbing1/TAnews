import json
import os


def get_config():
    return {
        "page_url": os.environ.get(
            "PAGE_URL", "https://www.nytimes.com/athletic/football/premier-league/"
        ),
        "athletic_cookies": json.loads(os.environ.get("ATHLETIC_COOKIES", "[]")),
        "llm_base_url": os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"),
        "llm_api_key": os.environ.get("LLM_API_KEY", ""),
        "llm_model": os.environ.get("LLM_MODEL", "deepseek-chat"),
        "serverchan_key": os.environ.get("SERVERCHAN_KEY", ""),
        "top_n": int(os.environ.get("TOP_N", "5")),
    }
