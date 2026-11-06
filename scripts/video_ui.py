#!/usr/bin/env python3
"""Make-a-video page (scripts/radar.sh video-ui): paste or load a Content Package, click Make video, watch each Video
Studio step, play the result. Runs `scripts/radar.sh video` on this Mac (the Studio steps need your Claude Code login
and FilmCraft, so they can't run in Docker), one video at a time. Listens on 127.0.0.1 only; stdlib only.
"""

import json
import os
import re
import subprocess
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PORT = 3600
ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
job = {"running": False, "log": "", "video": None}
lock = threading.Lock()


def run(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(text)
    p = subprocess.Popen([ROOT / "scripts/radar.sh", "video", f.name], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    for line in p.stdout:
        job["log"] += line
        if m := re.search(r"DONE (.+\.mp4)$", line.strip()):
            job["video"] = m[1]
    code = p.wait()
    os.unlink(f.name)
    job["log"] += "\nFinished." if code == 0 else f"\nStopped (exit {code}): see the log above."
    job["running"] = False


class Handler(BaseHTTPRequestHandler):
    def reply(self, code: int, body: bytes, ctype: str = "text/plain; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.reply(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/status":
            self.reply(200, json.dumps(job).encode(), "application/json")
        elif path == "/package":
            try:
                # the JSON package: the Studio keeps every field (the Markdown parser drops the score time)
                self.reply(200, urllib.request.urlopen("http://localhost:8000/api/admin/content-package", timeout=15).read())
            except OSError as e:
                self.reply(502, f"Trend Radar API not reachable ({e}). Start it: scripts/radar.sh up".encode())
        elif path == "/video" and job["video"]:
            self.reply(200, Path(job["video"]).read_bytes(), "video/mp4")
        else:
            self.reply(404, b"not found")

    def do_POST(self):
        # Only this page may start a job: a website open in another tab could otherwise POST a topic here (CSRF),
        # and a rebound DNS name could too, so check both Origin and Host.
        if self.headers.get("Origin") not in ORIGINS or self.headers.get("Host") not in {o[7:] for o in ORIGINS}:
            return self.reply(403, b"forbidden")
        if urlparse(self.path).path != "/make":
            return self.reply(404, b"not found")
        text = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        if not text.strip():
            return self.reply(400, b"Paste a package or a topic first.")
        with lock:
            if job["running"]:
                return self.reply(409, b"A video is already being made.")
            job.update(running=True, log="", video=None)
        threading.Thread(target=run, args=(text,), daemon=True).start()
        self.reply(202, b"started")

    def log_message(self, *args):  # no request log on every 2 s poll
        pass


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Make a Video</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#2ea043}
@media (prefers-color-scheme: light){:root{--bg:#f6f8fa;--panel:#fff;--line:#d0d7de;--text:#1f2328;--muted:#59636e;--accent:#1a7f37}}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px} p{color:var(--muted);margin:0 0 16px} a{color:inherit}
textarea,pre{width:100%;box-sizing:border-box;background:var(--panel);color:var(--text);border:1px solid var(--line);
  border-radius:8px;padding:12px;font:13px/1.45 ui-monospace,monospace}
textarea{height:260px;resize:vertical} pre{max-height:380px;overflow:auto;white-space:pre-wrap}
.row{display:flex;gap:10px;margin:12px 0;flex-wrap:wrap;align-items:center}
button{border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:8px;padding:8px 14px;
  font:inherit;cursor:pointer}
button.go{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button:disabled{opacity:.5;cursor:default}
video{width:100%;max-width:360px;border-radius:12px;display:block;margin-top:12px;background:#000}
#state{color:var(--muted)}
</style></head><body><main>
<h1>Make a video</h1>
<p>Paste the package from <a href="http://localhost:3100/admin" target="_blank">Radar admin</a> (Copy button) or load
today's. Your Video Studio makes it on this Mac: research, script, safety check, voice, animation, edit.
Nothing is published.</p>
<div class="row"><button id="load">Load today's package</button></div>
<textarea id="input" placeholder="Paste the Content Package (Markdown or JSON), or one topic line"></textarea>
<div class="row"><button class="go" id="make">Make video</button><span id="state"></span></div>
<pre id="log" hidden></pre>
<div id="result"></div>
<script>
const $ = id => document.getElementById(id);
$('load').onclick = async () => {
  const r = await fetch('/package'), t = await r.text();
  if (r.ok) { $('input').value = t; $('state').textContent = ''; } else $('state').textContent = t;
};
$('make').onclick = async () => {
  const r = await fetch('/make', {method: 'POST', body: $('input').value});
  if (!r.ok) { $('state').textContent = await r.text(); return; }
  poll();
};
async function poll() {
  const s = await (await fetch('/status')).json();
  $('make').disabled = s.running;
  $('log').hidden = !s.log; $('log').textContent = s.log; $('log').scrollTop = 1e9;
  $('state').textContent = s.running ? 'Making the video. Each step shows its start time; the edit takes longest.' : '';
  $('result').innerHTML = s.video && !s.running ? '<video src="/video?t=' + Date.now() + '" controls></video>' +
    '<div class="row"><a href="/video" download="video.mp4">Download MP4</a></div>' : '';
  if (s.running) setTimeout(poll, 2000);
}
poll();
</script></main></body></html>
"""

if __name__ == "__main__":
    print(f"Make-a-video page: http://127.0.0.1:{PORT}  (Ctrl+C stops it)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
