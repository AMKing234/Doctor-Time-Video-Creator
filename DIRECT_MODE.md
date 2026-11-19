# Direct Local Video Mode (abhi ka system)

Ab is project me **scheduler nahi, cloud nahi, upload nahi**. Aap topic aur timeline dete ho,
system research karke Full HD video bana deta hai aur local me archive + `REPORT.txt` likh deta hai.

## 1. Seedha command

```bash
cd AI-YOUTUBE-AUTOMATION

python3 make_video.py \
  --topic "All Roads Lead to Rome" \
  --timeline "Road building|Trade networks|Imperial postal system|Legacy of Roman roads" \
  --minutes 8
```

Agar timeline file hai:

```bash
python3 make_video.py --topic "The Silk Road" --timeline-file timeline.txt --minutes 22
```

Timeline file me ek point per line likho (bullet/number dono chalte hain):

```
1. Route building across deserts
2. Trade of silk, spices and ideas
3. Cities that grew along the route
4. Decline and lasting legacy
```

## 2. Dashboard se (browser)

```bash
python3 main.py --dashboard
# http://localhost:8080
```

Form me topic, timeline, minutes bharo → **🎥 VIDEO BANAO**. Progress live dikhega.
3D thumbnail ke liye: http://localhost:8080/studio

## 3. Kya-kya hota hai (automatic)

```
topic + timeline
   ↓ research (timeline se facts, offline knowledge base se merge)
   ↓ script (Hindi + English, requested minutes ke hisaab se scene count)
   ↓ voice (King Voice 👑 → edge-tts → synthetic)
   ↓ visuals (Wikimedia → FFmpeg cinematic plates)
   ↓ animation + 1920×1080 render + bilingual subtitles
   ↓ thumbnail + SEO (title, description, tags, chapters)
   ↓ 11 skills (hook score, title lint, chapters, EDL, resource…)
   ↓ local_agent/assets/archive/<topic>_<lang>/REPORT.txt
```

## 4. Output kahan milega

- Final video: `data/videos/<topic>_<lang>/final.mp4`
- Local archive: `local_agent/assets/archive/<topic>_<lang>/`
  - `REPORT.txt` — title, language, duration, chapters, tags, full description
  - video, captions, audio, visuals, SEO copy — sab copy
- Thumbnail: `data/thumbnails/<topic>_<lang>/thumbnail.jpg`

## 5. Kya hata diya gaya

`.github/workflows/`, `scheduler/`, `youtube_uploader/`, `analytics_engine/`,
`notifications/`, `common/control.py`, `local_agent/vault.py`,
`local_agent/sync.py`, `local_agent/cloud_worker.py`,
`local_agent/youtube_setup.py`, ON/OFF switches — sab delete.

Kuch bhi upload nahi hota, koi credential use nahi hoti.

## 6. Useful commands

```bash
python3 local_agent/agent.py --status          # tools/assets/database status
python3 local_agent/agent.py --tools-check
python3 local_agent/agent.py --skills-list
python3 local_agent/agent.py --tools-registry
python3 local_agent/agent.py --local-save <video_id>
python3 main.py --test                          # chota smoke video
python3 -m unittest discover -s tests -v
```
