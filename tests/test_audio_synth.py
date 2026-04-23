from unittest.mock import AsyncMock, patch

import pytest

from src.audio_synth import _synthesize_mp3


@pytest.mark.asyncio
async def test_synthesize_mp3_uses_edge_tts_to_save_output(tmp_path):
    out = tmp_path / "digest.mp3"
    communicate = AsyncMock()
    communicate.save = AsyncMock()

    with patch("src.audio_synth.edge_tts.Communicate", return_value=communicate) as mock_communicate:
        await _synthesize_mp3("hello world", str(out), voice="zh-CN-YunjianNeural")

    mock_communicate.assert_called_once_with("hello world", "zh-CN-YunjianNeural")
    communicate.save.assert_awaited_once_with(str(out))
