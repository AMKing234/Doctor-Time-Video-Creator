# Local Node + Cloud Node (Hybrid System)

## Big picture

| Node | Runs where | Does | Never does |
| --- | --- | --- | --- |
| **Local** | This Termux device | YouTube OAuth + upload, tools, visual/thumbnail assets, skills, ON/OFF control, owns credentials | Push credentials to GitHub |
| **Cloud** | GitHub Actions | Research, scripts, voice, visuals, rendering, SEO, analytics (scheduled) | Store/see YouTube credentials |
| **Sync bus** | `sync` git branch | Exchanges only non-secret JSON manifests | Carry tokens/secrets (scanner blocks them) |

When the internet is down, local outgoing messages stay queued in
`local_agent/state/outbox/` and are pushed on the next successful sync.

---

## 1. Install / verify local tools

```bash
cd AI-YOUTUBE-AUTOMATION
python3 local_agent/agent.py --tools-check
python3 local_agent/agent.py --tools-install     # pkg/pip, best effort
```

Checks: `ffmpeg`, `ffprobe`, `git`, `gh`, Python modules (`edge_tts`, `flask`,
`PIL`, `boto3`, `googleapiclient`), and a usable font.

## 2. ON / OFF switches (local)

```bash
python3 local_agent/agent.py --on                # master automation ON
python3 local_agent/agent.py --off               # master automation OFF
python3 local_agent/agent.py --upload-on         # YouTube upload ON (live)
python3 local_agent/agent.py --upload-off        # YouTube upload OFF (dry-run)
python3 local_agent/agent.py --status            # everything at a glance
```

The dashboard buttons write the same state file (`data/control.json`).
Upload still refuses to run if master automation is OFF.

## 3. YouTube credentials — LOCAL ONLY

1. In Google Cloud Console create an **OAuth client ID** of type
   **Desktop app / TV and Limited Input** and download the JSON.
2. Put that file anywhere on the phone, then:
   ```bash
   python3 local_agent/agent.py --setup-youtube /sdcard/Download/client_secret.json
   ```
   The file is copied into `local_agent/vault/` with `0600` permissions.
   OAuth uses the console flow (works in Termux). The token is verified with
   `channels.list(mine=True)` and stored in the same local vault.
3. Verify any time:
   ```bash
   python3 local_agent/agent.py --verify-youtube
   ```

> Delete the original downloaded JSON from shared storage after setup.
> `local_agent/vault/` is git-ignored and guarded by a pre-commit hook.

## 4. Upload a rendered video from local

```bash
python3 local_agent/agent.py --upload-on
python3 local_agent/agent.py --upload-video <topic_id>_en
# optional scheduling:
python3 local_agent/agent.py --upload-video <topic_id>_hi --publish-at 2026-11-20T14:00:00Z
```

Uploads happen from this device with the local token. Nothing is sent to GitHub.

## 5. Visual / thumbnail assets

```bash
python3 local_agent/agent.py --assets-fetch "ancient rome forum"
python3 local_agent/agent.py --asset-report
```

Images are searched from Wikimedia Commons (freely licensed), normalised to
1920×1080 and stored under `local_agent/assets/` with an `attribution.json`.
If the network fails, a cinematic FFmpeg plate is generated instead.

## 6. Skill report auto-setup

Drop a Markdown or JSON report and let the installer set tools up:

```markdown
# Skill report: documentary-upgrade

- pip: Pillow
- pkg: ffmpeg
- asset: medieval manuscripts
- note: enables local thumbnails
```

```bash
python3 local_agent/agent.py --apply-skill-report report.md           # dry-run
python3 local_agent/agent.py --apply-skill-report report.md --apply   # apply
```

Only `pip`, `pkg`, `asset` and `note` entries are acted on — no arbitrary commands.

## 7. Local ↔ cloud sync

```bash
python3 local_agent/agent.py --sync-status
python3 local_agent/agent.py --sync-push status_request
python3 local_agent/agent.py --sync-pull
```

The first push creates a `sync` branch with a `bus/inbox` and `bus/outbox`.
The cloud workflow `.github/workflows/sync.yml` runs every 30 minutes, processes
inbox messages and writes replies to the outbox. Every payload passes
`vault.assert_no_secrets()` before leaving the device.

## 8. Safety hook

```bash
git config core.hooksPath .githooks
```

The hook blocks any staged file under `local_agent/vault/` and any obvious
token/API-key string in a commit.
