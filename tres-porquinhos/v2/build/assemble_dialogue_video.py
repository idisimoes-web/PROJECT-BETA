#!/usr/bin/env python3
"""Assemble 2D dialogue video with speaker bust + nameplate + captions."""
from __future__ import annotations

import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "audio"
IMG = ROOT / "images" / "scenes"
CHARS = ROOT / "images" / "chars"
OUT = ROOT / "output"
BUILD = ROOT / "build"
ASSETS = Path("/opt/cursor/artifacts/assets")

SCENE_FILES = {
    "hook": "v2_hook.jpg",
    "titulo": "v2_titulo.jpg",
    "fazenda": "v2_fazenda.jpg",
    "pipoca_constroi": "v2_pipoca_constroi.jpg",
    "tambor_constroi": "v2_tambor_constroi.jpg",
    "tijolinho_constroi": "v2_tijolinho_constroi.jpg",
    "tijolinho_pronta": "v2_tijolinho_pronta.jpg",
    "pergunta1": "v2_pergunta1.jpg",
    "brincadeira": "v2_brincadeira.jpg",
    "lobo_aparece": "v2_lobo_aparece.jpg",
    "casa_palha": "v2_casa_palha.jpg",
    "palha_cai": "v2_palha_cai.jpg",
    "pergunta2": "v2_pergunta2.jpg",
    "casa_madeira": "v2_casa_madeira.jpg",
    "madeira_cai": "v2_madeira_cai.jpg",
    "fuga_tijolos": "v2_fuga_tijolos.jpg",
    "pergunta3": "v2_pergunta3.jpg",
    "tijolos_resistem": "v2_tijolos_resistem.jpg",
    "lobo_teima": "v2_lobo_teima.jpg",
    "chamine": "v2_chamine.jpg",
    "chamine_queda": "v2_chamine_queda.jpg",
    "final": "v2_final.jpg",
    "moral": "v2_moral.jpg",
    "cta": "v2_cta.jpg",
}

BUST = {
    "PIPOCA": "v2_bust_pipoca.jpg",
    "TAMBOR": "v2_bust_tambor.jpg",
    "TIJOLINHO": "v2_bust_tijolinho.jpg",
    "LOBO": "v2_bust_lobo.jpg",
    "MAMAE": "v2_bust_mamae.jpg",
    "NARRADOR": "v2_bust_narrador.jpg",
}

NAME_COLOR = {
    "PIPOCA": "0xF2C94C",
    "TAMBOR": "0x2F80ED",
    "TIJOLINHO": "0xEB5757",
    "LOBO": "0x4F5D4A",
    "MAMAE": "0xF2994A",
    "NARRADOR": "0x27AE60",
}

DISPLAY_NAME = {
    "PIPOCA": "PIPOCA",
    "TAMBOR": "TAMBOR",
    "TIJOLINHO": "TIJOLINHO",
    "LOBO": "LOBO MAU",
    "MAMAE": "MAMÃE",
    "NARRADOR": "NARRADOR",
}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


def sync_assets() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    CHARS.mkdir(parents=True, exist_ok=True)
    for name in list(SCENE_FILES.values()) + list(BUST.values()) + ["v2_charsheet.jpg"]:
        src = ASSETS / name
        if src.exists():
            dest_dir = CHARS if "bust" in name or "charsheet" in name else IMG
            if name == "v2_charsheet.jpg":
                dest_dir = CHARS
            dest = dest_dir / name
            if not dest.exists():
                run(["cp", str(src), str(dest)])


def make_music(path: Path, duration: float, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    freqs = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63]
    audio = np.zeros_like(t)
    note = 0.55
    for i in range(int(duration / note) + 2):
        f = freqs[i % len(freqs)]
        start = int(i * note * sr)
        end = min(len(t), start + int(note * sr))
        if start >= len(t):
            break
        tt = np.arange(end - start) / sr
        env = np.sin(np.pi * np.clip(tt / note, 0, 1))
        audio[start:end] += 0.035 * env * np.sin(2 * np.pi * f * tt)
    fade = int(1.2 * sr)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    pcm = (np.clip(audio, -0.9, 0.9) * 32767).astype(np.int16)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def wrap(text: str, width: int = 36) -> str:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = " ".join(cur + [w])
        if len(trial) > width and cur:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return "\\N".join(lines[:3])


def write_ass(path: Path, items: list[dict], vertical: bool = False) -> None:
    resx, resy = (1080, 1920) if vertical else (1920, 1080)
    fontsize = 44 if vertical else 48
    margin_v = 280 if vertical else 60
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {resx}
PlayResY: {resy}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,4,0,2,70,70,{margin_v},1
Style: NameTag,DejaVu Sans Bold,{fontsize - 4},&H00000000,&H000000FF,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,7,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def ts(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    events = []
    for it in items:
        body = wrap(it["text"], 28 if vertical else 40)
        events.append(
            f"Dialogue: 0,{ts(it['start'])},{ts(it['end'])},Default,,0,0,0,,{body}"
        )
        # name tag near top-left
        events.append(
            f"Dialogue: 1,{ts(it['start'])},{ts(it['end'])},NameTag,,0,0,0,,{DISPLAY_NAME[it['who']]}"
        )
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def render_line_clip(
    scene_img: Path,
    bust_img: Path,
    duration: float,
    who: str,
    out: Path,
    idx: int,
    size: str,
) -> None:
    frames = max(int(duration * 30), 1)
    zoom = (
        f"min(1.08,1+0.03*on/{frames})"
        if idx % 2 == 0
        else f"if(eq(on,1),1.08,max(1.0,1.08-0.03*on/{frames}))"
    )
    color = NAME_COLOR[who]
    name = DISPLAY_NAME[who]

    if size == "yt":
        w, h = 1920, 1080
        # scene with ken burns, bust lower-left, nameplate bar (fixed coords for drawbox)
        vf = (
            f"[0:v]scale=2100:1180:force_original_aspect_ratio=increase,crop=2100:1180,"
            f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30[bg];"
            f"[1:v]scale=320:320[bust];"
            f"[bg][bust]overlay=40:720,"
            f"drawbox=x=40:y=1010:w=360:h=50:color={color}@0.95:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{name}':fontcolor=white:fontsize=28:x=55:y=1020,"
            f"format=yuv420p"
        )
    else:
        w, h = 1080, 1920
        still = out.with_suffix(".still.jpg")
        run([
            "ffmpeg", "-y", "-i", str(scene_img),
            "-filter_complex",
            (
                f"[0:v]split=2[a][b];"
                f"[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                f"gblur=sigma=26[bg];"
                f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
            ),
            "-frames:v", "1", "-update", "1", str(still),
        ])
        scene_img = still
        vf = (
            f"[0:v]scale=1200:2133,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={w}x{h}:fps=30[bg];"
            f"[1:v]scale=280:280[bust];"
            f"[bg][bust]overlay=400:1420,"
            f"drawbox=x=380:y=1720:w=320:h=50:color={color}@0.95:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{name}':fontcolor=white:fontsize=26:x=430:y=1730,"
            f"format=yuv420p"
        )

    run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(scene_img),
        "-loop", "1", "-i", str(bust_img),
        "-filter_complex", vf,
        "-t", f"{duration:.3f}",
        "-an", "-pix_fmt", "yuv420p",
        str(out),
    ])
    if size != "yt":
        Path(str(out.with_suffix(".still.jpg"))).unlink(missing_ok=True)


def build(size: str) -> Path:
    sync_assets()
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    timeline = json.loads((AUDIO / "timeline.json").read_text(encoding="utf-8"))
    items = timeline["items"]
    clips_dir = BUILD / f"clips_{size}"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips = []

    for idx, it in enumerate(items):
        scene = IMG / SCENE_FILES[it["scene"]]
        bust = CHARS / BUST[it["who"]]
        clip = clips_dir / f"{it['id']}.mp4"
        print(f"[{size}] {it['id']} {it['who']} / {it['scene']} ({it['duration']:.2f}s)")
        render_line_clip(scene, bust, it["duration"], it["who"], clip, idx, size)
        clips.append(clip)

    silent = BUILD / f"video_{size}_silent.mp4"
    lst = BUILD / f"concat_{size}.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])

    music = BUILD / "music_bed.wav"
    if not music.exists():
        make_music(music, timeline["duration"] + 2)

    mixed = BUILD / f"audio_{size}.m4a"
    run([
        "ffmpeg", "-y",
        "-i", str(AUDIO / "dialogue_full.mp3"),
        "-stream_loop", "-1", "-i", str(music),
        "-filter_complex",
        (
            f"[1:a]volume=0.08,afade=t=in:st=0:d=1,afade=t=out:st={timeline['duration']-2}:d=2[bed];"
            f"[0:a]volume=1.1[nar];"
            f"[nar][bed]amix=inputs=2:duration=first:dropout_transition=0,"
            f"aformat=sample_rates=48000:channel_layouts=stereo,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]"
        ),
        "-map", "[aout]", "-t", f"{timeline['duration']:.3f}",
        "-c:a", "aac", "-b:a", "192k",
        str(mixed),
    ])

    # force 48k after loudnorm quirks
    mixed48 = BUILD / f"audio_{size}_48k.m4a"
    run([
        "ffmpeg", "-y", "-i", str(mixed),
        "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k",
        str(mixed48),
    ])

    ass = BUILD / f"subs_{size}.ass"
    write_ass(ass, items, vertical=(size != "yt"))
    ass_esc = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    final = OUT / (
        "tres_porquinhos_2d_youtube_16x9.mp4" if size == "yt"
        else "tres_porquinhos_2d_tiktok_9x16.mp4"
    )
    print(f"[{size}] mux -> {final.name}")
    run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(mixed48),
        "-vf", f"subtitles={ass_esc}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(final),
    ])
    print(f"[{size}] DONE {probe(final):.2f}s")
    return final


def export_audio_mp3() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    run(["cp", str(AUDIO / "dialogue_full.mp3"), str(OUT / "dialogo_completo_multivozes.mp3")])
    # per-character highlight reel optional skipped


def main() -> None:
    export_audio_mp3()
    yt = build("yt")
    tk = build("tk")
    for p in (yt, tk):
        print("VERIFY", p.name, probe(p))


if __name__ == "__main__":
    main()
