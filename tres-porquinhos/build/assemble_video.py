#!/usr/bin/env python3
"""Assemble YouTube 16:9 and TikTok 9:16 story videos with Ken Burns + music."""
from __future__ import annotations

import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "audio"
IMG = ROOT / "images" / "youtube"
OUT = ROOT / "output"
BUILD = ROOT / "build"
SCENES = json.loads((ROOT / "script" / "cenas.json").read_text(encoding="utf-8"))

SCENE_IMAGES = {
    "s00": "s00_hook.jpg",
    "s01": "s01_titulo.jpg",
    "s02": "s02_familia.jpg",
    "s03": "s03_pipoca.jpg",
    "s04": "s04_tambor.jpg",
    "s05": "s05_tijolinho.jpg",
    "s06": "s06_pergunta1.jpg",
    "s07": "s07_diabom.jpg",
    "s08": "s08_lobo.jpg",
    "s09": "s09_casapalha.jpg",
    "s10": "s10_palhacai.jpg",
    "s11": "s11_pergunta2.jpg",
    "s12": "s12_casamadeira.jpg",
    "s13": "s13_fuga.jpg",
    "s14": "s14_pergunta3.jpg",
    "s15": "s15_tijolos.jpg",
    "s15b": "s15b_teima.jpg",
    "s16": "s16_chamine.jpg",
    "s17": "s17_final.jpg",
    "s18": "s18_moral.jpg",
}


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_music(path: Path, duration: float, sr: int = 44100) -> None:
    """Gentle pentatonic loop for kids (no copyrighted melody)."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # C major pentatonic-ish soft pads
    freqs = [261.63, 293.66, 329.63, 392.00, 440.00, 523.25]
    pattern = [0, 2, 4, 2, 1, 3, 4, 0, 2, 4, 3, 1]
    note_len = 0.75
    audio = np.zeros_like(t)
    for i, n in enumerate(range(int(duration / note_len) + 2)):
        f = freqs[pattern[i % len(pattern)]]
        start = int(i * note_len * sr)
        end = min(len(t), start + int(note_len * sr))
        if start >= len(t):
            break
        tt = np.arange(end - start) / sr
        env = np.sin(np.pi * np.clip(tt / note_len, 0, 1)) ** 1.2
        tone = 0.045 * env * np.sin(2 * np.pi * f * tt)
        tone += 0.02 * env * np.sin(2 * np.pi * (f * 1.5) * tt)
        audio[start:end] += tone
    # soft low drone
    audio += 0.015 * np.sin(2 * np.pi * 130.81 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t))
    # fade ends
    fade = int(1.5 * sr)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    audio = np.clip(audio, -0.9, 0.9)
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def make_wind_sfx(path: Path, duration: float = 2.2, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    noise = np.random.normal(0, 1, t.shape)
    # band-ish whoosh via envelope + simple filter approx
    env = np.sin(np.pi * t / duration) ** 2
    whoosh = 0.12 * noise * env
    # add descending tone
    f = np.linspace(600, 180, len(t))
    whoosh += 0.04 * env * np.sin(2 * np.pi * np.cumsum(f) / sr)
    pcm = (np.clip(whoosh, -0.9, 0.9) * 32767).astype(np.int16)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def wrap_text(text: str, width: int = 42) -> str:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = (" ".join(cur + [w])).strip()
        if len(trial) > width and cur:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return "\\N".join(lines[:4])


def write_ass(path: Path, timeline: list[dict]) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,52,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,4,0,2,80,80,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def ts(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    events = []
    for item in timeline:
        body = wrap_text(item["text"])
        events.append(
            f"Dialogue: 0,{ts(item['start'])},{ts(item['end'])},Default,,0,0,0,,{body}"
        )
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def ken_burns_clip(image: Path, duration: float, out: Path, idx: int, size: str) -> None:
    frames = max(int(duration * 30), 1)
    # alternate gentle zoom direction
    zoom_expr = (
        f"min(1.10,1+0.035*on/{frames})"
        if idx % 2 == 0
        else f"if(eq(on,1),1.10,max(1.0,1.10-0.035*on/{frames}))"
    )

    if size == "yt":
        w, h = 1920, 1080
        vf = (
            f"scale=2000:1125:force_original_aspect_ratio=increase,"
            f"crop=2000:1125,"
            f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={w}x{h}:fps=30,format=yuv420p"
        )
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(image),
            "-vf", vf,
            "-t", f"{duration:.3f}",
            "-an",
            "-pix_fmt", "yuv420p",
            str(out),
        ])
        return

    # TikTok 9:16 — keep full illustration visible over blurred backdrop
    w, h = 1080, 1920
    # Pre-render a still vertical frame, then apply mild zoompan
    still = out.with_suffix(".still.jpg")
    run([
        "ffmpeg", "-y", "-i", str(image),
        "-filter_complex",
        (
            f"[0:v]split=2[bg0][fg0];"
            f"[bg0]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"gblur=sigma=28,eq=brightness=-0.05:saturation=1.05[bg];"
            f"[fg0]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
        ),
        "-frames:v", "1", "-update", "1",
        str(still),
    ])
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(still),
        "-vf",
        (
            f"scale=1200:2133,"
            f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={w}x{h}:fps=30,format=yuv420p"
        ),
        "-t", f"{duration:.3f}",
        "-an",
        "-pix_fmt", "yuv420p",
        str(out),
    ])
    still.unlink(missing_ok=True)


def concat_videos(clips: list[Path], out: Path) -> None:
    lst = BUILD / f"concat_{out.stem}.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", str(out),
    ])


def mix_audio(narration: Path, music: Path, wind: Path, out: Path, duration: float) -> None:
    # Place wind whooshes around straw/wood fall scenes approx via adelay later if needed.
    # Soft bed under narration.
    run([
        "ffmpeg", "-y",
        "-i", str(narration),
        "-stream_loop", "-1", "-i", str(music),
        "-i", str(wind),
        "-i", str(wind),
        "-filter_complex",
        (
            f"[1:a]volume=0.14,afade=t=in:st=0:d=1.5,afade=t=out:st={max(duration-2,0)}:d=2[bed];"
            f"[2:a]adelay=195000|195000,volume=0.35[w1];"  # ~s10 area fallback; refined below
            f"[3:a]adelay=255000|255000,volume=0.35[w2];"
            f"[0:a]volume=1.0[nar];"
            f"[nar][bed]amix=inputs=2:duration=first:dropout_transition=0[a1];"
            f"[a1][w1]amix=inputs=2:duration=first:dropout_transition=0[a2];"
            f"[a2][w2]amix=inputs=2:duration=first:dropout_transition=0,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
        ),
        "-map", "[aout]",
        "-t", f"{duration:.3f}",
        str(out),
    ])


def mix_audio_timed(narration: Path, music: Path, wind: Path, out: Path, duration: float, wind_ats: list[float]) -> None:
    inputs = ["-i", str(narration), "-stream_loop", "-1", "-i", str(music)]
    filter_parts = [
        f"[1:a]volume=0.12,afade=t=in:st=0:d=1.2,afade=t=out:st={max(duration-2,0)}:d=2[bed]",
        "[0:a]volume=1.05[nar]",
        "[nar][bed]amix=inputs=2:duration=first:dropout_transition=0[base]",
    ]
    current = "base"
    for i, at in enumerate(wind_ats):
        delay_ms = int(at * 1000)
        inputs += ["-i", str(wind)]
        idx = i + 2
        filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume=0.4[w{i}]")
        nxt = f"m{i}"
        filter_parts.append(
            f"[{current}][w{i}]amix=inputs=2:duration=first:dropout_transition=0[{nxt}]"
        )
        current = nxt
    filter_parts.append(
        f"[{current}]loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
    )
    run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[aout]",
        "-t", f"{duration:.3f}",
        str(out),
    ])


def mux(video: Path, audio: Path, ass: Path | None, out: Path, burn_subs: bool) -> None:
    if burn_subs and ass is not None:
        # escape path for ffmpeg subtitles filter
        ass_esc = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        vf = f"subtitles={ass_esc}"
        run([
            "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(out),
        ])
    else:
        run([
            "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(out),
        ])


def build_size(size: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    clips_dir = BUILD / f"clips_{size}"
    clips_dir.mkdir(parents=True, exist_ok=True)

    timeline = []
    clips = []
    t = 0.0
    wind_ats = []
    for idx, scene in enumerate(SCENES):
        sid = scene["id"]
        speech = AUDIO / f"{sid}.mp3"
        dur = probe_duration(speech)
        img = IMG / SCENE_IMAGES[sid]
        clip = clips_dir / f"{sid}.mp4"
        print(f"[{size}] Ken Burns {sid} ({dur:.2f}s)")
        ken_burns_clip(img, dur, clip, idx, size)
        clips.append(clip)
        # speech without trailing pause for subtitle end-ish
        pause = float(scene.get("pause_after", 0.4))
        timeline.append({
            "start": t,
            "end": max(t + dur - pause, t + 0.8),
            "text": scene["text"],
        })
        if sid in {"s10", "s12"}:
            wind_ats.append(t + 0.4)
        t += dur

    silent_video = BUILD / f"video_{size}_silent.mp4"
    concat_videos(clips, silent_video)

    music = BUILD / "music_bed.wav"
    wind = BUILD / "wind.wav"
    if not music.exists():
        make_music(music, t + 2)
    if not wind.exists():
        make_wind_sfx(wind)

    mixed = BUILD / f"audio_mixed_{size}.m4a"
    print(f"[{size}] Mixing audio ({t:.2f}s)")
    mix_audio_timed(AUDIO / "narration_full.mp3", music, wind, mixed, t, wind_ats)

    ass = BUILD / f"subs_{size}.ass"
    write_ass(ass, timeline)

    final = OUT / (
        "os_tres_porquinhos_youtube_16x9.mp4" if size == "yt"
        else "os_tres_porquinhos_tiktok_9x16.mp4"
    )
    print(f"[{size}] Mux + captions -> {final.name}")
    mux(silent_video, mixed, ass, final, burn_subs=True)
    print(f"[{size}] DONE duration~{t:.2f}s -> {final}")
    return final


def make_thumbnail_text() -> None:
    src = Path("/opt/cursor/artifacts/assets/thumbnail_yt.jpg")
    if not src.exists():
        return
    out = OUT / "thumbnail_youtube.jpg"
    # draw title banner
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf",
        (
            "scale=1280:720,"
            "drawbox=x=40:y=40:w=1200:h=150:color=black@0.45:t=fill,"
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            "text='Os Tr\\ês Porquinhos vs o Lobo Mau':"
            "fontcolor=white:fontsize=48:x=(w-text_w)/2:y=70,"
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            "text='Hist\\ória Infantil Completa':"
            "fontcolor=yellow:fontsize=36:x=(w-text_w)/2:y=130"
        ),
        "-frames:v", "1",
        str(out),
    ])


def main() -> None:
    make_thumbnail_text()
    yt = build_size("yt")
    tk = build_size("tk")
    for p in (yt, tk):
        d = probe_duration(p)
        print(f"VERIFY {p.name} = {d:.2f}s")


if __name__ == "__main__":
    main()
