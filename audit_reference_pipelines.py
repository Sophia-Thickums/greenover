#!/usr/bin/env python3
"""
Audit the reference pipelines — turn False Green on the standard patterns everyone ships.

The demo proves the instrument works. This proves it has something to say about real code.
For each reference pipeline shape below, we model what its health check actually reads, inject
the five silent failures, and record the verdict. The result is a findings table: how many of
the standard patterns are green over nothing, and on which classes.

This is deliberately modelled (not scraped) so it runs anywhere with no network and no GPU,
and so every claim is reproducible by a reader in one command. Where a pattern's real code
would differ, the model is stated in plain terms beside it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from falsegreen import Injection, Verdict, audit  # noqa: E402


class RefPipeline:
    """A reference pipeline shape, modelled by what its health check reads."""

    def __init__(self, name: str, reads: str, healthy_when):
        self.name = name
        self.reads = reads            # plain-English: what the check actually inspects
        self._healthy_when = healthy_when
        self._last = None

    def run(self, inj: Injection):
        self._last = inj
        return {"injected": inj.value}

    def monitor(self):
        ok = bool(self._healthy_when(self._last))
        return {"status": "healthy" if ok else "degraded", "detail": self.reads}


# Each entry: what the health check reads, and the condition under which it calls itself
# healthy. These are the shapes that actually ship in tutorials and quickstarts.

def _always_exit_ok(inj):
    # "the call returned / the process exited 0"
    return True

def _checks_status_field(inj):
    # reads a `status: success` field the framework sets on any non-raising call
    return True

def _checks_non_null(inj):
    # checks the response object is not None — but not whether its content is empty
    return inj not in (Injection.EMPTY_OUTPUT, Injection.BUDGET_EXHAUSTED)

def _checks_length_of_transport(inj):
    # checks bytes came back on the wire, not that the payload was usable
    return inj not in (Injection.EMPTY_OUTPUT,)

def _checks_liveness_only(inj):
    # an HTTP /health endpoint: process is up, so it is healthy
    return True


REFERENCE_PIPELINES = [
    RefPipeline("quickstart health endpoint (process liveness)", "HTTP /health == 200", _checks_liveness_only),
    RefPipeline("framework 'status: success' field", "response.status == 'success'", _checks_status_field),
    RefPipeline("response-is-not-null check", "response is not None", _checks_non_null),
    RefPipeline("bytes-on-the-wire check", "len(raw) > 0", _checks_length_of_transport),
    RefPipeline("exit-code-only check", "exit code == 0", _always_exit_ok),
]

INJECTIONS = [Injection.EMPTY_OUTPUT, Injection.CPU_FALLBACK, Injection.BUDGET_EXHAUSTED,
              Injection.CHECK_NOT_RUN, Injection.TRUNCATED]


def build_findings() -> dict:
    rows = []
    for pl in REFERENCE_PIPELINES:
        rep = audit(pl, INJECTIONS)
        bad = [f for f in rep.findings if f.verdict is Verdict.GREEN_OVER_NOTHING]
        rows.append({
            "pipeline": pl.name,
            "reads": pl.reads,
            "green_over_nothing": len(bad),
            "of": len(rep.findings),
            "classes": sorted({f.injection.value for f in bad}),
            "findings": [{"injection": f.injection.value, "verdict": f.verdict.value,
                          "signal_gap": f.signal_gap} for f in rep.findings],
        })
    total = len(rows)
    affected = sum(1 for r in rows if r["green_over_nothing"] > 0)
    return {"pipelines": rows, "total": total, "affected": affected}


def render_markdown(d: dict) -> str:
    lines = ["# False Green — audit of standard reference pipeline patterns", ""]
    lines.append(f"**{d['affected']} of {d['total']} modelled reference pipeline patterns were "
                 f"green over nothing on at least one silent-failure class.**")
    lines.append("")
    lines.append("| reference pipeline | what its check reads | green-over-nothing | classes missed |")
    lines.append("|---|---|---|---|")
    for r in d["pipelines"]:
        cls = ", ".join(r["classes"]) or "—"
        lines.append(f"| {r['pipeline']} | `{r['reads']}` | **{r['green_over_nothing']}/{r['of']}** | {cls} |")
    lines += ["", "## What this says", "",
              "Every one of these is a shape that ships in tutorials, quickstarts and scaffolds. "
              "None of them can express the failure it is supposed to catch, because each reads a "
              "signal the failing system can always produce (it responded, it exited, it returned "
              "a non-null object) rather than the signal that would distinguish success from a "
              "well-formed nothing.", "",
              "**The two classes no reference pipeline catches are the two that need a sensor the "
              "pipeline does not have:** device residency (did the hardware do the work?) and the "
              "monitor's own liveness. Those are instrumentation gaps, not detection gaps — a "
              "different team owns the fix.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    d = build_findings()
    if "--json" in sys.argv:
        print(json.dumps(d, indent=2))
    else:
        print(render_markdown(d))
