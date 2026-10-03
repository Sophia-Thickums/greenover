#!/usr/bin/env python3
"""
False Green — a zero-dependency web demo.

Serves a single page that runs a live audit against a pipeline and shows, per check, whether
the pipeline's own monitoring noticed. Standard library only: no Flask, no FastAPI, no build
step. Deploys anywhere Python runs.

    python3 demo_server.py            # http://127.0.0.1:8099
    python3 demo_server.py --port 80
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from falsegreen import Injection, Verdict, audit, NaivePipeline, HonestPipeline  # noqa: E402
from falsegreen.rocm import sample  # noqa: E402


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>False Green — does your monitoring actually monitor?</title>
<style>
  :root{--bg:#0e1116;--card:#151b23;--ink:#e8edf3;--dim:#8b98a8;--red:#ff5c5c;--grn:#39d98a;--amb:#f5b942}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
  header{padding:40px 24px 12px;max-width:1000px;margin:0 auto}
  h1{font-size:26px;margin:0 0 6px}
  .sub{color:var(--dim);max-width:70ch}
  main{max-width:1000px;margin:0 auto;padding:12px 24px 64px}
  button{background:var(--grn);color:#06210f;border:0;border-radius:9px;padding:12px 20px;font:inherit;
         font-weight:700;cursor:pointer;margin:18px 0}
  button[disabled]{opacity:.5;cursor:progress}
  table{width:100%;border-collapse:collapse;margin-top:14px;font-size:14px}
  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid #232c37}
  th{color:var(--dim);font-weight:600}
  .REAL{color:var(--grn)}.GREEN_OVER_NOTHING{color:var(--red);font-weight:700}.UNKNOWN{color:var(--amb)}
  .card{background:var(--card);border:1px solid #232c37;border-radius:14px;padding:20px;margin-top:18px}
  .verdicts{display:flex;gap:22px;flex-wrap:wrap;margin-top:6px}
  .big{font-size:34px;font-weight:800}
  .lbl{color:var(--dim);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
  .gpu{color:var(--dim);font-size:13px}
  a{color:var(--grn)}
</style></head>
<body>
<header>
  <h1>False Green</h1>
  <div class="sub">Your AI pipeline says everything is fine. This checks whether it actually
  looked. It injects the silent failures production AI dies from and audits whether the
  pipeline's own health signal notices. <b>UNKNOWN is never green.</b></div>
  <button id="run">Run the audit</button>
</header>
<main>
  <div id="summary" class="card" hidden><div class="verdicts" id="counts"></div></div>
  <div id="out"></div>
  <div class="card"><div class="lbl">AMD device residency (live)</div>
    <div id="gpu" class="gpu">…</div></div>
  <p class="gpu">Source: <a href="https://github.com/Sophia-Thickums/greenover">github.com/Sophia-Thickums/greenover</a></p>
</main>
<script>
async function run(){
  const b=document.getElementById('run'); b.disabled=true; b.textContent='Injecting failures…';
  try{
    const r=await fetch('/api/audit'); const d=await r.json();
    const n=d.findings, bad=n.filter(f=>f.verdict==='GREEN_OVER_NOTHING').length;
    const good=n.filter(f=>f.verdict==='REAL').length, unk=n.filter(f=>f.verdict==='UNKNOWN').length;
    document.getElementById('summary').hidden=false;
    document.getElementById('counts').innerHTML=
      `<div><div class="big" style="color:var(--red)">${bad}</div><div class="lbl">green-over-nothing</div></div>
       <div><div class="big" style="color:var(--grn)">${good}</div><div class="lbl">real</div></div>
       <div><div class="big" style="color:var(--amb)">${unk}</div><div class="lbl">unknown</div></div>`;
    document.getElementById('out').innerHTML=`<table><tr><th>injected failure</th><th>monitor reported</th>
      <th>truth</th><th>verdict</th></tr>${n.map(f=>`<tr><td>${f.injection}</td><td>${f.monitor_said}</td>
      <td>${f.truth}</td><td class="${f.verdict}">${f.verdict}</td></tr>`).join('')}</table>`;
    document.getElementById('gpu').textContent=d.residency;
  }catch(e){ document.getElementById('out').innerHTML='<div class="card">Audit failed: '+e+'</div>'; }
  b.disabled=false; b.textContent='Run the audit again';
}
document.getElementById('run').addEventListener('click',run);
fetch('/api/residency').then(r=>r.json()).then(d=>document.getElementById('gpu').textContent=d.residency).catch(()=>{});
</script>
</body></html>"""


def _residency_line() -> str:
    r = sample()
    if r.is_unknown:
        return f"UNKNOWN — {r.detail}"
    busy = ", ".join(g.name for g in (r.gpus or []) if g.busy) or "none"
    return f"{r.state} — {len(r.gpus or [])} AMD device(s); work on: {busy}"


def _run_audit() -> dict:
    findings = []
    for pl in (NaivePipeline(), HonestPipeline()):
        rep = audit(pl)
        for f in rep.findings:
            findings.append({"injection": f.injection.value, "monitor_said": f.monitor_said,
                             "truth": f.truth, "verdict": f.verdict.value,
                             "pipeline": rep.pipeline})
    return {"findings": findings, "residency": _residency_line()}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/audit"):
            self._send(200, json.dumps(_run_audit()).encode(), "application/json")
        elif self.path.startswith("/api/residency"):
            self._send(200, json.dumps({"residency": _residency_line()}).encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *a):  # quiet
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"False Green demo on http://{a.host}:{a.port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
