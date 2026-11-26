"""Voice-over: one clip per scene with edge-tts (Microsoft neural voices; only the script text is sent).
Writes audio/vo_<id>.mp3 and timeline.json (scene start/end in seconds, voice offsets)."""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

D = Path(__file__).parent
A = D / "audio"; A.mkdir(exist_ok=True)
S = json.loads((D / "script.json").read_text(encoding="utf-8"))
LEAD = 0.35   # silence before each line inside its scene


def duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout
    return float(out.strip())


async def main():
    t = 0.0
    scenes = []
    for sc in S["scenes"]:
        mp3 = A / f"vo_{sc['id']}.mp3"
        await edge_tts.Communicate(sc["zh"], S["voice"], rate=S["rate"]).save(str(mp3))
        d = duration(mp3)
        length = LEAD + d + sc["pad"]
        scenes.append({"id": sc["id"], "start": round(t, 3), "end": round(t + length, 3), "vo_at": round(t + LEAD, 3),
                       "vo_len": round(d, 3), "zh": sc["zh"], "en": sc["en"]})
        t += length
    (D / "timeline.json").write_text(json.dumps({"total": round(t, 3), "scenes": scenes}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    for s in scenes:
        print(f"{s['id']:8s} {s['start']:6.2f} → {s['end']:6.2f}  voice {s['vo_len']:.2f}s")
    print("total", round(t, 2))


asyncio.run(main())
