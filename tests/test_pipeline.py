import asyncio
from unittest.mock import patch, AsyncMock
from datetime import date, datetime, timezone
import os

from src.models import Article, AnalyzedArticle


def _make_config(audio_enabled: bool = False) -> dict:
    return {
        "page_url": "http://page",
        "athletic_cookies": [],
        "llm_base_url": "https://api.example.com",
        "llm_api_key": "key",
        "llm_model": "test-model",
        "serverchan_key": "sc-key",
        "top_n": 5,
        "audio_enabled": audio_enabled,
        "audio_voice": "zh-CN-YunjianNeural",
        "audio_keep_releases": 7,
    }


def _make_article() -> Article:
    return Article(
        title="Test", link="http://x", summary="S",
        published=datetime(2026, 2, 15, tzinfo=timezone.utc),
        comment_count=42,
    )


def _make_analyzed() -> AnalyzedArticle:
    return AnalyzedArticle(
        title_cn="测试", title_original="Test", article_type="新闻",
        importance=5, overview="概述", detail="详情",
        link="http://x",
    )


class TestRunPipelineDigest:
    @patch("src.pipeline.save_step")
    @patch("src.pipeline.notify")
    @patch("src.pipeline.analyze_articles", new_callable=AsyncMock)
    @patch("src.pipeline.scrape_full_texts", new_callable=AsyncMock)
    @patch("src.pipeline.rank_articles")
    @patch("src.pipeline.collect_articles", new_callable=AsyncMock)
    def test_full_digest_pipeline_calls_rank(
        self, mock_collect, mock_rank, mock_scrape, mock_analyze, mock_notify, mock_save
    ):
        from src.pipeline import run_pipeline

        mock_collect.return_value = [_make_article()]
        mock_rank.return_value = [_make_article()]
        mock_scrape.return_value = ([_make_article()], False)
        mock_analyze.return_value = [_make_analyzed()]
        mock_notify.return_value = True

        asyncio.run(run_pipeline(mode="digest", config=_make_config()))

        mock_collect.assert_awaited_once()
        mock_rank.assert_called_once()
        mock_scrape.assert_awaited_once()
        mock_analyze.assert_called_once()
        mock_notify.assert_called_once()
        assert mock_notify.call_args.kwargs["title_prefix"] == "英超每日精选"

    @patch("src.pipeline.save_step")
    @patch("src.pipeline.notify")
    @patch("src.pipeline.collect_articles", new_callable=AsyncMock)
    def test_digest_no_articles_skips_notify(self, mock_collect, mock_notify, mock_save):
        from src.pipeline import run_pipeline

        mock_collect.return_value = []
        asyncio.run(run_pipeline(mode="digest", config=_make_config()))

        mock_notify.assert_not_called()


class TestRunPipelineHot:
    @patch("src.pipeline.save_step")
    @patch("src.pipeline.notify")
    @patch("src.pipeline.analyze_articles", new_callable=AsyncMock)
    @patch("src.pipeline.scrape_full_texts", new_callable=AsyncMock)
    @patch("src.pipeline.rank_articles")
    @patch("src.pipeline.collect_hot_articles", new_callable=AsyncMock)
    def test_full_hot_pipeline_skips_rank(
        self, mock_collect, mock_rank, mock_scrape, mock_analyze, mock_notify, mock_save
    ):
        from src.pipeline import run_pipeline

        mock_collect.return_value = [_make_article()]
        mock_scrape.return_value = ([_make_article()], False)
        mock_analyze.return_value = [_make_analyzed()]
        mock_notify.return_value = True

        asyncio.run(run_pipeline(mode="hot", config=_make_config()))

        mock_collect.assert_awaited_once()
        mock_rank.assert_not_called()
        mock_scrape.assert_awaited_once()
        mock_analyze.assert_called_once()
        assert mock_notify.call_args.kwargs["title_prefix"] == "英超热议文章"


class TestRunPipelineAudio:
    @patch("src.pipeline.save_step")
    @patch("src.pipeline.notify")
    @patch("src.pipeline.synthesize_and_upload", new_callable=AsyncMock)
    @patch("src.pipeline.build_audio_script")
    @patch("src.pipeline.analyze_articles", new_callable=AsyncMock)
    @patch("src.pipeline.scrape_full_texts", new_callable=AsyncMock)
    @patch("src.pipeline.rank_articles")
    @patch("src.pipeline.collect_articles", new_callable=AsyncMock)
    def test_digest_audio_uses_audio_digest_tag(
        self, mock_collect, mock_rank, mock_scrape, mock_analyze,
        mock_script, mock_synth, mock_notify, mock_save,
    ):
        from src.pipeline import run_pipeline

        mock_collect.return_value = [_make_article()]
        mock_rank.return_value = [_make_article()]
        mock_scrape.return_value = ([_make_article()], False)
        mock_analyze.return_value = [_make_analyzed()]
        mock_script.return_value = "script"
        mock_synth.return_value = "https://example.com/a.mp3"
        mock_notify.return_value = True

        asyncio.run(run_pipeline(mode="digest", config=_make_config(audio_enabled=True)))

        assert mock_synth.await_args.kwargs["tag_prefix"] == "audio-digest"
        assert mock_notify.call_args.kwargs["audio_url"] == "https://example.com/a.mp3"

    @patch("src.pipeline.save_step")
    @patch("src.pipeline.notify")
    @patch("src.pipeline.synthesize_and_upload", new_callable=AsyncMock)
    @patch("src.pipeline.build_audio_script")
    @patch("src.pipeline.analyze_articles", new_callable=AsyncMock)
    @patch("src.pipeline.scrape_full_texts", new_callable=AsyncMock)
    @patch("src.pipeline.collect_hot_articles", new_callable=AsyncMock)
    def test_hot_audio_uses_audio_hot_tag(
        self, mock_collect, mock_scrape, mock_analyze,
        mock_script, mock_synth, mock_notify, mock_save,
    ):
        from src.pipeline import run_pipeline

        mock_collect.return_value = [_make_article()]
        mock_scrape.return_value = ([_make_article()], False)
        mock_analyze.return_value = [_make_analyzed()]
        mock_script.return_value = "script"
        mock_synth.return_value = "https://example.com/h.mp3"
        mock_notify.return_value = True

        asyncio.run(run_pipeline(mode="hot", config=_make_config(audio_enabled=True)))

        assert mock_synth.await_args.kwargs["tag_prefix"] == "audio-hot"
        assert mock_notify.call_args.kwargs["title_prefix"] == "英超热议文章"

    @patch("src.pipeline.save_step")
    @patch("src.pipeline.notify")
    @patch("src.pipeline.synthesize_and_upload", new_callable=AsyncMock)
    @patch("src.pipeline.build_audio_script")
    @patch("src.pipeline.analyze_articles", new_callable=AsyncMock)
    @patch("src.pipeline.scrape_full_texts", new_callable=AsyncMock)
    @patch("src.pipeline.rank_articles")
    @patch("src.pipeline.collect_articles", new_callable=AsyncMock)
    def test_audio_failure_falls_back_to_text_only(
        self, mock_collect, mock_rank, mock_scrape, mock_analyze,
        mock_script, mock_synth, mock_notify, mock_save,
    ):
        from src.pipeline import run_pipeline

        mock_collect.return_value = [_make_article()]
        mock_rank.return_value = [_make_article()]
        mock_scrape.return_value = ([_make_article()], False)
        mock_analyze.return_value = [_make_analyzed()]
        mock_script.return_value = "script"
        mock_synth.side_effect = RuntimeError("boom")
        mock_notify.return_value = True

        asyncio.run(run_pipeline(mode="digest", config=_make_config(audio_enabled=True)))

        assert mock_notify.call_args.kwargs["audio_url"] is None

    @patch("src.pipeline.beijing_today")
    @patch("src.pipeline.save_step")
    @patch("src.pipeline.notify")
    @patch("src.pipeline.synthesize_and_upload", new_callable=AsyncMock)
    @patch("src.pipeline.build_audio_script")
    @patch("src.pipeline.analyze_articles", new_callable=AsyncMock)
    @patch("src.pipeline.scrape_full_texts", new_callable=AsyncMock)
    @patch("src.pipeline.rank_articles")
    @patch("src.pipeline.collect_articles", new_callable=AsyncMock)
    def test_uses_beijing_date_for_output_audio_and_notify(
        self,
        mock_collect,
        mock_rank,
        mock_scrape,
        mock_analyze,
        mock_script,
        mock_synth,
        mock_notify,
        mock_save,
        mock_beijing_today,
    ):
        from src.pipeline import run_pipeline

        fixed_today = date(2026, 2, 16)
        mock_beijing_today.return_value = fixed_today
        mock_collect.return_value = [_make_article()]
        mock_rank.return_value = [_make_article()]
        mock_scrape.return_value = ([_make_article()], False)
        mock_analyze.return_value = [_make_analyzed()]
        mock_script.return_value = "script"
        mock_synth.return_value = "https://example.com/a.mp3"
        mock_notify.return_value = True

        asyncio.run(run_pipeline(mode="digest", config=_make_config(audio_enabled=True)))

        expected_output_dir = os.path.join("output", str(fixed_today))
        assert all(call.args[2] == expected_output_dir for call in mock_save.call_args_list)
        assert mock_script.call_args.args[2] == fixed_today
        assert mock_synth.await_args.args[1] == fixed_today
        assert mock_notify.call_args.kwargs["today"] == fixed_today
