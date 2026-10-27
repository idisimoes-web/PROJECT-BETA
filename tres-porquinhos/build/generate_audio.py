#!/usr/bin/env python3
"""Generate per-scene TTS audio (pt-BR) and a full narration track."""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "script" / "cenas.json"
AUDIO = ROOT / "audio"
VOICE = "pt-BR-FranciscaNeural"
RATE = "+5%"
PITCH = "+5Hz"


async def synth(text: str, out: Path) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(str(out))


async def main() -> None:
    AUDIO.mkdir(parents=True, exist_ok=True)
    scenes = json.loads(SCENES.read_text(encoding="utf-8"))
    concat_list = AUDIO / "concat.txt"
    lines: list[str] = []

    for scene in scenes:
        sid = scene["id"]
        speech = AUDIO / f"{sid}_speech.mp3"
        pause = float(scene.get("pause_after", 0.4))
        silence = AUDIO / f"{sid}_silence.wav"
        merged = AUDIO / f"{sid}.mp3"

        print(f"TTS {sid}...")
        await synth(scene["text"], speech)

        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"anullsrc=r=24000:cl=mono",
                "-t", f"{pause}",
                str(silence),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(speech),
                "-i", str(silence),
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                "-map", "[a]",
                str(merged),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        lines.append(f"file '{merged.name}'")

    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
    full = AUDIO / "narration_full.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(full),
        ],
        check=True,
        cwd=str(AUDIO),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    probe = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(full),
        ],
        text=True,
    ).strip()
    print(f"FULL_DURATION_SEC={probe}")


if __name__ == "__main__":
    asyncio.run(main())
