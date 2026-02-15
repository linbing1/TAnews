import asyncio
import logging
import sys

from src.collector import collect_articles
from src.ranker import rank_articles
from src.scraper import scrape_full_texts
from src.analyzer import analyze_articles
from src.notifier import notify
from src.llm import LLMClient
from src.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run():
    config = get_config()

    # Step 1: Collect articles from listing page
    logger.info("Step 1: Collecting articles from listing page...")
    articles = await collect_articles(config["page_url"], config["athletic_cookies"])
    if not articles:
        logger.info("No Premier League articles found. Exiting.")
        return

    logger.info("Found %d articles", len(articles))

    # Step 2: Rank and select top N
    llm = LLMClient(
        base_url=config["llm_base_url"],
        api_key=config["llm_api_key"],
        model=config["llm_model"],
    )
    logger.info("Step 2: Ranking articles...")
    top_articles = rank_articles(articles, llm, top_n=config["top_n"])
    logger.info("Selected top %d articles", len(top_articles))

    # Step 3: Scrape full texts
    logger.info("Step 3: Scraping full texts...")
    top_articles = await scrape_full_texts(top_articles, config["athletic_cookies"])

    # Step 4: Analyze with LLM
    logger.info("Step 4: Analyzing articles...")
    analyzed = analyze_articles(top_articles, llm)
    if not analyzed:
        logger.error("Analysis failed, no results to push")
        return

    # Step 5: Push to WeChat
    logger.info("Step 5: Pushing to WeChat...")
    success = notify(analyzed, config["serverchan_key"])
    if success:
        logger.info("Daily digest sent successfully!")
    else:
        logger.error("Failed to send digest")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
