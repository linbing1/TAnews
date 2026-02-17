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
    @patch("src.scraper._scrape_page", new_callable=AsyncMock)
    @patch("src.scraper.async_playwright")
    async def test_populates_full_text(self, mock_pw, mock_scrape_page):
        mock_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_scrape_page.return_value = "Full article content here."

        articles = [_make_article()]
        result, has_fallbacks = await scrape_full_texts(articles, cookies=[])
        assert result[0].full_text == "Full article content here."
        assert has_fallbacks is False
        mock_scrape_page.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.scraper._scrape_page", new_callable=AsyncMock)
    @patch("src.scraper.async_playwright")
    async def test_falls_back_to_summary_on_failure(self, mock_pw, mock_scrape_page):
        mock_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_scrape_page.side_effect = Exception("Cookie expired")

        articles = [_make_article()]
        result, has_fallbacks = await scrape_full_texts(articles, cookies=[])
        assert result[0].full_text == articles[0].summary
        assert has_fallbacks is True
