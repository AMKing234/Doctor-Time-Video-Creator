---
name: yt-resource
description: Estimate video duration, word budget, render time and storage before/after production.
---

# yt-resource

Used by the local node to decide how long a documentary should be and what it
will cost in time and disk space. Reads a script JSON and an optional render
manifest.

```bash
python3 skills/resource.py --script data/scripts/<file>.json
python3 skills/resource.py --script ... --render data/videos/<id>/render_manifest.json --json
```

Outputs words, spoken minutes, scene count, estimated render minutes, estimated
MP4 size and a recommended scene duration.
