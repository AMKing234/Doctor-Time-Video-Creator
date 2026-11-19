# Tools, Skills & APIs — full inventory

> **Short answer:** abhi koi API key chahiye hi nahi. Sab kuch local/offline chal raha hai.
> Upload ka code hata diya gaya hai — koi credential use hi nahi hoti.

## 1. APIs / credentials

### Free / already available — no key

| Tool | Kaam |
| --- | --- |
| FFmpeg / FFprobe | video render, plates, mux, subtitles |
| edge-tts | Hindi + English narration (free) |
| King Voice 👑 (`../kingvoice`) | aapka local voice engine |
| Wikimedia Commons API | freely-licensed historical images |
| SQLite | topic/video/analytics history |
| GitHub CLI (`gh`) | local tooling (optional) |

### Optional — quality upgrade ke liye (sirf .env me daalo)

| Key | Effect |
| --- | --- |
| `AI_API_KEY` / `AI_API_BASE` / `AI_MODEL` | smarter bilingual research + scripts (offline templates abhi bhi chalte hain) |
| `IMAGE_API_KEY` | AI-generated visuals (abhi FFmpeg plates + Wikimedia) |
| AWS credentials | S3 backup (abhi local `storage/`) |

`.env.example` copy karke `.env` banayein. Empty keys = fully offline. `.env` kabhi commit na karein.

## 2. Vendored repositories (12)

Sab repos is device par `vendor/` me hain. GitHub repo light rakhne ke liye sirf chhota,
pipeline-wired `youtube-agent-skill` commit hota hai; baaki `scripts/fetch_vendors.sh` se
dobaraa fetch ho sakte hain:

```bash
bash scripts/fetch_vendors.sh
python3 local_agent/agent.py --tools-registry
```

| Repo | Kaam | Status |
| --- | --- | --- |
| youtube-agent-skill | 11 skills: script, SEO, package, edit, chapters, retention, shorts, viral, audit, comment, plan | ✅ 6 Python tools wired |
| three.js | 3D WebGL | ✅ 3D thumbnail studio (minimal runtime committed) |
| pixelfx | 244 pixel effects | 📦 optional thumbnails |
| mcp-for-blender | Blender control via MCP | 📦 optional 3D (Blender alag se chahiye) |
| react-three-rapier | physics for R3F | 📦 optional 3D motion |
| react-postprocessing | postprocessing effects | 📦 optional cinematic bloom |
| lemo-opuscar | 99 film styles | 📦 style reference |
| librosa | audio/beat analysis | 📦 beat-synced cuts |
| video-shotcraft | shot planning | 📦 shot-list enhancement |
| ClaudeAnimationBase | code motion | 📦 motion templates |
| opus-video-prompts | video prompts | 📦 visual prompts |
| awesome-opus5-5-videos | curated videos | 📦 trend reference |

Legend: ✅ actively wired, 📦 available locally.

## 3. 11 skills + 3 local skills

`skills/youtube_agent.py`: yt-script, yt-package, yt-edit, yt-comment, yt-plan, yt-viral,
yt-retention, yt-shorts, yt-seo, yt-chapters, yt-audit.
Python tools: `hookscore`, `title`, `deadair`, `chapters`, `retention`, `swipe`.

Local: `yt-video` (full production + local delivery), `yt-seo-local` (full SEO + lint),
`yt-resource` (duration/render/storage estimate).

## 4. 3D Thumbnail Studio

```bash
python3 main.py --dashboard      # http://localhost:8080/studio
```

Title likho → theme chuno → **Save Thumbnail**. Image local library me:
`local_agent/assets/thumbnails/studio_*.jpg`.

## 5. Video ban gaya to delivery

Har video ke liye `ensure_delivered()` archive banata hai:

- `local_agent/assets/archive/<video_id>/REPORT.txt`
- video, visuals, audio, captions, SEO copy — sab copy

```bash
python3 local_agent/agent.py --local-save <video_id>
```
