import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.models import Article, AnalyzedArticle
from src.analyzer import analyze_articles


def _make_article(title="Arsenal dominate", full_text="Full analysis...") -> Article:
    return Article(
        title=title, link="https://example.com/1", summary="Summary",
        published=datetime(2026, 2, 15, tzinfo=timezone.utc), full_text=full_text,
    )


class TestAnalyzeArticles:
    def test_returns_analyzed_articles(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps([{
            "title_cn": "阿森纳主导比赛",
            "title_original": "Arsenal dominate",
            "article_type": "深度分析",
            "importance": 5,
            "overview": "阿森纳在比赛中展现了统治力。",
            "detail": "详细的战术分析内容...",
            "key_people_and_data": "萨卡：2球1助攻",
            "impact": "阿森纳升至榜首。",
            "link": "https://example.com/1",
        }])
        articles = [_make_article()]
        result = analyze_articles(articles, mock_llm)
        assert len(result) == 1
        assert result[0].title_cn == "阿森纳主导比赛"
        assert result[0].importance == 5

    def test_handles_malformed_llm_response(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "This is not JSON"
        articles = [_make_article()]
        result = analyze_articles(articles, mock_llm)
        assert result == []
