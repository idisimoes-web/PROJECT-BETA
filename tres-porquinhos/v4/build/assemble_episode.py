#!/usr/bin/env python3
"""Assemble Peppa-like preschool episode with camera cuts + character voices."""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "audio"
SCENES = ROOT / "images" / "scenes"
OUT = ROOT / "output"
BUILD = ROOT / "build"
ASSETS = Path("/opt/cursor/artifacts/assets")

SCENE_MAP = {
    "titulo": "v4_titulo.jpg",
    "fazenda_wide": "v4_fazenda_wide.jpg",
    "fazenda_medium": "v4_fazenda_medium.jpg",
    "fazenda_reaction": "v4_fazenda_reaction.jpg",
    "pipoca_constroi": "v4_pipoca_constroi.jpg",
    "tambor_constroi": "v4_tambor_constroi.jpg",
    "tijolinho_constroi": "v4_tijolinho_constroi.jpg",
    "tijolos_pronta": "v4_tijolos_pronta.jpg",
    "tres_casas": "v4_tres_casas.jpg",
    "brincadeira": "v4_brincadeira.jpg",
    "lobo_floresta": "v4_lobo_floresta.jpg",
    "lobo_palha": "v4_lobo_palha.jpg",
    "pipoca_medo": "v4_pipoca_medo.jpg",
    "palha_cai": "v4_palha_cai.jpg",
    "pipoca_corre": "v4_pipoca_corre.jpg",
    "tambor_porta": "v4_tambor_porta.jpg",
    "lobo_madeira": "v4_lobo_madeira.jpg",
    "dentro_madeira": "v4_dentro_madeira.jpg",
    "madeira_cai": "v4_madeira_cai.jpg",
    "fuga": "v4_fuga.jpg",
    "tijolos_aberta": "v4_tijolos_aberta.jpg",
    "dentro_tijolos": "v4_dentro_tijolos.jpg",
    "lobo_tijolos": "v4_lobo_tijolos.jpg",
    "janela_vitoria": "v4_janela_vitoria.jpg",
    "lobo_empurra": "v4_lobo_empurra.jpg",
    "chamine": "v4_chamine.jpg",
    "lareira": "v4_lareira.jpg",
    "lobo_foge": "v4_lobo_foge.jpg",
    "abraco": "v4_abraco.jpg",
    "final": "v4_final.jpg",
}

NAME_COLOR = {
    "PIPOCA": "0xF2C94C",
    "TAMBOR": "0x2F80ED",
    "TIJOLINHO": "0xEB5757",
    "MAMAE": "0xF2994A",
    "LOBO": "0x6B8F71",
}

DISPLAY = {
    "PIPOCA": "PIPOCA",
    "TAMBOR": "TAMBOR",
    "TIJOLINHO": "TIJOLINHO",
    "MAMAE": "MAMAE",
    "LOBO": "LOBO MAU",
}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def probe(path: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        text=True,
    ).strip())


def sync() -> None:
    SCENES.mkdir(parents=True, exist_ok=True)
    for name in SCENE_MAP.values():
        src = ASSETS / name
        if src.exists():
            run(["cp", "-f", str(src), str(SCENES / name)])
    bible = ASSETS / "v4_bible.jpg"
    if bible.exists():
        run(["cp", "-f", str(bible), str(SCENES / "v4_bible.jpg")])


def wrap(text: str, width: int = 36) -> str:
    words = text.split()
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if len(trial) > width and cur:
            lines.append(" ".join(cur)); cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return "\\N".join(lines[:3])


def write_ass(path: Path, items: list[dict], vertical: bool = False) -> None:
    resx, resy = (1080, 1920) if vertical else (1920, 1080)
    fs = 40 if vertical else 48
    mv = 240 if vertical else 48
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {resx}
PlayResY: {resy}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{fs},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,4,0,2,70,70,{mv},1
Style: Tag,DejaVu Sans Bold,{fs-6},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,7,40,40,36,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def ts(sec: float) -> str:
        h = int(sec // 3600); m = int((sec % 3600) // 60); s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"
    ev = []
    for it in items:
        ev.append(f"Dialogue: 0,{ts(it['start'])},{ts(it['end'])},Default,,0,0,0,,{wrap(it['text'], 28 if vertical else 40)}")
        ev.append(f"Dialogue: 1,{ts(it['start'])},{ts(it['end'])},Tag,,0,0,0,,{DISPLAY[it['who']]}")
    path.write_text(header + "\n".join(ev) + "\n", encoding="utf-8")


def camera_crop(camera: str, pose: str) -> str:
    """Return zoompan z/x/y hints via crop before scale."""
    # Relative crop windows simulating wide/medium/close + pose A/B offset
    if camera == "wide":
        # slight drift by pose
        return "scale=2000:1125:force_original_aspect_ratio=increase,crop=1920:1080" if pose == "a" \
            else "scale=2000:1125:force_original_aspect_ratio=increase,crop=1920:1080:x=40:y=20"
    if camera == "medium":
        return "scale=2400:1350:force_original_aspect_ratio=increase,crop=1920:1080:x=240:y=120" if pose == "a" \
            else "scale=2400:1350:force_original_aspect_ratio=increase,crop=1920:1080:x=280:y=140"
    # close
    return "scale=2800:1575:force_original_aspect_ratio=increase,crop=1920:1080:x=440:y=220" if pose == "a" \
        else "scale=2800:1575:force_original_aspect_ratio=increase,crop=1920:1080:x=500:y=240"


def render_clip(img: Path, duration: float, who: str, camera: str, pose: str, out: Path, size: str, idx: int) -> None:
    frames = max(int(duration * 30), 1)
    color = NAME_COLOR[who]
    name = DISPLAY[who]
    zoom = f"min(1.06,1+0.025*on/{frames})" if idx % 2 == 0 else f"if(eq(on,1),1.06,max(1.0,1.06-0.025*on/{frames}))"
    crop = camera_crop(camera, pose)

    if size == "yt":
        w, h = 1920, 1080
        vf = (
            f"{crop},"
            f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30,"
            f"drawbox=x=40:y=36:w=360:h=52:color={color}@0.92:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{name}':fontcolor=white:fontsize=28:x=55:y=46,"
            f"format=yuv420p"
        )
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img),
            "-vf", vf, "-t", f"{duration:.3f}", "-an", "-pix_fmt", "yuv420p", str(out),
        ])
    else:
        w, h = 1080, 1920
        still = out.with_suffix(".jpg")
        run([
            "ffmpeg", "-y", "-i", str(img),
            "-vf", f"{crop},scale=1280:720",
            "-frames:v", "1", "-update", "1", str(still),
        ])
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(still),
            "-filter_complex",
            (
                f"[0:v]split=2[a][b];"
                f"[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=18[bg];"
                f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
                f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30,"
                f"drawbox=x=360:y=70:w=360:h=52:color={color}@0.92:t=fill,"
                f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{name}':fontcolor=white:fontsize=26:x=(w-text_w)/2:y=80,"
                f"format=yuv420p"
            ),
            "-t", f"{duration:.3f}", "-an", "-pix_fmt", "yuv420p", str(out),
        ])
        still.unlink(missing_ok=True)


def make_bed(path: Path, duration: float, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    freqs = [261.63, 329.63, 392.00, 349.23, 293.66, 392.00]
    audio = np.zeros_like(t)
    note = 0.6
    for i in range(int(duration / note) + 2):
        f = freqs[i % len(freqs)]
        a = int(i * note * sr); b = min(len(t), a + int(note * sr))
        if a >= len(t):
            break
        tt = np.arange(b - a) / sr
        env = np.sin(np.pi * np.clip(tt / note, 0, 1))
        audio[a:b] += 0.03 * env * np.sin(2 * np.pi * f * tt)
    fade = int(1.2 * sr)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    pcm = (np.clip(audio, -0.8, 0.8) * 32767).astype(np.int16)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def build(size: str) -> Path:
    sync()
    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    timeline = json.loads((AUDIO / "timeline.json").read_text(encoding="utf-8"))
    items = timeline["items"]
    clips_dir = BUILD / f"clips_{size}"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for idx, it in enumerate(items):
        img = SCENES / SCENE_MAP[it["scene"]]
        clip = clips_dir / f"{it['id']}.mp4"
        print(f"[{size}] {it['id']} {it['who']} {it['scene']} {it['camera']}")
        render_clip(img, it["duration"], it["who"], it["camera"], it.get("pose", "a"), clip, size, idx)
        clips.append(clip)

    silent = BUILD / f"video_{size}_silent.mp4"
    lst = BUILD / f"concat_{size}.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])

    bed = BUILD / "bed.wav"
    if not bed.exists():
        make_bed(bed, timeline["duration"] + 2)
    mixed = BUILD / f"audio_{size}.m4a"
    run([
        "ffmpeg", "-y", "-i", str(AUDIO / "dialogue_full.mp3"), "-stream_loop", "-1", "-i", str(bed),
        "-filter_complex",
        "[1:a]volume=0.07[bed];[0:a]volume=1.12[vox];[vox][bed]amix=inputs=2:duration=first,"
        "aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100[a]",
        "-map", "[a]", "-t", f"{timeline['duration']:.3f}", "-c:a", "aac", "-b:a", "192k", str(mixed),
    ])
    mixed48 = BUILD / f"audio_{size}_ok.m4a"
    run(["ffmpeg", "-y", "-i", str(mixed), "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "192k", str(mixed48)])

    ass = BUILD / f"subs_{size}.ass"
    write_ass(ass, items, vertical=(size != "yt"))
    ass_esc = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    raw = BUILD / f"raw_{size}.mp4"
    run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(mixed48),
        "-vf", f"subtitles={ass_esc}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "19",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(raw),
    ])
    final = OUT / (
        "tres_porquinhos_estilo_peppa_youtube.mp4" if size == "yt"
        else "tres_porquinhos_estilo_peppa_tiktok.mp4"
    )
    # web-compatible pass
    run([
        "ffmpeg", "-y", "-i", str(raw),
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-profile:v", "main", "-level", "4.0", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart", str(final),
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
