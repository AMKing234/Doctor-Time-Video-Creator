# 🎬 AI Documentary Factory

A self-operating AI YouTube documentary production studio. GitHub Actions is the
orchestration centre; research, bilingual scriptwriting, narration, cinematic
visuals, rendering, thumbnails, SEO, publishing and analytics all run automatically.

> ⚠️ **Upload is disabled by default.** The upload stage runs in **dry-run** mode
> and only writes a local plan. Nothing is sent to YouTube until you explicitly
> set `YOUTUBE_ENABLED=true` and configure OAuth credentials.

---

## 1. Architecture

```
GitHub Actions (scheduler / control centre)
        │
        ▼
Topic Engine → Research Engine → Script Engine (HI + EN)
        │
        ▼
Voice Engine (King Voice 👑 / edge-tts) + Visual Engine (AI / FFmpeg plates)
        │
        ▼
Animation → Video Editor (FFmpeg) → Thumbnail + SEO
        │
        ▼
External asset storage (S3 / local) → YouTube Uploader (dry-run by default)
        │
        ▼
Analytics Engine → optimal publish time → next cycle
```

Large MP4/MP3 assets are **never committed** to git. Jobs exchange small JSON
manifests through GitHub Actions artifacts; final media goes to external storage
(S3-compatible) or a local `storage/` folder that is git-ignored.

## 2. Repository layout

```
.github/workflows/   main, research, video-production, upload, analytics
config/              settings.json, languages.json, channel.json
common/              config, paths, utils, logging, AI client
research/            knowledge base + deep research engine
topic_engine/        discovery, scoring, duplicate prevention
script_engine/       bilingual, chaptered, emotion-tagged scripts
voice_engine/        King Voice 👑 integration + edge-tts + offline fallback
visual_engine/       AI images + cinematic FFmpeg plates
animation_engine/    Ken Burns motion
video_editor/        concat, music, subtitles, final H.264 render
thumbnail_engine/    1280x720 thumbnails
seo_engine/          titles, descriptions, tags, hashtags, chapters
youtube_uploader/    OAuth upload/schedule (DISABLED by default)
analytics_engine/    metrics + publish-time optimisation
scheduler/           cron + optimal slot
database/            SQLite production history
notifications/       console + webhook
error_handler/       retries, run tracking, error log
storage/             local / S3 asset store
dashboard/           Flask monitoring UI
tests/               offline smoke tests
```

## 3. Quick start (local / Termux)

```bash
cd AI-YOUTUBE-AUTOMATION
python3 -m pip install -r requirements.txt   # or: pkg install python ffmpeg
python3 -m unittest discover -s tests -v

# Full end-to-end smoke run (short, offline, no uploads)
python3 main.py --stage full --test

# Individual stages
python3 main.py --stage research
python3 main.py --stage script
python3 main.py --stage voice
python3 main.py --stage visual
python3 main.py --stage video
python3 main.py --stage seo
python3 main.py --stage upload     # dry-run
python3 main.py --stage analytics

# Monitoring dashboard
python3 main.py --dashboard        # http://localhost:8080
```

`--test` keeps the script to a few scenes so a complete run finishes quickly.
Without `--test`, offline mode targets roughly 20–25 minutes using structured
narrative templates. For genuinely varied long-form prose, configure an AI API key.

## 4. GitHub setup

1. Create a new GitHub repository and push this folder:
   ```bash
   git init
   git add .
   git commit -m "Initial AI Documentary Factory"
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
2. **Settings → Secrets and variables → Actions**, add what you need:

   | Secret | Purpose |
   | --- | --- |
   | `AI_API_KEY` | Research + scriptwriting (OpenAI-compatible) |
   | `AI_API_BASE` / `AI_MODEL` | Endpoint + model override |
   | `IMAGE_API_KEY` | Cinematic AI stills (optional) |
   | `STORAGE_PROVIDER=s3` + `S3_*` | External media storage |
   | `YOUTUBE_ENABLED=true` | Only when ready to publish |
   | `YOUTUBE_CLIENT_SECRETS` / `YOUTUBE_TOKEN_FILE` | OAuth files (base64-decode in workflow) |
   | `NOTIFY_WEBHOOK_URL` | Slack/Discord notifications |

3. The scheduler runs `main.yml` daily at **03:00 UTC**. Change `cron` in
   `.github/workflows/main.yml` and `config/settings.json` as needed.

## 5. Voice engine

`voice_engine/engine.py` first tries to import your existing King Voice 👑
repository (`engine.py`) from `KINGVOICE_REPO_PATH` (default `../kingvoice`) and
reuses its emotion presets and FFmpeg DSP. On a clean runner where the repo is
absent, an equivalent built-in edge-tts implementation is used. If edge-tts has
no network, a length-matched synthetic audio bed is generated so the pipeline
still renders. No manual voice work is ever needed.

## 6. Upload safety

- `config/settings.json → upload.enabled` is `false`.
- `upload.dry_run` is `true`.
- `YOUTUBE_ENABLED` defaults to `false` in the workflow.
- The dry-run writes `data/uploads/<video_id>.json` describing the planned upload.

To go live: set both the config flag and the secret to `true`, add OAuth files,
and decide `privacy` / `schedule_enabled`. The Analytics Engine then feeds the
optimal publish hour back into the Scheduler automatically.

## 6.1 ON/OFF switches

The dashboard has two live switches (state stored in `data/control.json`, which is
git-ignored):

- **Master Automation** — turns the entire pipeline ON/OFF. Every stage checks it
  and exits safely when OFF. In GitHub Actions, set repository variable
  `AUTOMATION_ENABLED=false` to pause the scheduled workflow.
- **YouTube Upload** — `OFF` = dry-run (default), `ON` = attempt a live upload once
  OAuth is configured.

CLI equivalents:

```bash
python3 main.py --automation off
python3 main.py --automation on
python3 main.py --upload off
python3 main.py --upload on
```

## 7. What is automatic

No manual topic selection, scriptwriting, voice generation, image/frame creation,
editing, thumbnail design, SEO, upload or scheduling. Errors are retried with
backoff and stored in SQLite; a complete production history is kept in
`data/automation.db` and visible in the dashboard.

## 8. Roadmap notes

- Replace template expansion with long-form AI scripts when a key is configured.
- Add royalty-free music licensing/source tracking.
- Add per-scene lip-sync or avatar presenters if desired.
- Add multi-channel support via multiple `channel.json` profiles.
