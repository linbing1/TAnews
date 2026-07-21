import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.collector import collect_articles, is_premier_league_article, _parse_date_from_url


def _setup_playwright_page(mock_pw):
    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_browser = AsyncMock()
    mock_instance = AsyncMock()

    mock_pw.return_value.__aenter__.return_value = mock_instance
    mock_instance.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    return mock_page


def _make_link(href: str, text: str, *, parent_text: str | None = None, comment_text: str | None = None):
    link = AsyncMock()
    link.get_attribute.return_value = href
    link.inner_text.return_value = text

    if comment_text is None:
        link.query_selector.return_value = None
    else:
        nowrap_span = AsyncMock()
        nowrap_span.inner_text.return_value = comment_text
        link.query_selector.return_value = nowrap_span

    parent = AsyncMock()
    parent.inner_text.return_value = parent_text or text
    link.evaluate_handle.return_value = parent
    return link


class TestIsPremierLeague:
    def test_matches_team_names(self):
        assert is_premier_league_article("Arsenal win 3-0") is True
        assert is_premier_league_article("Liverpool beat Chelsea") is True
        assert is_premier_league_article("Premier League roundup") is True

    def test_rejects_non_pl(self):
        assert is_premier_league_article("NBA Playoffs recap") is False
        assert is_premier_league_article("Winter Olympics day 9") is False

    def test_matches_keywords_as_whole_words(self):
        assert is_premier_league_article("Tottenham star Son scores twice") is True
        assert is_premier_league_article("The key reason Spain won") is False


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
        mock_page = _setup_playwright_page(mock_pw)
        links = [
            _make_link("/athletic/123/2026/02/15/arsenal-win/", "Arsenal dominate in 3-0 victory"),
            _make_link("/athletic/456/2026/02/15/nba-recap/", "NBA Playoffs: Lakers win game"),
            _make_link("/athletic/789/2026/02/15/salah-goal/", "Mohamed Salah scores stunning goal"),
            _make_link("/athletic/nfl/", "NFL news"),
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
        mock_page = _setup_playwright_page(mock_pw)
        mock_page.query_selector_all.return_value = [
            _make_link("/athletic/123/2026/02/15/nba/", "NBA Playoffs recap and analysis")
        ]

        articles = await collect_articles("http://fake-url", cookies=[])
        assert articles == []

    @pytest.mark.asyncio
    @patch("src.collector.async_playwright")
    async def test_can_collect_without_premier_league_filter(self, mock_pw):
        mock_page = _setup_playwright_page(mock_pw)
        mock_page.query_selector_all.return_value = [
            _make_link(
                "/athletic/123/2026/06/17/champions-league-draw/",
                "Champions League draw leaves Madrid and Milan together",
            )
        ]

        articles = await collect_articles("http://fake-url", cookies=[], article_filter=None)

        assert len(articles) == 1
        assert articles[0].title == "Champions League draw leaves Madrid and Milan together"

    @pytest.mark.asyncio
    @patch("src.collector.async_playwright")
    async def test_extracts_summary_from_parent(self, mock_pw):
        mock_page = _setup_playwright_page(mock_pw)
        mock_page.query_selector_all.return_value = [
            _make_link(
                "/athletic/123/2026/02/15/arsenal-win/",
                "Arsenal dominate in 3-0 victory",
                parent_text="Arsenal dominate in 3-0 victory\nSaka scores twice as Gunners go top",
            )
        ]

        articles = await collect_articles("http://fake-url", cookies=[])

        assert len(articles) == 1
        assert articles[0].summary == "Saka scores twice as Gunners go top"

    @pytest.mark.asyncio
    @patch("src.collector.async_playwright")
    async def test_extracts_comment_count_from_nowrap_span(self, mock_pw):
        mock_page = _setup_playwright_page(mock_pw)
        mock_page.query_selector_all.return_value = [
            _make_link(
                "/athletic/123/2026/02/15/arsenal-win/",
                "Arsenal dominate in 3-0 victory",
                comment_text="42",
            )
        ]

        articles = await collect_articles("http://fake-url", cookies=[])

        assert len(articles) == 1
        assert articles[0].comment_count == 42
