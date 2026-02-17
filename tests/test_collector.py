import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.collector import collect_articles, _is_premier_league, _parse_date_from_url


class TestIsPremierLeague:
    def test_matches_team_names(self):
        assert _is_premier_league("Arsenal win 3-0") is True
        assert _is_premier_league("Liverpool beat Chelsea") is True
        assert _is_premier_league("Premier League roundup") is True

    def test_rejects_non_pl(self):
        assert _is_premier_league("NBA Playoffs recap") is False
        assert _is_premier_league("Winter Olympics day 9") is False


class TestParseDateFromUrl:
    def test_extracts_date(self):
        url = "/athletic/123/2026/02/15/arsenal-win/"
        result = _parse_date_from_url(url)
        assert result == datetime(2026, 2, 15, tzinfo=timezone.utc)

    def test_returns_none_for_no_date(self):
        url = "/athletic/news/"
        result = _parse_date_from_url(url)
        assert result is None


class TestCollectArticles:
    @pytest.mark.asyncio
    @patch("src.collector.async_playwright")
    async def test_filters_premier_league_articles(self, mock_pw):
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_instance = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        async def make_link(href, text):
            link = AsyncMock()
            link.get_attribute.return_value = href
            link.inner_text.return_value = text
            link.query_selector.return_value = None
            parent = AsyncMock()
            parent.inner_text.return_value = text
            link.evaluate_handle.return_value = parent
            return link

        links = [
            await make_link("/athletic/123/2026/02/15/arsenal-win/", "Arsenal dominate in 3-0 victory"),
            await make_link("/athletic/456/2026/02/15/nba-recap/", "NBA Playoffs: Lakers win game"),
            await make_link("/athletic/789/2026/02/15/salah-goal/", "Mohamed Salah scores stunning goal"),
            await make_link("/athletic/nfl/", "NFL news"),
        ]
        mock_page.query_selector_all.return_value = links

        articles = await collect_articles("http://fake-url", cookies=[])

        assert len(articles) == 2
        titles = [a.title for a in articles]
        assert "Arsenal dominate in 3-0 victory" in titles
        assert "Mohamed Salah scores stunning goal" in titles

    @pytest.mark.asyncio
    @patch("src.collector.async_playwright")
    async def test_returns_empty_on_no_pl_articles(self, mock_pw):
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_instance = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        link = AsyncMock()
        link.get_attribute.return_value = "/athletic/123/2026/02/15/nba/"
        link.inner_text.return_value = "NBA Playoffs recap and analysis"
        link.query_selector.return_value = None
        parent = AsyncMock()
        parent.inner_text.return_value = "NBA Playoffs recap and analysis"
        link.evaluate_handle.return_value = parent
        mock_page.query_selector_all.return_value = [link]

        articles = await collect_articles("http://fake-url", cookies=[])
        assert articles == []

    @pytest.mark.asyncio
    @patch("src.collector.async_playwright")
    async def test_extracts_summary_from_parent(self, mock_pw):
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_instance = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # Simulate a link element whose parent has extra text
        link = AsyncMock()
        link.get_attribute.return_value = "/athletic/123/2026/02/15/arsenal-win/"
        link.inner_text.return_value = "Arsenal dominate in 3-0 victory"
        link.query_selector.return_value = None

        parent = AsyncMock()
        parent.inner_text.return_value = "Arsenal dominate in 3-0 victory\nSaka scores twice as Gunners go top"
        link.evaluate_handle.return_value = parent

        mock_page.query_selector_all.return_value = [link]

        articles = await collect_articles("http://fake-url", cookies=[])

        assert len(articles) == 1
        assert articles[0].summary == "Saka scores twice as Gunners go top"

    @pytest.mark.asyncio
    @patch("src.collector.async_playwright")
    async def test_extracts_comment_count_from_nowrap_span(self, mock_pw):
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_instance = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_instance
        mock_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        link = AsyncMock()
        link.get_attribute.return_value = "/athletic/123/2026/02/15/arsenal-win/"
        link.inner_text.return_value = "Arsenal dominate in 3-0 victory"

        nowrap_span = AsyncMock()
        nowrap_span.inner_text.return_value = "42"
        link.query_selector.return_value = nowrap_span

        parent = AsyncMock()
        parent.inner_text.return_value = "Arsenal dominate in 3-0 victory"
        link.evaluate_handle.return_value = parent

        mock_page.query_selector_all.return_value = [link]

        articles = await collect_articles("http://fake-url", cookies=[])

        assert len(articles) == 1
        assert articles[0].comment_count == 42
