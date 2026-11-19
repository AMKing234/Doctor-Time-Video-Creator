# AI Documentary Factory — Direct Local Video Maker

Aap topic + timeline + minutes dete ho; system khud research karke **Full HD Hindi/English
documentary** bana deta hai, thumbnail aur SEO banata hai, aur sab kuch local me
archive + `REPORT.txt` ke saath save karta hai.

> **Ab koi scheduler nahi, koi GitHub Actions nahi, koi YouTube upload nahi.**
> Sab kuch isi device par chalta hai. Koi API key zaroori nahi.

## Quick start

```bash
cd AI-YOUTUBE-AUTOMATION

python3 make_video.py \
  --topic "All Roads Lead to Rome" \
  --timeline "Road building|Trade networks|Imperial postal system|Legacy" \
  --minutes 8

python3 main.py --dashboard        # http://localhost:8080  (form + 3D studio)
```

Detail: [DIRECT_MODE.md](DIRECT_MODE.md) · Tools/APIs: [OPTIONAL_TOOLS.md](OPTIONAL_TOOLS.md)

## Pipeline

```
topic + timeline → research → script (HI+EN) → voice → visuals → animation
→ 1920×1080 render → subtitles → thumbnail → SEO → 11 skills → REPORT.txt
```

- **Research:** aapki timeline ka har point ek "beat" ban jata hai; offline knowledge base
  se merge hota hai. AI key ho to research aur script aur polished hote hain (optional).
- **Duration:** `--minutes` ke hisaab se timeline beats repeat/expand hote hain taake
  target duration mile. Koi naya historical claim nahi banaya jata.
- **Voice:** King Voice 👑 → edge-tts → synthetic fallback (sab free/local).
- **Visuals:** Wikimedia Commons images ya FFmpeg cinematic plates (offline).
- **Guarantee:** video ban gaya to `local_agent/assets/archive/<id>/REPORT.txt` zaroor banega.

## Layout

```
make_video.py              direct entry point (topic + timeline + minutes)
main.py                    stage runner + dashboard launcher
research/ script_engine/   bilingual research + scripts
voice_engine/ visual_engine/ animation_engine/ video_editor/
seo_engine/ thumbnail_engine/
skills/                    11 YouTube skills + 3 local skills + tool registry
dashboard/                 local dashboard + three.js 3D thumbnail studio
local_agent/fallback.py    archive + REPORT.txt
database/                  SQLite history (duplicates skip)
vendor/                    local tool repos (fetch_vendors.sh se dobara fetch)
```

## Commands

```bash
python3 make_video.py --topic "..." --timeline "A|B|C" --minutes 22
python3 main.py --stage full           # curated topic se smoke run
python3 main.py --stage video          # sirf render
python3 main.py --test                 # chota test
python3 main.py --dashboard            # browser UI + /studio
python3 local_agent/agent.py --status
python3 local_agent/agent.py --tools-check
python3 local_agent/agent.py --skills-list
python3 local_agent/agent.py --tools-registry
python3 -m unittest discover -s tests -v
```

## Safety

- Koi OAuth/token/client-secret file project me nahi hai aur na hi kabhi bheji jati hai.
- `.githooks/pre-commit` credential-like files/strings ko commit hone se rokta hai
  (`git config core.hooksPath .githooks` ek baar chalao).
- Bade media (`*.mp4`, `*.wav`, ...) aur `data/` git-ignored hain.

Abhi koi video upload nahi hua aur upload ka code repo se hata diya gaya hai.
