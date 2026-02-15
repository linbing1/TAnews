import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.models import Article
from src.scraper import scrape_full_texts


def _make_article(title="Test", link="https://example.com/1") -> Article:
    return Article(
        title=title, link=link, summary="A summary",
        published=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )


class TestScrapeFullTexts:
    @pytest.mark.asyncio
    @patch("src.scraper._scrape_one", new_callable=AsyncMock)
    async def test_populates_full_text(self, mock_scrape_one):
        mock_scrape_one.return_value = "Full article content here."
        articles = [_make_article()]
        result = await scrape_full_texts(articles, cookies=[])
        assert result[0].full_text == "Full article content here."
        mock_scrape_one.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.scraper._scrape_one", new_callable=AsyncMock)
    async def test_falls_back_to_summary_on_failure(self, mock_scrape_one):
        mock_scrape_one.side_effect = Exception("Cookie expired")
        articles = [_make_article()]
        result = await scrape_full_texts(articles, cookies=[])
        assert result[0].full_text == articles[0].summary
