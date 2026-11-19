"""Lightweight Flask dashboard with live ON/OFF automation controls."""
from __future__ import annotations

from common.config import load_settings
from common.control import automation_enabled, set_automation_enabled, set_upload_enabled, upload_override
from common.logging_setup import get_logger
from database.manager import Database
from scheduler.scheduler import Scheduler

log = get_logger("dashboard")

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Documentary Factory — Dashboard</title>
<style>
body{background:#0B0F19;color:#E8EAF0;font:15px system-ui,sans-serif;margin:0;padding:28px}
h1{color:#D4AF37;margin:0 0 4px}h2{color:#D4AF37;font-size:18px;margin-top:32px}
.sub{color:#8A93A8;margin-bottom:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.card{background:#141B2B;border:1px solid #23304A;border-radius:12px;padding:18px}
.card b{font-size:30px;color:#fff;display:block}.card span{color:#8A93A8;font-size:12px;text-transform:uppercase}
button{margin-top:12px;width:100%;padding:10px;border:0;border-radius:8px;font-weight:700;cursor:pointer}
.on{background:#1E7A45;color:#fff}.off{background:#6B2737;color:#fff}
pre{background:#101624;border:1px solid #23304A;padding:16px;border-radius:10px;overflow:auto;max-height:280px}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:8px;border-bottom:1px solid #23304A;text-align:left}
#msg{color:#8A93A8;min-height:20px;margin-top:8px}
</style></head><body>
<h1>AI Documentary Factory</h1><div class="sub">Live automation status — updates every 15 seconds · <a href="/studio" style="color:#D4AF37">🎬 3D Thumbnail Studio</a> · <span id="toolsInfo"></span></div>

<h2>Automation Control</h2>
<div class="grid">
  <div class="card"><b id="autoState">—</b><span>Master Automation</span>
    <button id="autoBtn" onclick="toggle('automation')">Toggle</button></div>
  <div class="card"><b id="uploadState">—</b><span>YouTube Upload</span>
    <button id="uploadBtn" onclick="toggle('upload')">Toggle</button></div>
</div>
<div id="msg"></div>

<h2>Production Stats</h2><div class="grid" id="stats"></div>
<h2>Production Schedule</h2><pre id="schedule"></pre>
<h2>Recent Runs</h2><div id="runs"></div>
<h2>Videos</h2><div id="videos"></div>

<script>
let control={};
async function loadControl(){
 control=await (await fetch('/api/control')).json();
 const a=control.automation_enabled, u=control.upload_enabled;
 document.getElementById('autoState').textContent=a?'ON':'OFF';
 document.getElementById('uploadState').textContent=u?'ON':'OFF';
 const ab=document.getElementById('autoBtn'), ub=document.getElementById('uploadBtn');
 ab.className=a?'on':'off'; ub.className=u?'on':'off';
 ab.textContent=a?'Turn OFF':'Turn ON'; ub.textContent=u?'Turn OFF (go live)':'Turn ON (go live)';
}
async function toggle(name){
 const key=name==='automation'?'automation_enabled':'upload_enabled';
 const r=await fetch('/api/control/'+name,{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({enabled:!control[key]})});
 const d=await r.json();
 document.getElementById('msg').textContent=d.message||'';
 loadControl();
}
async function load(){
 await loadControl();
 const t=await (await fetch('/api/tools')).json();
 document.getElementById('toolsInfo').textContent=`${t.installed}/${t.count} tools vendored`;
 const s=await (await fetch('/api/stats')).json();
 document.getElementById('stats').innerHTML=Object.entries(s).map(([k,v])=>
   `<div class="card"><b>${v}</b><span>${k}</span></div>`).join('');
 document.getElementById('schedule').textContent=JSON.stringify(
   await (await fetch('/api/schedule')).json(),null,2);
 const runs=await (await fetch('/api/runs')).json();
 document.getElementById('runs').innerHTML='<table><tr><th>Stage</th><th>Status</th><th>Started</th></tr>'+
   runs.map(r=>`<tr><td>${r.stage}</td><td>${r.status}</td><td>${r.started_at}</td></tr>`).join('')+'</table>';
 const videos=await (await fetch('/api/videos')).json();
 document.getElementById('videos').innerHTML='<table><tr><th>Title</th><th>Lang</th><th>Status</th><th>Duration</th></tr>'+
   videos.map(v=>`<tr><td>${v.title}</td><td>${v.language}</td><td>${v.status}</td><td>${Math.round(v.duration||0)}s</td></tr>`).join('')+'</table>';
}
load();setInterval(load,15000);
</script></body></html>"""


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

    @app.route("/api/control")
    def control_state():
        upload = upload_override()
        if upload is None:
            upload = bool(load_settings().get("upload", {}).get("enabled", False))
        return jsonify({
            "automation_enabled": automation_enabled(),
            "upload_enabled": bool(upload),
            "upload_mode": "live" if upload else "dry-run",
        })

    @app.route("/api/control/<name>", methods=["POST"])
    def set_control(name):
        payload = request.get_json(silent=True) or {}
        if "enabled" not in payload:
            return jsonify({"error": "missing 'enabled'"}), 400
        enabled = bool(payload["enabled"])
        if name == "automation":
            set_automation_enabled(enabled)
            message = f"Master automation turned {'ON' if enabled else 'OFF'}"
        elif name == "upload":
            set_upload_enabled(enabled)
            message = f"YouTube upload turned {'ON (live)' if enabled else 'OFF (dry-run)'}"
        else:
            return jsonify({"error": "unknown switch"}), 404
        log.info(message)
        return jsonify({"ok": True, "message": message})

    @app.route("/api/stats")
    def stats():
        return jsonify(db.stats())

    @app.route("/api/schedule")
    def schedule():
        return jsonify(Scheduler().plan())

    @app.route("/api/<table>")
    def table(table):
        if table not in {"topics", "research", "scripts", "videos", "analytics", "runs", "errors"}:
            return jsonify({"error": "unknown table"}), 404
        return jsonify(db.records(table, 100))

    return app


def run_dashboard() -> None:
    import os as _os
    port = int(_os.environ.get("DASHBOARD_PORT", 8080))
    log.info("Dashboard starting on port %d", port)
    create_app().run(host="0.0.0.0", port=port, debug=False)
