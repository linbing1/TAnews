import logging

import edge_tts

logger = logging.getLogger(__name__)


async def _synthesize_mp3(script: str, output_path: str, voice: str) -> None:
    logger.info("Synthesizing audio to %s", output_path)
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(output_path)
