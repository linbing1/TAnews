from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.collector import collect_articles

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_rss.xml"


class TestCollectArticles:
    @patch("src.collector.httpx.get")
    def test_filters_premier_league_articles(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = FIXTURE_PATH.read_text()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        articles = collect_articles("http://fake-rss", now=now)

        titles = [a.title for a in articles]
        assert len(articles) == 2
        assert any("Arsenal" in t for t in titles)
        assert any("Manchester United" in t for t in titles)
        assert not any("NBA" in t or "Lakers" in t for t in titles)
        assert not any("old article" in t for t in titles)

    @patch("src.collector.httpx.get")
    def test_returns_empty_on_no_matches(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = '<?xml version="1.0"?><rss version="2.0"><channel><item><title>NBA news</title><link>http://x</link><description>Basketball</description><pubDate>Sun, 15 Feb 2026 06:00:00 GMT</pubDate></item></channel></rss>'
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        now = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        articles = collect_articles("http://fake-rss", now=now)
        assert articles == []
