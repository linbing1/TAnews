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
            "detail": "**战术转折：** 详细的战术分析内容。",
            "link": "https://example.com/1",
        }])
        articles = [_make_article()]
        result = analyze_articles(articles, mock_llm)
        assert len(result) == 1
        assert result[0].title_cn == "阿森纳主导比赛"
        assert result[0].importance == 5
        assert not hasattr(result[0], "key_people_and_data")
        assert not hasattr(result[0], "impact")

    def test_handles_malformed_llm_response(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "This is not JSON"
        articles = [_make_article()]
        result = analyze_articles(articles, mock_llm)
        assert result == []

    def test_coerces_string_importance_to_int(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps([{
            "title_cn": "阿森纳主导比赛",
            "title_original": "Arsenal dominate",
            "article_type": "深度分析",
            "importance": "5",
            "overview": "阿森纳在比赛中展现了统治力。",
            "detail": "**战术转折：** 详细的战术分析内容。",
            "link": "https://example.com/1",
        }])

        result = analyze_articles([_make_article()], mock_llm)

        assert len(result) == 1
        assert result[0].importance == 5
        assert isinstance(result[0].importance, int)

    def test_uses_source_link_when_llm_omits_link(self):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps([{
            "title_cn": "阿森纳主导比赛",
            "title_original": "Arsenal dominate",
            "article_type": "深度分析",
            "importance": 5,
            "overview": "阿森纳在比赛中展现了统治力。",
            "detail": "**战术转折：** 详细的战术分析内容。",
        }])
        article = _make_article()

        result = analyze_articles([article], mock_llm)

        assert len(result) == 1
        assert result[0].link == article.link


class TestAnalyzerPrompt:
    def test_system_prompt_loaded_from_file(self):
        from src.analyzer import _SYSTEM_PROMPT

        assert "**加粗段首：**" in _SYSTEM_PROMPT
        assert "保留英文原文" in _SYSTEM_PROMPT
        assert "key_people_and_data" not in _SYSTEM_PROMPT
        assert "impact" not in _SYSTEM_PROMPT
