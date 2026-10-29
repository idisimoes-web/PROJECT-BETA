#!/usr/bin/env python3
"""Synthesize per-character dialogue lines with distinct voices."""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "script" / "dialogo.json"
AUDIO = ROOT / "audio"
LINES = AUDIO / "lines"


async def synth(text: str, voice: str, rate: str, pitch: str, out: Path) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(out))


async def main() -> None:
    data = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voices = data["voices"]
    LINES.mkdir(parents=True, exist_ok=True)
    concat_lines: list[str] = []
    timeline = []
    t = 0.0

    for line in data["lines"]:
        who = line["who"]
        cfg = voices[who]
        speech = LINES / f"{line['id']}_speech.mp3"
        silence = LINES / f"{line['id']}_silence.wav"
        merged = LINES / f"{line['id']}.mp3"
        print(f"{line['id']} {who}: {line['text'][:48]}...")
        await synth(line["text"], cfg["voice"], cfg["rate"], cfg["pitch"], speech)
        pause = float(line.get("pause", 0.25))
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anullsrc=r=24000:cl=mono",
                "-t", f"{pause}",
                str(silence),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(speech), "-i", str(silence),
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                "-map", "[a]", str(merged),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        dur = float(
            subprocess.check_output(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "csv=p=0", str(merged),
                ],
                text=True,
            ).strip()
        )
        timeline.append({
            "id": line["id"],
            "who": who,
            "scene": line["scene"],
            "text": line["text"],
            "start": t,
            "end": t + max(dur - pause, 0.4),
            "duration": dur,
            "audio": str(merged.relative_to(ROOT)),
        })
        concat_lines.append(f"file '{merged.resolve()}'")
        t += dur

    (AUDIO / "timeline.json").write_text(
        json.dumps({"duration": t, "items": timeline}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    concat_path = AUDIO / "concat.txt"
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    full = AUDIO / "dialogue_full.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_path), "-c", "copy", str(full),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"FULL_DURATION_SEC={t:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
