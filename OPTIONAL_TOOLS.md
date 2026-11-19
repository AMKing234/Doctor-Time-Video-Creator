# Tools, Skills & APIs — full inventory

> **Short answer:** abhi koi paid API key chahiye nahi. System offline chal raha hai.
> Sirf YouTube upload ke liye ek **OAuth client-secrets JSON** baad me chahiye — aur wo
> sirf is device ke `local_agent/vault/` me rahega, GitHub par kabhi nahi.

## 1. APIs / credentials — kya chahiye

### Required (sirf tab, jab aap YouTube par upload karna chahein)

| Kya | Kahan se | Notes |
| --- | --- | --- |
| OAuth Client ID (type: **Desktop app**) JSON | Google Cloud Console → APIs & Services → Credentials | Local vault me import hota hai |
| **YouTube Data API v3** enabled | Usi Google Cloud project me | Free quota ~10,000 units/day |

```bash
python3 local_agent/agent.py --setup-youtube /path/to/client_secret.json
python3 local_agent/agent.py --verify-youtube
```

### Already available — free, no key

| Tool | Kaam |
| --- | --- |
| FFmpeg / FFprobe | video render, plates, mux, subtitles |
| edge-tts | Hindi + English narration (free) |
| King Voice 👑 (`../kingvoice`) | aapka local voice engine |
| Wikimedia Commons API | freely-licensed historical images |
| SQLite | topic/video/analytics history |
| GitHub CLI (`gh`) | already logged-in; sync bus ke liye |

### Optional (quality upgrade ke liye)

| Key | Effect |
| --- | --- |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | smarter bilingual scripts (offline templates abhi bhi chalte hain) |
| `IMAGE_API_KEY` | AI-generated visuals (abhi FFmpeg plates + Wikimedia) |
| AWS credentials | S3 backup (abhi local `storage/`) |

## 2. Vendored repositories (12)

Sab repos is device par `vendor/` me clone hain. GitHub repo ko light rakhne ke liye
sirf chhota, pipeline-wired `youtube-agent-skill` commit hota hai; baaki sab ko
`scripts/fetch_vendors.sh` se dobara fetch kiya ja sakta hai:

```bash
bash scripts/fetch_vendors.sh
python3 local_agent/agent.py --tools-registry
```

| Repo | Kaam | System me status |
| --- | --- | --- |
| [youtube-agent-skill](https://github.com/Jakeschincariol/youtube-agent-skill) | 11 skills: script, SEO, package, edit, chapters, retention, shorts, viral, audit, comment, plan | ✅ 6 Python tools wired into `full` pipeline |
| [three.js](https://github.com/mrdoob/three.js) | 3D WebGL/WebGPU rendering | ✅ 3D thumbnail studio (minimal runtime committed) |
| [pixelfx](https://github.com/patch-gg/pixelfx) | 244 pixel-art effects | 📦 optional thumbnail/sprite effects |
| [mcp-for-blender](https://github.com/ahujasid/mcp-for-blender) | Blender 3D control via MCP | 📦 optional 3D scenes (Blender alag se chahiye) |
| [react-three-rapier](https://github.com/pmndrs/react-three-rapier) | physics for React Three Fiber | 📦 optional 3D intro motion |
| [react-postprocessing](https://github.com/pmndrs/react-postprocessing) | postprocessing effects | 📦 optional cinematic bloom |
| [lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) | 99 code-only film styles | 📦 cinematic style reference |
| [librosa](https://github.com/librosa/librosa) | audio analysis / beat tracking | 📦 beat-synced cuts (optional) |
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | shot planning | 📦 shot-list enhancement |
| [ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase) | code-driven motion | 📦 motion templates |
| [opus-video-prompts](https://github.com/joeseesun/opus-video-prompts) | video prompts | 📦 visual prompt library |
| [awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos) | curated videos | 📦 style/trend reference |

Legend: ✅ = actively wired, 📦 = available locally for optional use.

## 3. 11 YouTube agent skills — sab kaam me

`skills/youtube_agent.py` ke through:

| Skill | Kaam |
| --- | --- |
| yt-script | hook formulas + hook scoring |
| yt-package | title + thumbnail pair lint |
| yt-edit | dead-air / filler / repeat detection (EDL) |
| yt-comment | comment strategy |
| yt-plan | content planning |
| yt-viral | outlier/viral video analysis |
| yt-retention | audience retention analysis |
| yt-shorts | find Shorts inside long videos |
| yt-seo | full SEO |
| yt-chapters | auto chapters |
| yt-audit | channel audit |

Python tools: `hookscore`, `title`, `deadair`, `chapters`, `retention`, `swipe`.

## 4. Local skills (new)

| Skill | File | Kaam |
| --- | --- | --- |
| yt-video | `skills/video_skill.py` | poora video banata hai + local delivery guarantee |
| yt-seo-local | `skills/seo_skill.py` | full SEO + title/thumbnail lint |
| yt-resource | `skills/resource.py` | duration, word budget, render time, storage estimate |

## 5. 3D Thumbnail Studio

```bash
python3 main.py --dashboard      # http://localhost:8080/studio
```

Browser me title likho → theme chuno → **Save Thumbnail**. Image local asset library
me save hoti hai: `local_agent/assets/thumbnails/studio_*.jpg`.

## 6. Upload na ho to kya hoga

Har video ke liye `skills_stage` automatically check karta hai:

- Upload hua → YouTube ID record
- Upload nahi hua → `local_agent/assets/archive/<video_id>/` me video, visuals,
  captions, SEO copy kak ke **`REPORT.txt`** generate hota hai (full SEO ke saath).

```bash
python3 local_agent/agent.py --local-save <video_id>
```
