"""Direct video maker dashboard — no scheduler, no upload, no cloud."""
from __future__ import annotations

import threading

from common.config import load_settings
from common.logging_setup import get_logger
from database.manager import Database

log = get_logger("dashboard")

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Doctor Time Video Creator — Direct Video Maker</title>
<style>
body{background:#0B0F19;color:#E8EAF0;font:15px system-ui,sans-serif;margin:0;padding:28px}
h1{color:#D4AF37;margin:0 0 4px}h2{color:#D4AF37;font-size:18px;margin-top:30px}
.sub{color:#8A93A8;margin-bottom:22px}
a{color:#D4AF37}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.card{background:#141B2B;border:1px solid #23304A;border-radius:12px;padding:18px}
.card b{font-size:26px;color:#fff;display:block;word-break:break-word}
.card span{color:#8A93A8;font-size:12px;text-transform:uppercase}
input,textarea,select,button{font:14px system-ui,sans-serif;padding:10px;border-radius:8px;
 border:1px solid #23304A;background:#141B2B;color:#E8EAF0}
textarea{width:100%;min-height:90px;box-sizing:border-box}
label{display:flex;flex-direction:column;gap:5px;color:#8A93A8;font-size:12px;margin-bottom:12px}
button{cursor:pointer;background:#1E7A45;font-weight:700}
button:disabled{background:#6B2737;cursor:wait}
pre{background:#101624;border:1px solid #23304A;padding:16px;border-radius:10px;
 overflow:auto;max-height:320px;white-space:pre-wrap}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:8px;border-bottom:1px solid #23304A;text-align:left}
#msg{color:#D4AF37;min-height:22px;margin-top:8px}
</style></head><body>
<h1>Doctor Time Video Creator</h1>
<div class="sub">Direct local video maker · no scheduler · no upload · <a href="/studio">🎬 3D Thumbnail Studio</a> · <span id="toolsInfo"></span></div>

<h2>Banega kya?</h2>
<form id="form" onsubmit="start(event)">
 <label>Topic<input id="topic" required placeholder="jaise: All Roads Lead to Rome"></label>
 <label>Timeline (ek line ya '|' se alag) — research isi se hogi
  <textarea id="timeline" placeholder="Road building|Trade networks|Imperial postal system|Legacy"></textarea></label>
 <div class="grid" style="margin-bottom:12px">
  <label>Minutes<input id="minutes" type="number" min="1" max="180" value="8"></label>
  <label>Language<select id="lang">
    <option value="both">Hindi + English</option><option value="hi">Hindi</option><option value="en">English</option>
  </select></label>
 </div>
 <button id="go" type="submit">🎥 VIDEO BANAO</button>
</form>
<div id="msg"></div>
<pre id="progress">Ready.</pre>

<h2>Production Stats</h2><div class="grid" id="stats"></div>
<h2>Videos</h2><div id="videos"></div>
<script>
async function load(){
 const t=await (await fetch('/api/tools')).json();
 document.getElementById('toolsInfo').textContent=`${t.installed}/${t.count} tools vendored`;
 const s=await (await fetch('/api/stats')).json();
 document.getElementById('stats').innerHTML=Object.entries(s).map(([k,v])=>
   `<div class="card"><b>${v}</b><span>${k}</span></div>`).join('');
 const videos=await (await fetch('/api/videos')).json();
 document.getElementById('videos').innerHTML='<table><tr><th>Title</th><th>Lang</th><th>Status</th><th>Duration</th></tr>'+
   videos.map(v=>`<tr><td>${v.title}</td><td>${v.language}</td><td>${v.status}</td><td>${Math.round(v.duration||0)}s</td></tr>`).join('')+'</table>';
}
async function poll(){
 const s=await (await fetch('/api/make/status')).json();
 document.getElementById('progress').textContent=s.log||'Ready.';
 document.getElementById('msg').textContent=s.message||'';
 document.getElementById('go').disabled=!!s.running;
 if(s.running)setTimeout(poll,2500); else load();
}
async function start(e){
 e.preventDefault();
 const lang=document.getElementById('lang').value;
 const body={topic:document.getElementById('topic').value,
   timeline:document.getElementById('timeline').value,
   minutes:parseFloat(document.getElementById('minutes').value),
   languages:lang==='both'?['hi','en']:[lang]};
 const r=await fetch('/api/make',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify(body)});
 const d=await r.json();
 document.getElementById('msg').textContent=d.error||'Video ban raha hai…';
 poll();
}
load();poll();
</script></body></html>"""


_JOB: dict[str, Any] = {"running": False, "log": "Ready.", "message": "", "result": None}


def create_app():
    import base64
    from pathlib import Path

    from flask import Flask, jsonify, request, send_from_directory

    from common.paths import ROOT
    from common.utils import iso_now
    from skills.tool_registry import report as tools_report

    app = Flask(__name__)
    db = Database()

    @app.route("/")
    def index():
        return HTML

    @app.route("/favicon.ico")
    def favicon():
        return "", 204

    @app.route("/studio")
    def studio():
        return send_from_directory(Path(__file__).parent, "studio.html")

    @app.route("/vendor/<path:filename>")
    def vendor_file(filename):
        return send_from_directory(ROOT / "vendor", filename)

    @app.route("/static-three/<path:filename>")
    def studio_three(filename):
        return send_from_directory(Path(__file__).parent / "static" / "three", filename)

    @app.route("/api/tools")
    def tools():
        return jsonify(tools_report())

    @app.route("/api/studio/save", methods=["POST"])
    def studio_save():
        payload = request.get_json(silent=True) or {}
        data = str(payload.get("image", ""))
        if not data.startswith("data:image/"):
            return jsonify({"error": "no image data"}), 400
        raw = base64.b64decode(data.split(",", 1)[1])
        dest = ROOT / "local_agent" / "assets" / "thumbnails"
        dest.mkdir(parents=True, exist_ok=True)
        name = "studio_" + iso_now().replace(":", "-") + ".jpg"
        path = dest / name
        path.write_bytes(raw)
        log.info("3D studio thumbnail saved: %s (%d bytes)", path, len(raw))
        return jsonify({"ok": True, "path": str(path), "bytes": len(raw),
                        "title": payload.get("title", "")})

    @app.route("/api/stats")
    def stats():
        return jsonify(db.stats())

    @app.route("/api/videos")
    def videos():
        return jsonify(db.records("videos", 100))

    @app.route("/api/make/status")
    def make_status():
        return jsonify(_JOB)

    @app.route("/api/make", methods=["POST"])
    def make():
        if _JOB["running"]:
            return jsonify({"error": "ek video already ban raha hai"}), 409
        payload = request.get_json(silent=True) or {}
        topic = str(payload.get("topic", "")).strip()
        if not topic:
            return jsonify({"error": "topic required"}), 400
        timeline = str(payload.get("timeline", ""))
        minutes = float(payload.get("minutes", 8) or 8)
        languages = payload.get("languages") or ["hi", "en"]

        def worker():
            from make_video import make_video
            lines = [_JOB["log"]]

            def progress(msg: str) -> None:
                lines.append(msg)
                _JOB["log"] = "\n".join(lines[-40:])

            try:
                result = make_video(topic, timeline, minutes,
                                    languages=languages, progress=progress)
                _JOB["result"] = result
                _JOB["message"] = "VIDEO BAN GAYA — REPORT.txt ready"
                progress("VIDEO BAN GAYA ✅")
            except Exception as exc:  # noqa: BLE001
                log.exception("Video job failed")
                _JOB["message"] = f"Error: {exc}"
                progress(f"Error: {exc}")
            finally:
                _JOB["running"] = False

        _JOB.update({"running": True, "log": "Started: " + topic,
                     "message": "", "result": None})
        threading.Thread(target=worker, daemon=True).start()
        return jsonify({"ok": True, "message": "video ban raha hai"})

    return app


def run_dashboard() -> None:
    import os as _os
    port = int(_os.environ.get("DASHBOARD_PORT", 8080))
    log.info("Dashboard starting on port %d", port)
    create_app().run(host="0.0.0.0", port=port, debug=False)
