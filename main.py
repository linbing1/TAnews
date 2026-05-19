import asyncio
import json
import logging

from src.config import get_config
from src.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


if __name__ == "__main__":
    selected_links = asyncio.run(run_pipeline(mode="digest", config=get_config()))
    if selected_links:
        with open("/tmp/digest-links.json", "w") as f:
            json.dump(list(selected_links), f)
