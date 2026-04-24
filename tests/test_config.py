from datetime import date, datetime, timezone
from unittest.mock import patch

from src.config import beijing_today, get_config


class TestGetConfig:
    def test_audio_defaults(self, monkeypatch):
        monkeypatch.delenv("AUDIO_ENABLED", raising=False)
        monkeypatch.delenv("AUDIO_VOICE", raising=False)
        monkeypatch.delenv("AUDIO_KEEP_RELEASES", raising=False)

        config = get_config()

        assert config["audio_enabled"] is True
        assert config["audio_voice"] == "zh-CN-YunjianNeural"
        assert config["audio_keep_releases"] == 7

    def test_audio_empty_strings_use_defaults(self, monkeypatch):
        monkeypatch.setenv("AUDIO_ENABLED", "")
        monkeypatch.setenv("AUDIO_VOICE", "")
        monkeypatch.setenv("AUDIO_KEEP_RELEASES", "")

        config = get_config()

        assert config["audio_enabled"] is True
        assert config["audio_voice"] == "zh-CN-YunjianNeural"
        assert config["audio_keep_releases"] == 7

    def test_audio_enabled_false_lowercase(self, monkeypatch):
        monkeypatch.setenv("AUDIO_ENABLED", "false")

        config = get_config()

        assert config["audio_enabled"] is False

    def test_audio_enabled_false_uppercase(self, monkeypatch):
        monkeypatch.setenv("AUDIO_ENABLED", "FALSE")

        config = get_config()

        assert config["audio_enabled"] is False

    def test_audio_voice_override(self, monkeypatch):
        monkeypatch.setenv("AUDIO_VOICE", "en-US-GuyNeural")

        config = get_config()

        assert config["audio_voice"] == "en-US-GuyNeural"

    def test_audio_voice_empty_string_uses_default(self, monkeypatch):
        monkeypatch.setenv("AUDIO_VOICE", "")

        config = get_config()

        assert config["audio_voice"] == "zh-CN-YunjianNeural"

    def test_audio_keep_releases_override(self, monkeypatch):
        monkeypatch.setenv("AUDIO_KEEP_RELEASES", "14")

        config = get_config()

        assert config["audio_keep_releases"] == 14

    def test_audio_keep_releases_empty_string_uses_default(self, monkeypatch):
        monkeypatch.setenv("AUDIO_KEEP_RELEASES", "")

        config = get_config()

        assert config["audio_keep_releases"] == 7


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
