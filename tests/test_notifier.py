from unittest.mock import patch, MagicMock
from datetime import date

import pytest

from src.models import AnalyzedArticle
from src.notifier import notify, format_digest


def _make_analyzed() -> AnalyzedArticle:
    return AnalyzedArticle(
        title_cn="阿森纳争冠分析", title_original="Arsenal title race analysis",
        article_type="深度分析", importance=5,
        overview="阿森纳在本赛季展现了强大的争冠实力。",
        detail="**战术转折：** 详细的战术分析。",
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
        assert "### 文章概述" in body
        assert "### 详细内容" in body
        assert "关键人物与数据" not in body
        assert "影响与展望" not in body

    def test_preserves_bold_section_markers_in_detail(self):
        article = AnalyzedArticle(
            title_cn="标题", title_original="Title",
            article_type="深度分析", importance=3,
            overview="概述",
            detail="**战术转折：** 前半场被动。\n\n> 教练说：'我们必须做出改变。'\n\n**数据与对比：** **xG 2.41**。",
            link="https://example.com/1",
        )

        _, body = format_digest([article], date(2026, 2, 15))
        assert "**战术转折：**" in body
        assert "> 教练说：" in body
        assert "**xG 2.41**" in body

    def test_custom_title_prefix(self):
        articles = [_make_analyzed()]
        title, body = format_digest(articles, date(2026, 2, 16), title_prefix="英超热议文章")
        assert "英超热议文章" in title
        assert "2026-02-16" in title
        assert "英超每日精选" not in title

    @pytest.mark.parametrize(
        ("has_fallbacks", "audio_url", "expected_present", "expected_absent"),
        [
            (False, None, [], ["点击收听音频版", "Cookie 可能失效"]),
            (
                True,
                "https://example.com/audio.mp3",
                ["🎧 [点击收听音频版](https://example.com/audio.mp3)", "Cookie 可能失效", "ATHLETIC_COOKIES"],
                [],
            ),
        ],
    )
    def test_format_digest_optional_blocks(
        self,
        has_fallbacks,
        audio_url,
        expected_present,
        expected_absent,
    ):
        _, body = format_digest(
            [_make_analyzed()],
            date(2026, 2, 15),
            has_fallbacks=has_fallbacks,
            audio_url=audio_url,
        )

        for text in expected_present:
            assert text in body
        for text in expected_absent:
            assert text not in body

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
