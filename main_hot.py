import asyncio
import logging
import os
import sys
from dataclasses import asdict
from datetime import date

from src.analyzer import analyze_articles
from src.config import get_config, save_step
from src.hot_collector import collect_hot_articles
from src.llm import LLMClient
from src.notifier import notify
from src.scraper import scrape_full_texts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run():
    config = get_config()
    output_dir = os.path.join("output", "hot", str(date.today()))

    # Step 1: Collect articles by comment count
    logger.info("Step 1: Collecting most-commented articles...")
    articles = await collect_hot_articles(
        config["page_url"], config["athletic_cookies"], top_n=config["top_n"]
    )
    if not articles:
        logger.info("No articles found. Exiting.")
        return

    logger.info("Found %d hot articles", len(articles))
    save_step("step1_hot_collected", [asdict(a) for a in articles], output_dir)

    # Step 2: Scrape full texts
    logger.info("Step 2: Scraping full texts...")
    articles, has_fallbacks = await scrape_full_texts(articles, config["athletic_cookies"])
    save_step("step2_scraped", [
        {**asdict(a), "full_text": a.full_text[:200] + "..."} for a in articles
    ], output_dir)

    # Step 3: Analyze with LLM
    llm = LLMClient(
        base_url=config["llm_base_url"],
        api_key=config["llm_api_key"],
        model=config["llm_model"],
    )
    logger.info("Step 3: Analyzing articles...")
    analyzed = analyze_articles(articles, llm)
    save_step("step3_analyzed", [asdict(a) for a in analyzed], output_dir)
    if not analyzed:
        logger.error("Analysis failed, no results to push")
        return

    # Step 4: Push to WeChat
    logger.info("Step 4: Pushing to WeChat...")
    success = notify(analyzed, config["serverchan_key"], title_prefix="英超热议文章", has_fallbacks=has_fallbacks)
    if success:
        logger.info("Hot digest sent successfully!")
    else:
        logger.error("Failed to send hot digest")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
