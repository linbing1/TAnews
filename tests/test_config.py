from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from src.config import beijing_today, get_config


class TestGetConfig:
    @pytest.mark.parametrize(
        ("audio_enabled", "audio_voice", "audio_keep_releases"),
        [
            (None, None, None),
            ("", "", ""),
        ],
    )
    def test_audio_defaults_for_missing_or_empty_values(
        self,
        monkeypatch,
        audio_enabled,
        audio_voice,
        audio_keep_releases,
    ):
        for name, value in {
            "AUDIO_ENABLED": audio_enabled,
            "AUDIO_VOICE": audio_voice,
            "AUDIO_KEEP_RELEASES": audio_keep_releases,
        }.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)

        config = get_config()

        assert config["audio_enabled"] is True
        assert config["audio_voice"] == "zh-CN-YunjianNeural"
        assert config["audio_keep_releases"] == 7

    @pytest.mark.parametrize("value", ["false", "FALSE"])
    def test_audio_enabled_false_values(self, monkeypatch, value):
        monkeypatch.setenv("AUDIO_ENABLED", value)

        config = get_config()

        assert config["audio_enabled"] is False

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("en-US-GuyNeural", "en-US-GuyNeural"),
            ("", "zh-CN-YunjianNeural"),
        ],
    )
    def test_audio_voice_values(self, monkeypatch, value, expected):
        monkeypatch.setenv("AUDIO_VOICE", value)

        config = get_config()

        assert config["audio_voice"] == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("14", 14),
            ("", 7),
        ],
    )
    def test_audio_keep_releases_values(self, monkeypatch, value, expected):
        monkeypatch.setenv("AUDIO_KEEP_RELEASES", value)

        config = get_config()

        assert config["audio_keep_releases"] == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "https://www.nytimes.com/athletic/football/world-cup/"),
            ("", "https://www.nytimes.com/athletic/football/world-cup/"),
            ("https://example.com/world-cup/", "https://example.com/world-cup/"),
        ],
    )
    def test_world_cup_page_url_values(self, monkeypatch, value, expected):
        if value is None:
            monkeypatch.delenv("WORLD_CUP_PAGE_URL", raising=False)
        else:
            monkeypatch.setenv("WORLD_CUP_PAGE_URL", value)

        config = get_config()

        assert config["world_cup_page_url"] == expected


class FrozenUtcDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        current = cls(2026, 2, 15, 23, 30, tzinfo=timezone.utc)
        if tz is None:
            return current
        return current.astimezone(tz)


class TestBeijingToday:
    def test_uses_asia_shanghai_date(self):
        with patch("src.config.datetime", FrozenUtcDateTime):
            assert beijing_today() == date(2026, 2, 16)
