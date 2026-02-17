import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.models import Article
from src.hot_collector import collect_hot_articles


def _make_article(title, comment_count):
    return Article(
        title=title,
        link=f"https://example.com/{title.replace(' ', '-')}",
        summary=title,
        published=datetime(2026, 2, 16, tzinfo=timezone.utc),
        comment_count=comment_count,
    )


class TestCollectHotArticles:
    @pytest.mark.asyncio
    @patch("src.hot_collector.collect_articles")
    async def test_returns_top_n_by_comment_count(self, mock_collect):
        mock_collect.return_value = [
            _make_article("Arsenal win big", 10),
            _make_article("Liverpool draw with Chelsea", 50),
            _make_article("Spurs suffer defeat", 30),
        ]

        articles = await collect_hot_articles("http://fake", cookies=[], top_n=2)

        assert len(articles) == 2
        assert articles[0].title == "Liverpool draw with Chelsea"
        assert articles[0].comment_count == 50
        assert articles[1].title == "Spurs suffer defeat"
        assert articles[1].comment_count == 30

    @pytest.mark.asyncio
    @patch("src.hot_collector.collect_articles")
    async def test_returns_empty_when_no_articles(self, mock_collect):
        mock_collect.return_value = []

        articles = await collect_hot_articles("http://fake", cookies=[], top_n=5)
        assert articles == []
