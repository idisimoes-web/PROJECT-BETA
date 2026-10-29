#!/usr/bin/env python3
from __future__ import annotations
import asyncio, json, subprocess
from pathlib import Path
import edge_tts

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "script" / "episodio.json"
AUDIO = ROOT / "audio"
LINES = AUDIO / "lines"

async def synth(text, voice, rate, pitch, out):
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))

async def main():
    data = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voices = data["voices"]
    LINES.mkdir(parents=True, exist_ok=True)
    timeline, concat, t = [], [], 0.0
    for shot in data["shots"]:
        who = shot["who"]
        cfg = voices[who]
        speech = LINES / f"{shot['id']}_speech.mp3"
        silence = LINES / f"{shot['id']}_silence.wav"
        merged = LINES / f"{shot['id']}.mp3"
        print(f"{shot['id']} {who}")
        await synth(shot["text"], cfg["voice"], cfg["rate"], cfg["pitch"], speech)
        pause = float(shot.get("pause", 0.2))
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i","anullsrc=r=24000:cl=mono","-t",f"{pause}",str(silence)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ffmpeg","-y","-i",str(speech),"-i",str(silence),
                        "-filter_complex","[0:a][1:a]concat=n=2:v=0:a=1[a]","-map","[a]",str(merged)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        dur = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(merged)], text=True).strip())
        timeline.append({**shot, "start": t, "end": t + max(dur - pause, 0.35), "duration": dur})
        concat.append(f"file '{merged.resolve()}'")
        t += dur
    (AUDIO/"timeline.json").write_text(json.dumps({"duration": t, "items": timeline}, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIO/"concat.txt").write_text("\n".join(concat)+"\n", encoding="utf-8")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(AUDIO/"concat.txt"),"-c","copy",str(AUDIO/"dialogue_full.mp3")],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"FULL_DURATION_SEC={t:.3f}")

if __name__ == "__main__":
    asyncio.run(main())
