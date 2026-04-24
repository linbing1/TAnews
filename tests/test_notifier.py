from unittest.mock import patch, MagicMock
from datetime import date

from src.models import AnalyzedArticle
from src.notifier import notify, format_digest


def _make_analyzed() -> AnalyzedArticle:
    return AnalyzedArticle(
        title_cn="阿森纳争冠分析", title_original="Arsenal title race analysis",
        article_type="深度分析", importance=5,
        overview="阿森纳在本赛季展现了强大的争冠实力。",
        detail="详细的战术分析...",
        key_people_and_data="萨卡、厄德高",
        impact="对争冠形势产生重大影响。",
        link="https://example.com/1",
    )


class TestFormatDigest:
    def test_formats_markdown(self):
        articles = [_make_analyzed()]
        title, body = format_digest(articles, date(2026, 2, 15))
        assert "英超每日精选" in title
        assert "2026-02-15" in title
        assert "阿森纳争冠分析" in body
        assert "深度分析" in body
        assert "⭐⭐⭐⭐⭐" in body

    def test_custom_title_prefix(self):
        articles = [_make_analyzed()]
        title, body = format_digest(articles, date(2026, 2, 16), title_prefix="英超热议文章")
        assert "英超热议文章" in title
        assert "2026-02-16" in title
        assert "英超每日精选" not in title

    def test_no_audio_line_when_audio_url_missing(self):
        articles = [_make_analyzed()]
        _, body = format_digest(articles, date(2026, 2, 15), audio_url=None)
        assert "点击收听音频版" not in body

    def test_audio_line_appears_below_title_before_first_section(self):
        articles = [_make_analyzed()]
        _, body = format_digest(
            articles,
            date(2026, 2, 15),
            audio_url="https://example.com/audio.mp3",
        )

        title_line = "# ⚽ 英超每日精选 - 2026-02-15"
        audio_line = "🎧 [点击收听音频版](https://example.com/audio.mp3)"
        first_section = "## 1. 阿森纳争冠分析"

        assert f"{title_line}\n\n{audio_line}\n\n{first_section}" in body

    def test_audio_line_coexists_with_fallback_warning(self):
        articles = [_make_analyzed()]
        _, body = format_digest(
            articles,
            date(2026, 2, 15),
            has_fallbacks=True,
            audio_url="https://example.com/audio.mp3",
        )

        assert "🎧 [点击收听音频版](https://example.com/audio.mp3)" in body
        assert "Cookie 可能失效" in body


class TestNotify:
    @patch("src.notifier.httpx.post")
    def test_sends_to_serverchan(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "message": "success"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        articles = [_make_analyzed()]
        result = notify(articles, "test-key")

        assert result is True
        mock_post.assert_called_once()
        call_data = mock_post.call_args
        assert "test-key" in call_data[0][0]


class TestFormatDigestFallbackWarning:
    def test_no_warning_without_fallbacks(self):
        articles = [_make_analyzed()]
        _, body = format_digest(articles, date(2026, 2, 15), has_fallbacks=False)
        assert "Cookie" not in body

    def test_warning_appended_with_fallbacks(self):
        articles = [_make_analyzed()]
        _, body = format_digest(articles, date(2026, 2, 15), has_fallbacks=True)
        assert "Cookie 可能失效" in body
        assert "ATHLETIC_COOKIES" in body
