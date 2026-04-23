import json
import logging
import os
import subprocess
from datetime import date
from urllib.parse import urlencode

try:
    import edge_tts
except ImportError as exc:
    edge_tts = None
    _EDGE_TTS_IMPORT_ERROR = exc
else:
    _EDGE_TTS_IMPORT_ERROR = None

logger = logging.getLogger(__name__)


async def _synthesize_mp3(script: str, output_path: str, voice: str) -> None:
    if edge_tts is None:
        raise ModuleNotFoundError("edge_tts is required for audio synthesis") from _EDGE_TTS_IMPORT_ERROR

    logger.info("Synthesizing audio to %s", output_path)
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(output_path)


def _build_release_asset_url(repo: str, tag: str, filename: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{filename}"


def _build_player_page_url(repo: str, asset_url: str, title: str) -> str:
    owner, name = repo.split("/", 1)
    if name.lower() == f"{owner.lower()}.github.io":
        base_url = f"https://{owner}.github.io"
    else:
        base_url = f"https://{owner}.github.io/{name}"

    query = urlencode({"src": asset_url, "title": title})
    return f"{base_url}/audio-player.html?{query}"


def _create_or_update_release(tag: str, asset_path: str, repo: str, title: str) -> None:
    try:
        logger.info("Creating release %s", tag)
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                asset_path,
                "--repo",
                repo,
                "--title",
                title,
                "--notes",
                f"Auto-generated audio digest for {tag}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        if "already exists" not in stderr:
            raise

        logger.info("Release %s exists; uploading asset with clobber", tag)
        subprocess.run(
            [
                "gh",
                "release",
                "upload",
                tag,
                asset_path,
                "--repo",
                repo,
                "--clobber",
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def prune_old_releases(tag_prefix: str, keep: int, repo: str) -> None:
    try:
        result = subprocess.run(
            [
                "gh",
                "release",
                "list",
                "--repo",
                repo,
                "--json",
                "tagName,createdAt",
                "--limit",
                "100",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        releases = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        logger.warning("Failed to list releases for pruning: %s", exc)
        return

    matching_releases = [
        release
        for release in releases
        if release["tagName"].startswith(f"{tag_prefix}-")
    ]
    matching_releases.sort(key=lambda release: release["createdAt"], reverse=True)

    for release in matching_releases[keep:]:
        tag = release["tagName"]
        try:
            subprocess.run(
                [
                    "gh",
                    "release",
                    "delete",
                    tag,
                    "--repo",
                    repo,
                    "--cleanup-tag",
                    "--yes",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.warning("Failed to delete old release %s: %s", tag, exc)


async def synthesize_and_upload(
    script: str,
    today: date,
    voice: str = "zh-CN-YunjianNeural",
    tag_prefix: str = "audio-digest",
    repo: str | None = None,
    keep: int = 7,
) -> str:
    if keep < 1:
        raise ValueError("keep must be at least 1")

    repo = repo or os.getenv("GITHUB_REPOSITORY")
    if not repo:
        raise ValueError("repo not provided and GITHUB_REPOSITORY env is empty")

    tag = f"{tag_prefix}-{today.isoformat()}"
    filename = f"{tag}.mp3"
    mp3_path = f"/tmp/{filename}"

    await _synthesize_mp3(script, mp3_path, voice)

    title = f"Audio digest {tag}"
    _create_or_update_release(tag, mp3_path, repo, title)

    try:
        prune_old_releases(tag_prefix, keep, repo)
    except Exception as exc:
        logger.warning("Unexpected prune_old_releases failure: %s", exc)

    asset_url = _build_release_asset_url(repo, tag, filename)
    return _build_player_page_url(repo, asset_url, title)
