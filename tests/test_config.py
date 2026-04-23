import os
from unittest.mock import patch

from src.config import get_config


class TestGetConfig:
    def test_audio_defaults(self):
        with patch.dict(
            os.environ,
            {
                "AUDIO_ENABLED": "false",
                "AUDIO_VOICE": "en-US-GuyNeural",
                "AUDIO_KEEP_RELEASES": "14",
                "TOP_N": "999",
                "ATHLETIC_COOKIES": "not-json",
            },
            clear=True,
        ):
            with patch.dict(os.environ, {}, clear=True):
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

    def test_audio_keep_releases_override(self, monkeypatch):
        monkeypatch.setenv("AUDIO_KEEP_RELEASES", "14")

        config = get_config()

        assert config["audio_keep_releases"] == 14
