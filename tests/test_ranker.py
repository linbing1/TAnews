from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.models import Article
from src.ranker import rank_articles


def _make_articles(n: int) -> list[Article]:
    return [
        Article(
            title=f"Article {i}",
            link=f"https://example.com/{i}",
            summary=f"Summary of article {i}",
            published=datetime(2026, 2, 15, i, 0, 0, tzinfo=timezone.utc),
        )
        for i in range(n)
    ]


class TestRankArticles:
    def test_returns_top_n(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "2,0,4"
        articles = _make_articles(6)
        result = rank_articles(articles, mock_llm, top_n=3)
        assert len(result) == 3
        assert result[0].title == "Article 2"
        assert result[1].title == "Article 0"
        assert result[2].title == "Article 4"

    def test_fewer_than_top_n_returns_all(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "1,0"
        articles = _make_articles(2)
        result = rank_articles(articles, mock_llm, top_n=5)
        assert len(result) == 2

    def test_skips_llm_when_articles_lte_top_n(self):
        mock_llm = MagicMock()
        articles = _make_articles(3)
        result = rank_articles(articles, mock_llm, top_n=5)
        assert len(result) == 3
        mock_llm.complete.assert_not_called()

    def test_sends_date_and_summary_to_llm(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "0,1"
        articles = [
            Article(
                title="Arsenal win",
                link="https://example.com/1",
                summary="Saka scores twice in dominant display",
                published=datetime(2026, 2, 16, 10, 0, 0, tzinfo=timezone.utc),
            ),
            Article(
                title="Liverpool draw",
                link="https://example.com/2",
                summary="Liverpool draw",
                published=datetime(2026, 2, 15, 8, 0, 0, tzinfo=timezone.utc),
            ),
        ]
        rank_articles(articles, mock_llm, top_n=1)

        call_args = mock_llm.complete.call_args
        user_prompt = call_args[0][1]
        # Date should appear in the prompt
        assert "2026-02-16" in user_prompt
        # Non-duplicate summary should appear
        assert "Saka scores twice" in user_prompt
