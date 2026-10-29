#!/usr/bin/env python3
"""Build a cartoon-style talking-head episode with per-character voices + lip flap."""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "audio"
MOUTH = ROOT / "images" / "mouth"
BG = ROOT / "images" / "bg"
OUT = ROOT / "output"
BUILD = ROOT / "build"
ASSETS = Path("/opt/cursor/artifacts/assets")

CHARS = {
    "PIPOCA": ("v3_pipoca_closed.jpg", "v3_pipoca_open.jpg"),
    "TAMBOR": ("v3_tambor_closed.jpg", "v3_tambor_open.jpg"),
    "TIJOLINHO": ("v3_tijolinho_closed.jpg", "v3_tijolinho_open.jpg"),
    "MAMAE": ("v3_mamae_closed.jpg", "v3_mamae_open.jpg"),
    "LOBO": ("v3_lobo_closed.jpg", "v3_lobo_open.jpg"),
}

BG_MAP = {
    "fazenda": "v3_bg_fazenda.jpg",
    "palha": "v3_bg_palha.jpg",
    "madeira": "v3_bg_madeira.jpg",
    "tijolos": "v3_bg_tijolos.jpg",
    "tres_casas": "v3_bg_tres_casas.jpg",
    "floresta": "v3_bg_floresta.jpg",
    "grama": "v3_bg_grama.jpg",
    "caminho": "v3_bg_caminho.jpg",
    "telhado": "v3_bg_telhado.jpg",
    "lareira": "v3_bg_lareira.jpg",
    "sala": "v3_bg_sala.jpg",
    "final": "v3_bg_final.jpg",
}

NAME_COLOR = {
    "PIPOCA": "0xF2C94C",
    "TAMBOR": "0x2F80ED",
    "TIJOLINHO": "0xEB5757",
    "MAMAE": "0xF2994A",
    "LOBO": "0x4F5D4A",
}

DISPLAY = {
    "PIPOCA": "PIPOCA",
    "TAMBOR": "TAMBOR",
    "TIJOLINHO": "TIJOLINHO",
    "MAMAE": "MAMAE",
    "LOBO": "LOBO MAU",
}

FPS = 12  # classic limited cartoon lip flap


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def probe(path: Path) -> float:
    return float(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            text=True,
        ).strip()
    )


def sync_assets() -> None:
    MOUTH.mkdir(parents=True, exist_ok=True)
    BG.mkdir(parents=True, exist_ok=True)
    for a, b in CHARS.values():
        for name in (a, b):
            src = ASSETS / name
            if src.exists():
                run(["cp", "-f", str(src), str(MOUTH / name)])
    for name in BG_MAP.values():
        src = ASSETS / name
        if src.exists():
            run(["cp", "-f", str(src), str(BG / name)])


def mp3_to_wav(mp3: Path, wav: Path) -> None:
    run(["ffmpeg", "-y", "-i", str(mp3), "-ac", "1", "-ar", "24000", str(wav)])


def lip_mask(wav: Path, duration: float, fps: int = FPS) -> list[int]:
    """Return 1=open mouth / 0=closed per frame from RMS energy."""
    with wave.open(str(wav), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)
    n_frames = max(int(duration * fps), 1)
    samples_per = max(int(sr / fps), 1)
    mask = []
    # dynamic threshold from clip
    rms_all = []
    for i in range(n_frames):
        start = i * samples_per
        chunk = data[start : start + samples_per]
        if len(chunk) == 0:
            rms_all.append(0.0)
        else:
            rms_all.append(float(np.sqrt(np.mean(chunk * chunk))))
    thr = max(np.percentile(rms_all, 35) if rms_all else 0, 200.0)
    prev = 0
    for rms in rms_all:
        open_m = 1 if rms > thr else 0
        # avoid flicker: hold previous sometimes
        if open_m != prev and rms < thr * 1.15 and prev == 1:
            open_m = 1 if rms > thr * 0.7 else 0
        mask.append(open_m)
        prev = open_m
    return mask


def wrap(text: str, width: int = 34) -> str:
    words = text.split()
    lines, cur = [], []
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
    fs = 42 if vertical else 50
    mv = 260 if vertical else 50
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {resx}
PlayResY: {resy}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{fs},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,4,0,2,60,60,{mv},1

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
        events.append(
            f"Dialogue: 0,{ts(it['start'])},{ts(it['end'])},Default,,0,0,0,,{wrap(it['text'], 26 if vertical else 38)}"
        )
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def render_talking_clip(
    bg: Path,
    closed: Path,
    opened: Path,
    line_audio: Path,
    duration: float,
    who: str,
    out: Path,
    size: str,
) -> None:
    wav = out.with_suffix(".wav")
    mp3_to_wav(line_audio, wav)
    mask = lip_mask(wav, duration, FPS)
    work = out.with_suffix(".d")
    work.mkdir(parents=True, exist_ok=True)
    closed_frame = work / "base_closed.jpg"
    open_frame = work / "base_open.jpg"
    color = NAME_COLOR[who]
    name = DISPLAY[who]

    def compose(char_img: Path, dest: Path) -> None:
        if size == "yt":
            w, h = 1920, 1080
            char_scale = 780
            box_x, box_y = 750, 36
            vf = (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                f"eq=brightness=-0.04:saturation=0.92[bg];"
                f"[1:v]scale={char_scale}:{char_scale}[ch];"
                f"[bg][ch]overlay=(W-w)/2:(H-h)/2-30,"
                f"drawbox=x={box_x}:y={box_y}:w=420:h=58:color={color}@0.95:t=fill,"
                f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{name}':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=46,"
                f"format=yuv420p"
            )
        else:
            w, h = 1080, 1920
            vf = (
                f"[0:v]split=2[a][b];"
                f"[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=20[bg];"
                f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[scene];"
                f"[bg][scene]overlay=(W-w)/2:(H-h)/2[base];"
                f"[1:v]scale=860:860[ch];"
                f"[base][ch]overlay=(W-w)/2:(H-h)/2-60,"
                f"drawbox=x=330:y=70:w=420:h=58:color={color}@0.95:t=fill,"
                f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{name}':fontcolor=white:fontsize=32:x=(w-text_w)/2:y=80,"
                f"format=yuv420p"
            )
        run([
            "ffmpeg", "-y", "-i", str(bg), "-i", str(char_img),
            "-filter_complex", vf,
            "-frames:v", "1", "-update", "1", str(dest),
        ])

    compose(closed, closed_frame)
    compose(opened, open_frame)

    # concat demuxer with per-frame durations (fast lip flap)
    seq = work / "seq.txt"
    dt = 1.0 / FPS
    parts = []
    for bit in mask:
        src = open_frame if bit else closed_frame
        parts.append(f"file '{src.resolve()}'\nduration {dt:.4f}")
    # concat demuxer needs last file repeated without duration
    last = open_frame if mask and mask[-1] else closed_frame
    parts.append(f"file '{last.resolve()}'")
    seq.write_text("\n".join(parts) + "\n", encoding="utf-8")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(seq),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(out),
    ])
    wav.unlink(missing_ok=True)


def build(size: str) -> Path:
    sync_assets()
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    timeline = json.loads((AUDIO / "timeline.json").read_text(encoding="utf-8"))
    items = timeline["items"]
    clips_dir = BUILD / f"clips_{size}"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips = []

    for it in items:
        who = it["who"]
        closed_n, open_n = CHARS[who]
        bg = BG / BG_MAP[it["bg"]]
        line_audio = AUDIO / "lines" / f"{it['id']}.mp3"
        clip = clips_dir / f"{it['id']}.mp4"
        print(f"[{size}] {it['id']} {who} talking ({it['duration']:.2f}s)")
        render_talking_clip(
            bg, MOUTH / closed_n, MOUTH / open_n, line_audio,
            it["duration"], who, clip, size,
        )
        clips.append(clip)

    silent = BUILD / f"video_{size}_silent.mp4"
    lst = BUILD / f"concat_{size}.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])

    # mix dialogue + light bed
    music = BUILD / "bed.wav"
    if not music.exists():
        # tiny silence bed placeholder - generate soft tone
        import math
        sr = 44100
        dur = timeline["duration"] + 1
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        audio = 0.02 * np.sin(2 * np.pi * 196 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t))
        pcm = (np.clip(audio, -0.5, 0.5) * 32767).astype(np.int16)
        with wave.open(str(music), "w") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

    mixed = BUILD / f"audio_{size}.m4a"
    run([
        "ffmpeg", "-y",
        "-i", str(AUDIO / "dialogue_full.mp3"),
        "-stream_loop", "-1", "-i", str(music),
        "-filter_complex",
        "[1:a]volume=0.06[bed];[0:a]volume=1.15[vox];"
        "[vox][bed]amix=inputs=2:duration=first,"
        "aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]",
        "-map", "[a]", "-t", f"{timeline['duration']:.3f}",
        "-c:a", "aac", "-b:a", "192k", str(mixed),
    ])
    mixed48 = BUILD / f"audio_{size}_48k.m4a"
    run(["ffmpeg", "-y", "-i", str(mixed), "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k", str(mixed48)])

    ass = BUILD / f"subs_{size}.ass"
    write_ass(ass, items, vertical=(size != "yt"))
    ass_esc = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    final = OUT / (
        "tres_porquinhos_cartoon_falando_youtube.mp4" if size == "yt"
        else "tres_porquinhos_cartoon_falando_tiktok.mp4"
    )
    run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(mixed48),
        "-vf", f"subtitles={ass_esc}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(final),
    ])
    print(f"[{size}] DONE {probe(final):.2f}s -> {final.name}")
    return final


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    run(["cp", "-f", str(AUDIO / "dialogue_full.mp3"), str(OUT / "vozes_personagens.mp3")])
    yt = build("yt")
    tk = build("tk")
    print("VERIFY", yt.name, probe(yt))
    print("VERIFY", tk.name, probe(tk))


if __name__ == "__main__":
    main()
