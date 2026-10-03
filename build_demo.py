#!/usr/bin/env python3
"""Build a self-contained static demo page from a real captured audit.

Reads a False Green audit JSON (as produced by `curl /api/audit` on demo_server.py) and
writes a single HTML file with no external dependencies, so it can be hosted anywhere --
GitHub Pages, any static host, or opened from disk. The audit data is embedded verbatim, so
the page shows a real run, not a mock.

    python3 build_demo.py /tmp/real_audit.json index.html
"""
import html
import json
import sys

TPL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>False Green — does your monitoring actually monitor?</title>
<style>
  :root{{--bg:#0e1116;--card:#151b23;--ink:#e8edf3;--dim:#8b98a8;--red:#ff5c5c;--grn:#39d98a;--amb:#f5b942}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}}
  header{{padding:48px 24px 12px;max-width:1000px;margin:0 auto}}
  h1{{font-size:28px;margin:0 0 8px}}
  .sub{{color:var(--dim);max-width:74ch}}
  main{{max-width:1000px;margin:0 auto;padding:12px 24px 72px}}
  table{{width:100%;border-collapse:collapse;margin-top:16px;font-size:14px}}
  th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid #232c37}}
  th{{color:var(--dim);font-weight:600}}
  .REAL{{color:var(--grn)}}.GREEN_OVER_NOTHING{{color:var(--red);font-weight:700}}.UNKNOWN{{color:var(--amb)}}
  .card{{background:var(--card);border:1px solid #232c37;border-radius:14px;padding:20px;margin-top:18px}}
  .verdicts{{display:flex;gap:26px;flex-wrap:wrap;margin-top:6px}}
  .big{{font-size:36px;font-weight:800}}
  .lbl{{color:var(--dim);font-size:12px;letter-spacing:.06em;text-transform:uppercase}}
  .gpu{{color:var(--dim);font-size:13px}}
  a{{color:var(--grn)}}
  code{{background:#0a0d11;border:1px solid #232c37;border-radius:6px;padding:2px 6px}}
  pre{{background:#0a0d11;border:1px solid #232c37;border-radius:10px;padding:14px;overflow:auto;font-size:13px}}
</style></head>
<body>
<header>
  <h1>False Green</h1>
  <div class="sub">Your AI pipeline says everything is fine. This checks whether it actually
  looked. False Green injects the silent failures production AI dies from and audits whether a
  pipeline's own health signal notices. Verdicts: <b>REAL</b>, <b
  style="color:var(--red)">GREEN_OVER_NOTHING</b>, or <b style="color:var(--amb)">UNKNOWN</b> — and
  UNKNOWN is never green.</div>
</header>
<main>
  <div class="card">
    <div class="verdicts">
      <div><div class="big" style="color:var(--red)">{bad}</div><div class="lbl">green-over-nothing</div></div>
      <div><div class="big" style="color:var(--grn)">{good}</div><div class="lbl">real</div></div>
      <div><div class="big" style="color:var(--amb)">{unk}</div><div class="lbl">unknown</div></div>
    </div>
    <div class="gpu" style="margin-top:12px">Capture: {stamp} · AMD residency: {residency}</div>
  </div>
  <table>
    <tr><th>injected failure</th><th>monitor reported</th><th>truth</th><th>verdict</th><th>pipeline</th></tr>
    {rows}
  </table>
  <div class="card">
    <div class="lbl">Run it yourself</div>
    <pre>git clone https://github.com/Sophia-Thickums/greenover
cd greenover
python3 -m falsegreen --selftest
python3 -m falsegreen --demo</pre>
    <div class="gpu">Source, tests and the non-vacuous selftest: <a href="https://github.com/Sophia-Thickums/greenover">github.com/Sophia-Thickums/greenover</a>. MIT.</div>
  </div>
</main>
</body></html>"""


def build(src: str, dst: str) -> None:
    d = json.load(open(src))
    findings = d["findings"]
    bad = sum(1 for f in findings if f["verdict"] == "GREEN_OVER_NOTHING")
    good = sum(1 for f in findings if f["verdict"] == "REAL")
    unk = sum(1 for f in findings if f["verdict"] == "UNKNOWN")
    rows = "\n    ".join(
        f'<tr><td>{html.escape(f["injection"])}</td><td>{html.escape(f["monitor_said"])}</td>'
        f'<td>{html.escape(f["truth"])}</td><td class="{f["verdict"]}">{f["verdict"]}</td>'
        f'<td class="gpu">{html.escape(f.get("pipeline", ""))}</td></tr>'
        for f in findings
    )
    out = TPL.format(bad=bad, good=good, unk=unk, rows=rows,
                     residency=html.escape(d.get("residency", "unknown")),
                     stamp="2026-10-03 18:22 CDT")
    open(dst, "w").write(out)
    print(f"wrote {dst}: {len(out)} bytes, {len(findings)} findings ({bad} bad / {good} real / {unk} unknown)")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "index.html")
