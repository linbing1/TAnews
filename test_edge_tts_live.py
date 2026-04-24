"""Manual smoke test for Edge-TTS voice selection and MP3 output.

Usage:
    python test_edge_tts_live.py
    python test_edge_tts_live.py en-US-GuyNeural
"""

import asyncio
import sys

import edge_tts

SAMPLE_TEXT = (
    "4月23日英超晨报，Arsenal 二比一击败 Chelsea，"
    "Liverpool 与 Tottenham 战成三比三。"
    "Saka、Son 和 Palmer 都在 headlines 里。"
)


async def main(voice: str) -> None:
    output_path = "./edge_tts_preview.mp3"
    print(f"Synthesizing preview with voice: {voice}")
    communicate = edge_tts.Communicate(SAMPLE_TEXT, voice)
    await communicate.save(output_path)
    print(f"Wrote preview to {output_path}")


if __name__ == "__main__":
    selected_voice = sys.argv[1] if len(sys.argv) > 1 else "zh-CN-YunjianNeural"
    asyncio.run(main(selected_voice))
