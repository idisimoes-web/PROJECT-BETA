#!/usr/bin/env python3
"""Generate per-line dialogue with strongly distinct character voices."""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "script" / "episodio.json"
AUDIO = ROOT / "audio"
LINES = AUDIO / "lines"
SAMPLES = AUDIO / "samples"


async def synth(text: str, voice: str, rate: str, pitch: str, out: Path) -> None:
    # Normalize punctuation that occasionally breaks Edge-TTS
    clean = (
        text.replace("…", "...")
        .replace("–", "-")
        .replace("—", "-")
    )
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            await edge_tts.Communicate(clean, voice, rate=rate, pitch=pitch).save(str(out))
            if out.exists() and out.stat().st_size > 500:
                return
            raise RuntimeError("empty audio file")
        except Exception as err:  # noqa: BLE001 — retry transient Edge-TTS failures
            last_err = err
            await asyncio.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"TTS failed for {voice} pitch={pitch}: {last_err}")


def apply_fx(src: Path, dest: Path, fx: str | None) -> None:
    if fx == "wolf":
        # Extra deepen + slight bass so Lobo ≠ Tambor (same base voice)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-af",
                "asetrate=24000*0.82,aresample=24000,atempo=1.0/0.82,bass=g=7:f=110,volume=1.15",
                str(dest),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ar", "24000", "-ac", "1", str(dest)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


async def main() -> None:
    data = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voices = data["voices"]
    LINES.mkdir(parents=True, exist_ok=True)
    SAMPLES.mkdir(parents=True, exist_ok=True)
    timeline, concat, t = [], [], 0.0

    # Per-character showcase samples
    sample_lines = {
        "PIPOCA": "Olá! Eu sou o Pipoca! Quero uma casa bem rápida pra brincar!",
        "TAMBOR": "Eu sou o Tambor! Vou construir de madeira! Tóc, tóc, tóc!",
        "TIJOLINHO": "Eu sou o Tijolinho. Quero uma casa firme… de tijolos.",
        "MAMAE": "Meus filhos queridos… paciência e carinho fazem a melhor casa.",
        "LOBO": "Eu sou o Lobo Mau! Vou assoprar a casinha! Fuuuuu!",
    }
    for who, text in sample_lines.items():
        cfg = voices[who]
        raw = SAMPLES / f"{who.lower()}_raw.mp3"
        out = SAMPLES / f"{who.lower()}.mp3"
        print(f"SAMPLE {who}")
        await synth(text, cfg["voice"], cfg["rate"], cfg["pitch"], raw)
        apply_fx(raw, out, cfg.get("fx"))
        raw.unlink(missing_ok=True)

    for shot in data["shots"]:
        who = shot["who"]
        cfg = voices[who]
        raw = LINES / f"{shot['id']}_raw.mp3"
        speech = LINES / f"{shot['id']}_speech.mp3"
        silence = LINES / f"{shot['id']}_silence.wav"
        merged = LINES / f"{shot['id']}.mp3"
        print(f"{shot['id']} {who}")
        await synth(shot["text"], cfg["voice"], cfg["rate"], cfg["pitch"], raw)
        apply_fx(raw, speech, cfg.get("fx"))
        raw.unlink(missing_ok=True)
        pause = float(shot.get("pause", 0.2))
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anullsrc=r=24000:cl=mono",
                "-t", f"{pause}", str(silence),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(speech), "-i", str(silence),
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                "-map", "[a]", str(merged),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        dur = float(
            subprocess.check_output(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0", str(merged),
                ],
                text=True,
            ).strip()
        )
        timeline.append(
            {
                **shot,
                "start": t,
                "end": t + max(dur - pause, 0.35),
                "duration": dur,
            }
        )
        concat.append(f"file '{merged.resolve()}'")
        t += dur

    (AUDIO / "timeline.json").write_text(
        json.dumps({"duration": t, "items": timeline}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (AUDIO / "concat.txt").write_text("\n".join(concat) + "\n", encoding="utf-8")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(AUDIO / "concat.txt"), "-c", "copy",
            str(AUDIO / "dialogue_full.mp3"),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Named voice reel for QA
    reel_parts = []
    for who in ["PIPOCA", "TAMBOR", "TIJOLINHO", "MAMAE", "LOBO"]:
        label = SAMPLES / f"label_{who.lower()}.mp3"
        await synth(who.title(), "pt-BR-AntonioNeural", "+0%", "+0Hz", label)
        reel_parts.append(label)
        reel_parts.append(SAMPLES / f"{who.lower()}.mp3")
    reel_txt = SAMPLES / "reel_concat.txt"
    reel_txt.write_text("".join(f"file '{p.resolve()}'\n" for p in reel_parts), encoding="utf-8")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(reel_txt), "-c", "copy",
            str(AUDIO / "vozes_amostra_5.mp3"),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"FULL_DURATION_SEC={t:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
