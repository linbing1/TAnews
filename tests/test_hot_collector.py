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

    @pytest.mark.asyncio
    @patch("src.hot_collector.collect_articles")
    async def test_backfills_digest_links_when_unique_articles_are_insufficient(
        self, mock_collect
    ):
        repeated_high = _make_article("Arsenal win big", 100)
        repeated_low = _make_article("Liverpool draw", 50)
        fresh = _make_article("Chelsea transfer update", 10)
        mock_collect.return_value = [repeated_high, repeated_low, fresh]

        articles = await collect_hot_articles(
            "http://fake",
            cookies=[],
            top_n=3,
            exclude_links={repeated_high.link, repeated_low.link},
        )

        assert [article.title for article in articles] == [
            "Chelsea transfer update",
            "Arsenal win big",
            "Liverpool draw",
        ]
