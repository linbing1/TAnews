import asyncio
import logging

from src.config import get_config
from src.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


if __name__ == "__main__":
    asyncio.run(run_pipeline(mode="hot", config=get_config()))
