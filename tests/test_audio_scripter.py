from datetime import date
from unittest.mock import MagicMock

import pytest

from src.models import AnalyzedArticle
from src.audio_scripter import build_audio_script


def _make_article(title_cn="阿森纳主导比赛", title_original="Arsenal dominate") -> AnalyzedArticle:
    return AnalyzedArticle(
        title_cn=title_cn,
        title_original=title_original,
        article_type="深度分析",
        importance=5,
        overview="阿森纳在比赛中展现了统治力。",
        detail="详细的战术分析内容。",
        link="https://example.com/1",
    )


class TestBuildAudioScript:
    def test_raises_for_empty_articles(self):
        llm = MagicMock()

        with pytest.raises(ValueError, match="no articles"):
            build_audio_script([], llm, date(2026, 4, 23))

    def test_calls_llm_with_expected_prompt_contract(self):
        llm = MagicMock()
        llm.complete.return_value = "口播稿"
        articles = [
            _make_article(title_cn="阿森纳主导比赛", title_original="Arsenal dominate"),
            _make_article(title_cn="切尔西扳平", title_original="Chelsea draw"),
        ]

        build_audio_script(articles, llm, date(2026, 4, 23), title_prefix="午间快报")

        llm.complete.assert_called_once()
        system_text, user_text = llm.complete.call_args[0]
        assert "开场" in system_text
        assert "转场" in system_text
        assert "结尾" in system_text
        assert "每篇文章 500-700" in system_text
        assert "通用中文译名" in system_text
        assert "冷门人名/球队若确实没有通用中文译名再保留英文" in system_text
        assert "不要使用间隔号" in system_text
        assert "不要使用 Markdown" in system_text
        assert "title_prefix: 午间快报" in user_text
        assert "year: 2026" in user_text
        assert "month: 4" in user_text
        assert "day: 23" in user_text
        assert "articles:" in user_text
        assert "- article 1" in user_text
        assert "- article 2" in user_text
        assert "title_cn: 阿森纳主导比赛" in user_text
        assert "title_original: Arsenal dominate" in user_text
        assert "title_cn: 切尔西扳平" in user_text
        assert "title_original: Chelsea draw" in user_text
        assert "article_type: 深度分析" in user_text
        assert "importance: 5" in user_text
        assert "overview: 阿森纳在比赛中展现了统治力。" in user_text
        assert "detail: 详细的战术分析内容。" in user_text
        assert "link: https://example.com/1" in user_text
        assert "key_people_and_data" not in user_text
        assert "impact" not in user_text

    def test_returns_trimmed_script(self):
        llm = MagicMock()
        llm.complete.return_value = "  口播稿正文\n"

        result = build_audio_script([_make_article()], llm, date(2026, 4, 23))

        assert result == "口播稿正文"
