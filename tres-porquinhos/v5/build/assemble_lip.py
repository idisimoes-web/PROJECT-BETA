#!/usr/bin/env python3
"""Episode with distinct voices + real lip-flap + natural scene acting."""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "audio"
TALK = ROOT / "images" / "talk"
ACTION = ROOT / "images" / "action"
OUT = ROOT / "output"
BUILD = ROOT / "build"
ASSETS = Path("/opt/cursor/artifacts/assets")
V4 = Path("/workspace/tres-porquinhos/v4/images/scenes")

FPS = 15  # snappier lip flap

CHARS = {
    "PIPOCA": ("v5_pipoca_closed.jpg", "v5_pipoca_open.jpg"),
    "TAMBOR": ("v5_tambor_closed.jpg", "v5_tambor_open.jpg"),
    "TIJOLINHO": ("v5_tijolinho_closed.jpg", "v5_tijolinho_open.jpg"),
    "MAMAE": ("v5_mamae_closed.jpg", "v5_mamae_open.jpg"),
    "LOBO": ("v5_lobo_closed.jpg", "v5_lobo_open.jpg"),
}

ACTION_SCENE = {
    "palha_cai": "v4_palha_cai.jpg",
    "madeira_cai": "v4_madeira_cai.jpg",
    "pipoca_corre": "v4_pipoca_corre.jpg",
    "fuga": "v4_fuga.jpg",
    "lobo_foge": "v4_lobo_foge.jpg",
    "chamine": "v4_chamine.jpg",
    "lobo_empurra": "v4_lobo_empurra.jpg",
    "lobo_palha": "v4_lobo_palha.jpg",
    "lobo_madeira": "v4_lobo_madeira.jpg",
    "lobo_tijolos": "v4_lobo_tijolos.jpg",
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

# Studio blue behind character sprites (~rgb 189,231,253)
BG_RGB = np.array([189.0, 231.0, 253.0], dtype=np.float32)
# Distances: bg ~0-5, pig face/body ~70-110 — keep a safe gap
KEY_SOFT = 28.0
KEY_HARD = 48.0


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def load_rgb(path: Path) -> np.ndarray:
    probe = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path),
        ],
        text=True,
    ).strip()
    w, h = map(int, probe.split(","))
    raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stderr=subprocess.DEVNULL,
    )
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)


def key_to_png(src: Path, dest: Path) -> None:
    """Cut studio-blue backdrop; keep pink/straw/clothes fully opaque."""
    rgb = load_rgb(src).astype(np.float32)
    dist = np.linalg.norm(rgb - BG_RGB, axis=2)
    alpha = np.clip((dist - KEY_SOFT) / (KEY_HARD - KEY_SOFT), 0.0, 1.0)
    alpha = (alpha * 255.0).astype(np.uint8)
    rgba = np.dstack([rgb.astype(np.uint8), alpha])
    h, w = alpha.shape
    # Write via ffmpeg raw rgba -> png
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgba",
            "-s", f"{w}x{h}", "-i", "pipe:0",
            "-frames:v", "1", str(dest),
        ],
        input=rgba.tobytes(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if proc.returncode != 0 or not dest.exists():
        run(["ffmpeg", "-y", "-i", str(src), "-frames:v", "1", str(dest)])


def probe(path: Path) -> float:
    return float(
        subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0", str(path),
            ],
            text=True,
        ).strip()
    )


def sync() -> None:
    TALK.mkdir(parents=True, exist_ok=True)
    ACTION.mkdir(parents=True, exist_ok=True)
    for a, b in CHARS.values():
        for n in (a, b):
            src = ASSETS / n
            if src.exists():
                run(["cp", "-f", str(src), str(TALK / n)])
    bg = ASSETS / "v5_talk_bg.jpg"
    if bg.exists():
        run(["cp", "-f", str(bg), str(TALK / "v5_talk_bg.jpg")])
    for name in set(ACTION_SCENE.values()):
        src = V4 / name
        if src.exists():
            run(["cp", "-f", str(src), str(ACTION / name)])
        elif (ASSETS / name).exists():
            run(["cp", "-f", str(ASSETS / name), str(ACTION / name)])


def mp3_to_wav(mp3: Path, wav: Path) -> None:
    run(["ffmpeg", "-y", "-i", str(mp3), "-ac", "1", "-ar", "24000", str(wav)])


def lip_mask(wav: Path, duration: float) -> list[int]:
    with wave.open(str(wav), "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    n = max(int(duration * FPS), 1)
    spf = max(int(sr / FPS), 1)
    rms = []
    for i in range(n):
        chunk = data[i * spf : (i + 1) * spf]
        rms.append(float(np.sqrt(np.mean(chunk * chunk))) if len(chunk) else 0.0)
    # Adaptive threshold: open on speech energy, close on pauses
    nonzero = [r for r in rms if r > 80]
    base = float(np.percentile(nonzero, 35)) if nonzero else 300.0
    thr = max(base, 220.0)
    out, prev = [], 0
    for r in rms:
        bit = 1 if r > thr else 0
        if prev == 1 and r > thr * 0.55:
            bit = 1
        # force brief closed frames so mouth flaps (not stuck open)
        out.append(bit)
        prev = bit
    # Anti-stuck-open: if a long open run, punch closed every 4th frame when energy dips
    run_len = 0
    for i, bit in enumerate(out):
        if bit:
            run_len += 1
            if run_len >= 4 and rms[i] < thr * 1.15:
                out[i] = 0
                run_len = 0
        else:
            run_len = 0
    if max(rms) > 500 and sum(out) < 2:
        for i, r in enumerate(rms):
            if r > thr * 0.5:
                out[i] = 1
    return out


def wrap(text: str, width: int = 36) -> str:
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
    fs = 42 if vertical else 48
    mv = 260 if vertical else 50
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {resx}
PlayResY: {resy}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{fs},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,4,0,2,70,70,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def ts(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    ev = []
    for it in items:
        ev.append(
            f"Dialogue: 0,{ts(it['start'])},{ts(it['end'])},Default,,0,0,0,,{wrap(it['text'], 28 if vertical else 40)}"
        )
    path.write_text(header + "\n".join(ev) + "\n", encoding="utf-8")


def char_scale(camera: str, size: str) -> int:
    if size == "yt":
        return {"wide": 620, "medium": 780, "close": 980}.get(camera, 820)
    return {"wide": 720, "medium": 860, "close": 980}.get(camera, 900)


def pose_offset(pose: str, camera: str) -> tuple[int, int]:
    """Small position drift so pose a/b feels like acting, not a stuck cutout."""
    dx = 0 if pose == "a" else (36 if camera != "close" else 18)
    dy = 10 if pose == "a" else (-18 if camera != "wide" else 6)
    return dx, dy


def compose_talk_still(
    char_img: Path,
    dest: Path,
    who: str,
    size: str,
    camera: str = "medium",
    pose: str = "a",
) -> None:
    bg = TALK / "v5_talk_bg.jpg"
    color = NAME_COLOR[who]
    name = DISPLAY[who]
    scale = char_scale(camera, size)
    dx, dy = pose_offset(pose, camera)
    keyed = dest.with_name(dest.stem + "_keyed.png")
    key_to_png(char_img, keyed)
    if size == "yt":
        w, h = 1920, 1080
        vf = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"eq=saturation=0.95:brightness=-0.02[bg];"
            f"[1:v]scale={scale}:{scale}[ch];"
            f"[bg][ch]overlay=(W-w)/2+{dx}:(H-h)/2+{dy}+10,"
            f"drawbox=x=40:y=40:w=380:h=56:color={color}@0.95:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{name}':fontcolor=white:fontsize=30:x=55:y=50,"
            f"format=yuv420p"
        )
    else:
        w, h = 1080, 1920
        vf = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[bg];"
            f"[1:v]scale={scale}:{scale}[ch];"
            f"[bg][ch]overlay=(W-w)/2+{dx}:(H-h)/2+{dy},"
            f"drawbox=x=350:y=80:w=380:h=56:color={color}@0.95:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{name}':fontcolor=white:fontsize=28:x=(w-text_w)/2:y=90,"
            f"format=yuv420p"
        )
    run([
        "ffmpeg", "-y",
        "-i", str(bg if bg.exists() else char_img),
        "-i", str(keyed),
        "-filter_complex", vf,
        "-frames:v", "1", "-update", "1", str(dest),
    ])
    keyed.unlink(missing_ok=True)


def render_talk_clip(
    who: str,
    line_audio: Path,
    duration: float,
    out: Path,
    size: str,
    camera: str = "medium",
    pose: str = "a",
) -> None:
    closed_n, open_n = CHARS[who]
    work = out.with_suffix(".d")
    work.mkdir(parents=True, exist_ok=True)
    closed_still = work / "closed.jpg"
    open_still = work / "open.jpg"
    compose_talk_still(TALK / closed_n, closed_still, who, size, camera, pose)
    compose_talk_still(TALK / open_n, open_still, who, size, camera, pose)

    wav = work / "a.wav"
    mp3_to_wav(line_audio, wav)
    mask = lip_mask(wav, duration)
    dt = 1.0 / FPS
    parts = []
    for bit in mask:
        src = open_still if bit else closed_still
        parts.append(f"file '{src.resolve()}'\nduration {dt:.4f}")
    last = open_still if mask and mask[-1] else closed_still
    parts.append(f"file '{last.resolve()}'")
    seq = work / "seq.txt"
    seq.write_text("\n".join(parts) + "\n", encoding="utf-8")
    tmp = work / "lip.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(seq),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(tmp),
    ])
    # Gentle bob + arm-feel sway while talking
    res = "1920x1080" if size == "yt" else "1080x1920"
    run([
        "ffmpeg", "-y", "-i", str(tmp),
        "-vf",
        f"fps=30,zoompan=z='1.03':x='iw/2-(iw/zoom/2)+6*sin(2*PI*on/50)':"
        f"y='ih/2-(ih/zoom/2)+10*sin(2*PI*on/36)':d=1:s={res}:fps=30,format=yuv420p",
        "-t", f"{duration:.3f}",
        "-an", str(out),
    ])


def render_action_clip(scene: str, duration: float, who: str, out: Path, size: str, idx: int) -> None:
    img_name = ACTION_SCENE.get(scene)
    img = ACTION / img_name if img_name and (ACTION / img_name).exists() else None
    if img is None:
        render_talk_clip(who, AUDIO / "lines" / "S01.mp3", duration, out, size)
        return
    frames = max(int(duration * 30), 1)
    zoom = (
        f"min(1.08,1+0.03*on/{frames})"
        if idx % 2 == 0
        else f"if(eq(on,1),1.08,max(1.0,1.08-0.03*on/{frames}))"
    )
    color = NAME_COLOR[who]
    name = DISPLAY[who]
    if size == "yt":
        vf = (
            f"scale=2000:1125:force_original_aspect_ratio=increase,crop=1920:1080,"
            f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps=30,"
            f"drawbox=x=40:y=40:w=380:h=56:color={color}@0.95:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{name}':fontcolor=white:fontsize=30:x=55:y=50,format=yuv420p"
        )
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-vf", vf, "-t", f"{duration:.3f}", "-an", str(out)])
    else:
        still = out.with_suffix(".jpg")
        run([
            "ffmpeg", "-y", "-i", str(img),
            "-filter_complex",
            "[0:v]split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=16[bg];"
            "[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2",
            "-frames:v", "1", "-update", "1", str(still),
        ])
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(still),
            "-vf",
            f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30,"
            f"drawbox=x=350:y=80:w=380:h=56:color={color}@0.95:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{name}':fontcolor=white:fontsize=28:x=(w-text_w)/2:y=90,format=yuv420p",
            "-t", f"{duration:.3f}", "-an", str(out),
        ])
        still.unlink(missing_ok=True)


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
        clip = clips_dir / f"{it['id']}.mp4"
        line = AUDIO / "lines" / f"{it['id']}.mp3"
        print(f"[{size}] {it['id']} {it['who']} {it.get('mode')} ({it['duration']:.2f}s)")
        if it.get("mode") == "action":
            render_action_clip(it["scene"], it["duration"], it["who"], clip, size, idx)
        else:
            render_talk_clip(
                it["who"], line, it["duration"], clip, size,
                camera=it.get("camera", "medium"),
                pose=it.get("pose", "a"),
            )
        clips.append(clip)

    silent = BUILD / f"video_{size}_silent.mp4"
    lst = BUILD / f"concat_{size}.txt"
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])

    bed = BUILD / "bed.wav"
    if not bed.exists():
        sr = 44100
        dur = timeline["duration"] + 1
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        audio = 0.025 * np.sin(2 * np.pi * 196 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.04 * t))
        pcm = (np.clip(audio, -0.5, 0.5) * 32767).astype(np.int16)
        with wave.open(str(bed), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())

    mixed = BUILD / f"audio_{size}.m4a"
    run([
        "ffmpeg", "-y",
        "-i", str(AUDIO / "dialogue_full.mp3"),
        "-stream_loop", "-1", "-i", str(bed),
        "-filter_complex",
        "[1:a]volume=0.05[bed];[0:a]volume=1.2[vox];[vox][bed]amix=inputs=2:duration=first,"
        "aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100[a]",
        "-map", "[a]", "-t", f"{timeline['duration']:.3f}",
        "-c:a", "aac", "-b:a", "192k", str(mixed),
    ])
    mixed_ok = BUILD / f"audio_{size}_ok.m4a"
    run(["ffmpeg", "-y", "-i", str(mixed), "-ar", "44100", "-ac", "2", "-c:a", "aac", "-b:a", "192k", str(mixed_ok)])

    ass = BUILD / f"subs_{size}.ass"
    write_ass(ass, items, vertical=(size != "yt"))
    ass_esc = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    raw = BUILD / f"raw_{size}.mp4"
    run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(mixed_ok),
        "-vf", f"subtitles={ass_esc}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "19",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(raw),
    ])
    final = OUT / (
        "tres_porquinhos_vozes_lip_youtube.mp4" if size == "yt"
        else "tres_porquinhos_vozes_lip_tiktok.mp4"
    )
    run([
        "ffmpeg", "-y", "-i", str(raw),
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-profile:v", "main", "-level", "4.0",
        "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart", str(final),
    ])
    print(f"[{size}] DONE {probe(final):.2f}s")
    return final


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    run(["cp", "-f", str(AUDIO / "dialogue_full.mp3"), str(OUT / "vozes_personagens.mp3")])
    if (AUDIO / "vozes_amostra_5.mp3").exists():
        run(["cp", "-f", str(AUDIO / "vozes_amostra_5.mp3"), str(OUT / "vozes_amostra_5.mp3")])
    yt = build("yt")
    tk = build("tk")
    print("VERIFY", yt.name, probe(yt))
    print("VERIFY", tk.name, probe(tk))


if __name__ == "__main__":
    main()
