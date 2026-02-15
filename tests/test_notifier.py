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
