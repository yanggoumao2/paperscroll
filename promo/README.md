# Promo video

Source of `docs/media/paperscroll-promo.mp4` (~54 s, 1920×1080, English voice-over, Chinese subtitles).
`script.json`: `speak` picks the narrated language (`en`/`zh`), `voice` the Edge TTS voice, `subtitle_en` adds an English line under the Chinese subtitle.
Everything is generated: real app screens from a sandbox copy of the database, scenes drawn in HTML, voice by
Microsoft Edge neural TTS, music and sound effects synthesised in `audio.py` (no third-party samples).

Windows, from this folder (`uv`, `ffmpeg` and Microsoft Edge required):

```powershell
uv sync
# 1. a sandbox server on :8799 with the owner's likes/notes removed from the copy
$env:PS_SANDBOX_CLEAN = "1"; ..\server\.venv\Scripts\python.exe ..\server\dev\sandbox_server.py   # separate window
# 2. screens, titles, voice, timeline
.venv\Scripts\python.exe capture.py
.venv\Scripts\python.exe titles.py      # needs a local database
.venv\Scripts\python.exe tts.py         # script.json -> audio/vo_*.mp3 + timeline.json
# 3. frames, sound, mux
.venv\Scripts\python.exe render.py      # scene.html -> frames/*.jpg (30 fps)
.venv\Scripts\python.exe audio.py       # -> audio/mix.wav
ffmpeg -framerate 30 -i frames\%05d.jpg -i audio\mix.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 `
  -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart -shortest out\paperscroll-promo.mp4
```

Edit the narration in `script.json` and the visuals in `scene.html` (`window.render(t)` draws the frame at time `t`).
`python render.py 3.5 14 30` renders single preview frames.
