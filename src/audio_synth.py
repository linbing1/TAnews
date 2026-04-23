import json
import logging
import os
import subprocess
from datetime import date

import edge_tts

logger = logging.getLogger(__name__)


async def _synthesize_mp3(script: str, output_path: str, voice: str) -> None:
    logger.info("Synthesizing audio to %s", output_path)
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(output_path)


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

    return f"https://github.com/{repo}/releases/download/{tag}/{filename}"
