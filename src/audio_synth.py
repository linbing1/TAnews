import json
import logging
import subprocess

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
