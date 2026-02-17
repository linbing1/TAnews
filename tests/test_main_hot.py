import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from src.models import Article, AnalyzedArticle


class TestHotPipeline:
    @patch("main_hot.save_step")
    @patch("main_hot.notify")
    @patch("main_hot.analyze_articles")
    @patch("main_hot.scrape_full_texts", new_callable=AsyncMock)
    @patch("main_hot.collect_hot_articles", new_callable=AsyncMock)
    @patch("main_hot.get_config")
    def test_full_pipeline(
        self, mock_config, mock_collect, mock_scrape, mock_analyze, mock_notify, mock_save
    ):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
        }

        article = Article(
            title="Test", link="http://x", summary="S",
            published=datetime(2026, 2, 16, tzinfo=timezone.utc),
            comment_count=42,
        )
        mock_collect.return_value = [article]
        mock_scrape.return_value = [article]

        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="Test", article_type="新闻",
            importance=5, overview="概述", detail="详情",
            key_people_and_data="数据", impact="影响", link="http://x",
        )
        mock_analyze.return_value = [analyzed]
        mock_notify.return_value = True

        from main_hot import run
        asyncio.run(run())

        mock_collect.assert_called_once()
        mock_scrape.assert_called_once()
        mock_analyze.assert_called_once()
        mock_notify.assert_called_once()
        # Verify title_prefix is passed
        notify_kwargs = mock_notify.call_args
        assert notify_kwargs[1]["title_prefix"] == "英超热议文章"

    @patch("main_hot.save_step")
    @patch("main_hot.notify")
    @patch("main_hot.collect_hot_articles", new_callable=AsyncMock)
    @patch("main_hot.get_config")
    def test_no_articles_sends_no_notification(
        self, mock_config, mock_collect, mock_notify, mock_save
    ):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
        }
        mock_collect.return_value = []

        from main_hot import run
        asyncio.run(run())

        mock_notify.assert_not_called()
