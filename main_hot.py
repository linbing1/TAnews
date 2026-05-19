import asyncio
import json
import logging
import os

from src.config import get_config
from src.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


if __name__ == "__main__":
    exclude_links: set[str] | None = None
    links_file = os.getenv("DIGEST_LINKS_FILE")
    if links_file and os.path.exists(links_file):
        with open(links_file) as f:
            exclude_links = set(json.load(f))
        logging.getLogger(__name__).info("Loaded %d digest links to exclude", len(exclude_links))

    asyncio.run(run_pipeline(mode="hot", config=get_config(), exclude_links=exclude_links))
