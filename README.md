# False Green

**Your AI pipeline says everything is fine. False Green checks whether it actually looked.**

False Green is chaos engineering for AI pipelines. It does not watch your pipeline — it
**attacks** it with the silent failures that production AI dies from, then reads your pipeline's
own health signal to see whether it noticed. Every check gets one of three verdicts:

| verdict | meaning |
|---|---|
| **REAL** | the monitor caught the injected failure |
| **GREEN_OVER_NOTHING** | the monitor reported *healthy* while the failure was live |
| **UNKNOWN** | the check could not be judged — **never** treated as green |

## Quick start (zero setup, no GPU, no network)

```bash
git clone https://github.com/Sophia-Thickums/falsegreen
cd falsegreen
python3 -m falsegreen --selftest   # proves each rule can go RED, and the control stays GREEN
python3 -m falsegreen --demo       # audits two example pipelines and prints the report
```

That is the whole barrier to entry. No arguments, no config, no model, no hardware.

## Live demo

- **Hosted demo:** https://sophia-thickums.github.io/greenover/
- **Run it locally with a web UI:** `python3 demo_server.py` → http://127.0.0.1:8099
  (standard library only; shows a live audit and the live AMD residency read)

## What it injects

Each injection is a real failure class, not a synthetic assertion:

| injection | the failure it reproduces |
|---|---|
| `empty_output` | the model returns `""` and a division guard turns "no data" into a tidy `0.000` |
| `cpu_fallback` | GPU residency is lost; the workload silently runs on CPU while the dashboard reads healthy |
| `budget_exhausted` | the model spends its whole budget in a hidden reasoning channel and reports a clean result over no data |
| `check_not_run` | the monitor itself never fires, so "zero problems" and "could not look" share one output |
| `truncated` | the output is cut at the token cap and the run is reported as success |

These are drawn from a first-person catalogue of measured failures. The governing principle:

> **A check must be able to express the failure it exists to catch.**

A check that can pass while the thing it guards is absent is worse than no check at all — it
manufactures confidence.

## Running against a real pipeline (AMD / ROCm)

Point it at a live generation pipeline on AMD hardware. The residency sensor reads the platform
directly — `rocm-smi`, no root — pins devices **by PCI bus, never by index**, and **fails closed**:
if it cannot read residency it reports `UNKNOWN`, never a green. A workload that thinks it is on
the GPU while the GPU sits idle is the most expensive silent failure in local AI, and this is the
instrument that can tell the difference.

```python
from falsegreen import OllamaPipeline, audit

pipeline = OllamaPipeline("your-local-model", monitor_style="naive")
report = audit(pipeline, probe=my_injection_probe)
print(report.to_markdown())
```

Where an injection can be produced for real on the host it is; where it cannot, it is applied
through a probe seam and **labelled SIMULATED in the report**. Nothing here overclaims.

## Verify it does what it says

```bash
python3 -m falsegreen --selftest     # exit 0 = pass, 1 = a rule misbehaved, 2 = usage
python3 -m unittest discover -s tests
```

The selftest is deliberately **non-vacuous**: it removes the rule each check exists to exercise
and confirms the verdict **degrades to `UNKNOWN`** rather than passing. A green suite over a test
that cannot fail is theatre; this one has been watched going red.

## Findings: the standard patterns are green over nothing

Run `python3 audit_reference_pipelines.py` to audit the reference pipeline shapes that ship in
tutorials and quickstarts. On the five modelled here:

**5 of 5 were green over nothing on at least one silent-failure class.** The two classes *no*
scaffold catches are device residency and the monitor's own liveness — because those need a
sensor the pipeline does not have, not a smarter check. See `audit_reference_pipelines.py`.

## Prior art, and how this differs

The adjacent work is real and worth naming, because a tool that pretends to be the first is a
tool that didn't look:

- **Silent-failure detectors** (`silentwatch-mcp`, `agent-coroner`, Vigil/MCPWatch) watch a
  production system's *logs and outputs* and flag runs that exited 0 but produced nothing.
- **Agent observability platforms** (Flowlines, Raindrop, Langfuse, Arize) read the traces you
  already collect and surface behavioural failures after the fact.

False Green is a different layer: it **injects** the failures and asks whether your monitoring
would have **fired** — fault injection aimed at the monitoring itself, not telemetry analysis.
It is the difference between a smoke detector you bought and a test that deliberately lights a
fire under it. The verdict is per-check (`REAL` / `GREEN_OVER_NOTHING` / `UNKNOWN`), and it is
**AMD/ROCm residency-aware** — the CPU-fallback class is measured against the actual devices, not
inferred from the workload's own report.

If you already run a silent-failure detector, False Green audits whether *it* can see what it
claims to. The two compose.

## What it does NOT do

- It does not prove your pipeline is correct, only whether its monitoring can see the failure
  classes above. A tool that claims certainty gets discounted; this one states its limits.
- It is not a replacement for tracing or evals — it is the layer that asks whether those signals
  would have fired.
- The residency sensor covers AMD ROCm via `rocm-smi`. On a host without it, residency is
  `UNKNOWN`, and `UNKNOWN` is not green.

## Why this exists

The primary obstacle to honest claims about AI systems is not capability. It is **measurement** —
tools that fail not by returning `wrong` answers, but by returning *confident, well-formed answers
about things they are not in fact observing*. False Green turns that thesis into a command you
can run against your own stack.

MIT licensed. Built for anyone shipping AI on real infrastructure.
