#!/usr/bin/env python3
"""Cut the vertical master into 3 cliffhanger parts for TikTok series posting."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "audio"
OUT = ROOT / "output"
SCENES = json.loads((ROOT / "script" / "cenas.json").read_text(encoding="utf-8"))
SRC = OUT / "os_tres_porquinhos_tiktok_9x16.mp4"


def probe(path: Path) -> float:
    return float(
        subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(path),
            ],
            text=True,
        ).strip()
    )


def main() -> None:
    # Build cumulative starts
    t = 0.0
    ends = {}
    for sc in SCENES:
        t += probe(AUDIO / f"{sc['id']}.mp3")
        ends[sc["id"]] = t

    parts = [
        ("parte1_palha.mp4", 0.0, ends["s10"], "Parte 1 — A casa de palha"),
        ("parte2_madeira.mp4", ends["s10"], ends["s13"], "Parte 2 — A casa de madeira"),
        ("parte3_tijolos.mp4", ends["s13"], ends["s18"], "Parte 3 — A casa de tijolos"),
    ]
    for name, start, end, _label in parts:
        dur = end - start
        out = OUT / name
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(SRC),
                "-t", f"{dur:.3f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(out),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"{name}: {dur:.1f}s ({start:.1f}->{end:.1f})")


if __name__ == "__main__":
    main()
