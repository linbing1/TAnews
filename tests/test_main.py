import json
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from src.config import save_step
from src.models import Article, AnalyzedArticle


class TestSaveStep:
    def test_creates_output_dir_and_file(self, tmp_path):
        data = [{"title": "Test"}]
        save_step("step1_collected", data, output_dir=str(tmp_path))
        path = tmp_path / "step1_collected.json"
        assert path.exists()
        assert json.loads(path.read_text()) == data


class TestMainPipeline:
    @patch("main.save_step")
    @patch("main.notify")
    @patch("main.analyze_articles")
    @patch("main.scrape_full_texts", new_callable=AsyncMock)
    @patch("main.rank_articles")
    @patch("main.collect_articles", new_callable=AsyncMock)
    @patch("main.get_config")
    def test_full_pipeline(
        self, mock_config, mock_collect, mock_rank, mock_scrape, mock_analyze, mock_notify, mock_save
    ):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
            "audio_enabled": False,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }

        article = Article(
            title="Test", link="http://x", summary="S",
            published=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        mock_collect.return_value = [article]
        mock_rank.return_value = [article]
        mock_scrape.return_value = ([article], False)

        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="Test", article_type="新闻",
            importance=5, overview="概述", detail="详情",
            key_people_and_data="数据", impact="影响", link="http://x",
        )
        mock_analyze.return_value = [analyzed]
        mock_notify.return_value = True

        from main import run
        import asyncio
        asyncio.run(run())

        mock_collect.assert_called_once()
        mock_rank.assert_called_once()
        mock_scrape.assert_called_once()
        mock_analyze.assert_called_once()
        mock_notify.assert_called_once()

    @patch("main.save_step")
    @patch("main.notify")
    @patch("main.collect_articles", new_callable=AsyncMock)
    @patch("main.get_config")
    def test_no_articles_sends_no_notification(self, mock_config, mock_collect, mock_notify, mock_save):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
            "audio_enabled": False,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }
        mock_collect.return_value = []

        from main import run
        import asyncio
        asyncio.run(run())

        mock_notify.assert_not_called()

    @patch("main.save_step")
    @patch("main.notify")
    @patch("main.synthesize_and_upload", new_callable=AsyncMock, create=True)
    @patch("main.build_audio_script", create=True)
    @patch("main.analyze_articles")
    @patch("main.scrape_full_texts", new_callable=AsyncMock)
    @patch("main.rank_articles")
    @patch("main.collect_articles", new_callable=AsyncMock)
    @patch("main.get_config")
    def test_audio_enabled_generates_and_sends_audio_url(
        self,
        mock_config,
        mock_collect,
        mock_rank,
        mock_scrape,
        mock_analyze,
        mock_build_audio_script,
        mock_synthesize,
        mock_notify,
        mock_save,
    ):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
            "audio_enabled": True,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }

        article = Article(
            title="Test", link="http://x", summary="S",
            published=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="Test", article_type="新闻",
            importance=5, overview="概述", detail="详情",
            key_people_and_data="数据", impact="影响", link="http://x",
        )

        mock_collect.return_value = [article]
        mock_rank.return_value = [article]
        mock_scrape.return_value = ([article], False)
        mock_analyze.return_value = [analyzed]
        mock_build_audio_script.return_value = "audio script"
        mock_synthesize.return_value = "https://example.com/audio.mp3"
        mock_notify.return_value = True

        from main import run
        asyncio.run(run())

        mock_build_audio_script.assert_called_once()
        mock_synthesize.assert_awaited_once()
        assert mock_notify.call_args.kwargs["audio_url"] == "https://example.com/audio.mp3"

    @patch("main.save_step")
    @patch("main.notify")
    @patch("main.synthesize_and_upload", new_callable=AsyncMock, create=True)
    @patch("main.build_audio_script", create=True)
    @patch("main.analyze_articles")
    @patch("main.scrape_full_texts", new_callable=AsyncMock)
    @patch("main.rank_articles")
    @patch("main.collect_articles", new_callable=AsyncMock)
    @patch("main.get_config")
    def test_audio_failure_falls_back_to_text_only(
        self,
        mock_config,
        mock_collect,
        mock_rank,
        mock_scrape,
        mock_analyze,
        mock_build_audio_script,
        mock_synthesize,
        mock_notify,
        mock_save,
    ):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
            "audio_enabled": True,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }

        article = Article(
            title="Test", link="http://x", summary="S",
            published=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="Test", article_type="新闻",
            importance=5, overview="概述", detail="详情",
            key_people_and_data="数据", impact="影响", link="http://x",
        )

        mock_collect.return_value = [article]
        mock_rank.return_value = [article]
        mock_scrape.return_value = ([article], False)
        mock_analyze.return_value = [analyzed]
        mock_build_audio_script.side_effect = RuntimeError("boom")
        mock_notify.return_value = True

        from main import run
        asyncio.run(run())

        mock_notify.assert_called_once()
        assert mock_notify.call_args.kwargs["audio_url"] is None
        mock_synthesize.assert_not_awaited()

    @patch("main.save_step")
    @patch("main.notify")
    @patch("main.synthesize_and_upload", new_callable=AsyncMock, create=True)
    @patch("main.build_audio_script", create=True)
    @patch("main.analyze_articles")
    @patch("main.scrape_full_texts", new_callable=AsyncMock)
    @patch("main.rank_articles")
    @patch("main.collect_articles", new_callable=AsyncMock)
    @patch("main.get_config")
    def test_audio_disabled_skips_audio_branch(
        self,
        mock_config,
        mock_collect,
        mock_rank,
        mock_scrape,
        mock_analyze,
        mock_build_audio_script,
        mock_synthesize,
        mock_notify,
        mock_save,
    ):
        mock_config.return_value = {
            "page_url": "http://page",
            "athletic_cookies": [],
            "llm_base_url": "https://api.example.com",
            "llm_api_key": "key",
            "llm_model": "test-model",
            "serverchan_key": "sc-key",
            "top_n": 5,
            "audio_enabled": False,
            "audio_voice": "zh-CN-YunjianNeural",
            "audio_keep_releases": 7,
        }

        article = Article(
            title="Test", link="http://x", summary="S",
            published=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        analyzed = AnalyzedArticle(
            title_cn="测试", title_original="Test", article_type="新闻",
            importance=5, overview="概述", detail="详情",
            key_people_and_data="数据", impact="影响", link="http://x",
        )

        mock_collect.return_value = [article]
        mock_rank.return_value = [article]
        mock_scrape.return_value = ([article], False)
        mock_analyze.return_value = [analyzed]
        mock_notify.return_value = True

        from main import run
        asyncio.run(run())

        mock_build_audio_script.assert_not_called()
        mock_synthesize.assert_not_awaited()
        assert mock_notify.call_args.kwargs["audio_url"] is None
