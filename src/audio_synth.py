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
