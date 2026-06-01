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
_RELEASES_PAGE_SIZE = 100
_GH_TIMEOUT = 120


def _strip_markdown(text: str) -> str:
    import re
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)  # bold/italic
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)     # underscore bold/italic
    text = re.sub(r"`([^`]+)`", r"\1", text)                # inline code
    text = re.sub(r"#{1,6}\s+", "", text)                   # headings
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # list bullets
    # Drop interpuncts inside transliterated names — TTS otherwise pauses there.
    text = re.sub(r"(?<=[一-鿿])[·•・](?=[一-鿿])", "", text)
    return text


async def _synthesize_mp3(script: str, output_path: str, voice: str) -> None:
    if edge_tts is None:
        raise ModuleNotFoundError("edge_tts is required for audio synthesis") from _EDGE_TTS_IMPORT_ERROR

    clean_script = _strip_markdown(script)
    logger.info("Synthesizing audio to %s", output_path)
    communicate = edge_tts.Communicate(clean_script, voice)
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


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        timeout=_GH_TIMEOUT,
    )


def _create_or_update_release(tag: str, asset_path: str, repo: str, title: str) -> None:
    try:
        logger.info("Creating release %s", tag)
        _run_gh(
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
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        if "already exists" not in stderr:
            raise

        logger.info("Release %s exists; uploading asset with clobber", tag)
        _run_gh(
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
        )


def _list_releases(repo: str) -> list[dict]:
    releases: list[dict] = []
    page = 1

    while True:
        result = _run_gh(
            [
                "gh",
                "api",
                f"repos/{repo}/releases?per_page={_RELEASES_PAGE_SIZE}&page={page}",
            ],
        )
        page_releases = json.loads(result.stdout)
        if not isinstance(page_releases, list):
            raise ValueError("release API did not return a list")

        releases.extend(
            {
                "tagName": release["tag_name"],
                "createdAt": release["created_at"],
            }
            for release in page_releases
        )

        if len(page_releases) < _RELEASES_PAGE_SIZE:
            break
        page += 1

    return releases


def prune_old_releases(tag_prefix: str, keep: int, repo: str) -> None:
    try:
        releases = _list_releases(repo)
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
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
            _run_gh(
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
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
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
