import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from src.audio_synth import (
    _create_or_update_release,
    _synthesize_mp3,
    prune_old_releases,
)


@pytest.mark.asyncio
async def test_synthesize_mp3_uses_edge_tts_to_save_output(tmp_path):
    out = tmp_path / "digest.mp3"
    communicate = AsyncMock()
    communicate.save = AsyncMock()

    with patch("src.audio_synth.edge_tts.Communicate", return_value=communicate) as mock_communicate:
        await _synthesize_mp3("hello world", str(out), voice="zh-CN-YunjianNeural")

    mock_communicate.assert_called_once_with("hello world", "zh-CN-YunjianNeural")
    communicate.save.assert_awaited_once_with(str(out))


def test_create_or_update_release_creates_new_release():
    with patch("src.audio_synth.subprocess.run") as mock_run:
        _create_or_update_release(
            "audio-digest-2026-04-23",
            "/tmp/audio-digest-2026-04-23.mp3",
            "owner/repo",
            "Audio digest audio-digest-2026-04-23",
        )

    assert mock_run.call_count == 1
    assert mock_run.call_args.kwargs == {"check": True, "capture_output": True, "text": True}
    assert mock_run.call_args.args[0] == [
        "gh",
        "release",
        "create",
        "audio-digest-2026-04-23",
        "/tmp/audio-digest-2026-04-23.mp3",
        "--repo",
        "owner/repo",
        "--title",
        "Audio digest audio-digest-2026-04-23",
        "--notes",
        "Auto-generated audio digest for audio-digest-2026-04-23",
    ]


def test_create_or_update_release_uploads_when_release_already_exists():
    error = subprocess.CalledProcessError(
        1,
        ["gh", "release", "create"],
        stderr="release already exists",
    )

    with patch("src.audio_synth.subprocess.run", side_effect=[error, None]) as mock_run:
        _create_or_update_release(
            "audio-digest-2026-04-23",
            "/tmp/audio-digest-2026-04-23.mp3",
            "owner/repo",
            "Audio digest audio-digest-2026-04-23",
        )

    assert mock_run.call_count == 2
    assert mock_run.call_args_list[1].args[0] == [
        "gh",
        "release",
        "upload",
        "audio-digest-2026-04-23",
        "/tmp/audio-digest-2026-04-23.mp3",
        "--repo",
        "owner/repo",
        "--clobber",
    ]


def test_create_or_update_release_reraises_unexpected_create_error():
    error = subprocess.CalledProcessError(
        1,
        ["gh", "release", "create"],
        stderr="permission denied",
    )

    with patch("src.audio_synth.subprocess.run", side_effect=error):
        with pytest.raises(subprocess.CalledProcessError):
            _create_or_update_release(
                "audio-digest-2026-04-23",
                "/tmp/audio-digest-2026-04-23.mp3",
                "owner/repo",
                "Audio digest audio-digest-2026-04-23",
            )


def test_prune_old_releases_deletes_releases_beyond_keep_count():
    list_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=(
            '[{"tagName":"audio-digest-2026-04-23","createdAt":"2026-04-23T00:00:00Z"},'
            '{"tagName":"audio-digest-2026-04-22","createdAt":"2026-04-22T00:00:00Z"},'
            '{"tagName":"audio-digest-2026-04-21","createdAt":"2026-04-21T00:00:00Z"}]'
        ),
        stderr="",
    )
    delete_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    with patch("src.audio_synth.subprocess.run", side_effect=[list_result, delete_result]) as mock_run:
        prune_old_releases("audio-digest", keep=2, repo="owner/repo")

    assert mock_run.call_count == 2
    assert mock_run.call_args_list[0].args[0] == [
        "gh",
        "release",
        "list",
        "--repo",
        "owner/repo",
        "--json",
        "tagName,createdAt",
        "--limit",
        "100",
    ]
    assert mock_run.call_args_list[1].args[0] == [
        "gh",
        "release",
        "delete",
        "audio-digest-2026-04-21",
        "--repo",
        "owner/repo",
        "--cleanup-tag",
        "--yes",
    ]


def test_prune_old_releases_keeps_everything_under_limit():
    list_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='[{"tagName":"audio-digest-2026-04-23","createdAt":"2026-04-23T00:00:00Z"}]',
        stderr="",
    )

    with patch("src.audio_synth.subprocess.run", return_value=list_result) as mock_run:
        prune_old_releases("audio-digest", keep=2, repo="owner/repo")

    mock_run.assert_called_once()


def test_prune_old_releases_ignores_other_prefixes():
    list_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=(
            '[{"tagName":"other-2026-04-24","createdAt":"2026-04-24T00:00:00Z"},'
            '{"tagName":"audio-digest-2026-04-23","createdAt":"2026-04-23T00:00:00Z"},'
            '{"tagName":"audio-digest-2026-04-22","createdAt":"2026-04-22T00:00:00Z"}]'
        ),
        stderr="",
    )
    delete_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    with patch("src.audio_synth.subprocess.run", side_effect=[list_result, delete_result]) as mock_run:
        prune_old_releases("audio-digest", keep=1, repo="owner/repo")

    assert mock_run.call_count == 2
    assert mock_run.call_args_list[1].args[0][3] == "audio-digest-2026-04-22"


def test_prune_old_releases_swallows_list_error_with_warning():
    error = subprocess.CalledProcessError(1, ["gh", "release", "list"], stderr="boom")

    with (
        patch("src.audio_synth.subprocess.run", side_effect=error),
        patch("src.audio_synth.logger.warning") as mock_warning,
    ):
        prune_old_releases("audio-digest", keep=2, repo="owner/repo")

    mock_warning.assert_called_once()


def test_prune_old_releases_swallows_individual_delete_errors():
    list_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=(
            '[{"tagName":"audio-digest-2026-04-23","createdAt":"2026-04-23T00:00:00Z"},'
            '{"tagName":"audio-digest-2026-04-22","createdAt":"2026-04-22T00:00:00Z"},'
            '{"tagName":"audio-digest-2026-04-21","createdAt":"2026-04-21T00:00:00Z"}]'
        ),
        stderr="",
    )
    delete_error = subprocess.CalledProcessError(1, ["gh", "release", "delete"], stderr="nope")
    delete_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    with (
        patch("src.audio_synth.subprocess.run", side_effect=[list_result, delete_error, delete_result]) as mock_run,
        patch("src.audio_synth.logger.warning") as mock_warning,
    ):
        prune_old_releases("audio-digest", keep=1, repo="owner/repo")

    assert mock_run.call_count == 3
    mock_warning.assert_called_once()
