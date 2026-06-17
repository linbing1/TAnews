import logging
import os
import sys
from dataclasses import asdict
from typing import Literal

from src.analyzer import analyze_articles
from src.audio_scripter import build_audio_script
from src.audio_synth import synthesize_and_upload
from src.collector import collect_articles
from src.config import beijing_today, save_step
from src.hot_collector import collect_hot_articles
from src.llm import LLMClient
from src.notifier import notify
from src.ranker import rank_articles
from src.scraper import scrape_full_texts

logger = logging.getLogger(__name__)

_MODE_DEFAULTS = {
    "digest": {
        "title_prefix": "英超每日精选",
        "tag_prefix": "audio-digest",
        "output_subdir": None,
    },
    "hot": {
        "title_prefix": "英超每日热议",
        "tag_prefix": "audio-hot",
        "output_subdir": "hot",
    },
    "world_cup": {
        "title_prefix": "世界杯每日精选",
        "tag_prefix": "audio-world-cup",
        "output_subdir": "world-cup",
    },
}


async def run_pipeline(
    *, mode: Literal["digest", "hot", "world_cup"], config: dict, exclude_links: set[str] | None = None
) -> set[str] | None:
    if mode not in _MODE_DEFAULTS:
        raise ValueError(f"unknown mode: {mode}")
    opts = _MODE_DEFAULTS[mode]

    today = beijing_today()
    subdir = opts["output_subdir"]
    output_dir = os.path.join("output", subdir, str(today)) if subdir else os.path.join("output", str(today))

    logger.info("Step 1: Collecting articles (mode=%s)...", mode)
    if mode == "digest":
        articles = await collect_articles(config["page_url"], config["athletic_cookies"])
    elif mode == "world_cup":
        articles = await collect_articles(
            config["world_cup_page_url"],
            config["athletic_cookies"],
            article_filter=None,
        )
    else:
        articles = await collect_hot_articles(
            config["page_url"], config["athletic_cookies"], top_n=config["top_n"],
            exclude_links=exclude_links,
        )

    if not articles:
        logger.info("All articles already covered by digest. Exiting.")
        return None

    logger.info("Found %d articles", len(articles))
    save_step("step1_collected", [asdict(a) for a in articles], output_dir)

    llm = LLMClient(
        base_url=config["llm_base_url"],
        api_key=config["llm_api_key"],
        model=config["llm_model"],
    )

    selected_links: set[str] | None = None
    if mode in ("digest", "world_cup"):
        logger.info("Step 2: Ranking articles...")
        articles = rank_articles(articles, llm, top_n=config["top_n"])
        selected_links = {a.link for a in articles}
        logger.info("Selected top %d articles", len(articles))
        save_step("step2_ranked", [asdict(a) for a in articles], output_dir)

    logger.info("Step 3: Scraping full texts...")
    articles, has_fallbacks = await scrape_full_texts(articles, config["athletic_cookies"])
    save_step(
        "step3_scraped",
        [{**asdict(a), "full_text": a.full_text[:200] + "..."} for a in articles],
        output_dir,
    )

    logger.info("Step 4: Analyzing articles...")
    analyzed = await analyze_articles(articles, llm)
    save_step("step4_analyzed", [asdict(a) for a in analyzed], output_dir)
    if not analyzed:
        logger.error("Analysis failed, no results to push")
        return selected_links

    audio_url: str | None = None
    if config["audio_enabled"]:
        try:
            logger.info("Step 4a: Generating audio script...")
            script = build_audio_script(analyzed, llm, today, title_prefix=opts["title_prefix"])
            save_step("step4a_script", {"script": script}, output_dir)

            logger.info("Step 4b: Synthesizing and uploading audio...")
            audio_url = await synthesize_and_upload(
                script,
                today,
                voice=config["audio_voice"],
                tag_prefix=opts["tag_prefix"],
                keep=config["audio_keep_releases"],
            )
            save_step("step4b_audio", {"url": audio_url}, output_dir)
        except Exception as e:
            logger.error("Audio pipeline failed, falling back to text-only: %s", e)

    logger.info("Step 5: Pushing to WeChat...")
    success = notify(
        analyzed,
        config["serverchan_key"],
        today=today,
        title_prefix=opts["title_prefix"],
        has_fallbacks=has_fallbacks,
        audio_url=audio_url,
    )
    if success:
        logger.info("Pipeline (%s) sent successfully!", mode)
    else:
        logger.error("Failed to send pipeline (%s)", mode)
        sys.exit(1)

    return selected_links
