from src.config import get_config


class TestGetConfig:
    def test_audio_defaults(self, monkeypatch):
        monkeypatch.delenv("AUDIO_ENABLED", raising=False)
        monkeypatch.delenv("AUDIO_VOICE", raising=False)
        monkeypatch.delenv("AUDIO_KEEP_RELEASES", raising=False)

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
