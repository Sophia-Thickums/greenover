# FALSE GREEN — slide deck (ACT III submission)

9 slides. Plain, engineer-facing, no filler. Each slide: what's on it, and what is said aloud.

---

**1 · TITLE**
- **False Green** — *Does your monitoring actually monitor?*
- Chaos engineering for AI pipelines · ROCm-aware
- Sophia Marie DeClue

**2 · THE HOOK**
- *"This health check says everything is fine."*
- Show a green status. Then: it has been returning empty responses for two minutes.
- **Nothing errored. It reported success the whole time.**

**3 · THE PROBLEM**
- Every pipeline is monitored; almost none of the checks can express the failure they exist to catch.
- `all clear` means two different things: *"no problems found"* and *"I could not look."*
- A check that passes while the thing it guards is absent **manufactures confidence.**

**4 · THE FAILURES (this is real, not hypothetical)**
- Silent CPU fallback → dashboard green, work 20–40× slower
- Empty output → a guard turns "no data" into a clean `0.000`
- Budget exhausted in a hidden reasoning channel → a result over no data
- The monitor never fires → "zero problems" and "couldn't look" share one output
- Truncation at the cap → reported as success

**5 · WHAT FALSE GREEN IS**
- Chaos engineering **aimed at the monitoring itself** — not telemetry analysis.
- It **injects** the failures and asks whether your check would have **fired**.
- A smoke detector *tests* the smoke detector.

**6 · THE VERDICTS**
- **REAL** — the monitor caught the injected failure
- **GREEN_OVER_NOTHING** — it reported healthy while the failure was live
- **UNKNOWN** — could not be judged — **never green**

**7 · THE DEMO (screenshot)**
- The naive monitor: **5 green-over-nothing**
- The honest monitor: **5 real**
- AMD residency panel: four devices, pinned by PCI bus, failing closed.

**8 · TECH — why the AMD stack is load-bearing**
- ROCm residency read live (`rocm-smi`; the residency signal is the instrument, not a badge)
- Pins by **PCI bus, never by index**; fails closed to UNKNOWN
- Runs against a live Ollama-on-ROCm pipeline; deployable to AMD Developer Cloud unchanged
- **Non-vacuous selftest:** remove a rule → the verdict degrades to UNKNOWN, never passes
- Pure Python stdlib core · MIT · one command, no install

**9 · VALUE + CLOSE**
- Every team running inference at scale ships at least one of these green-over-nothing checks and does not know which.
- Converts an invisible cost (wasted GPU-hours, corrupt metrics) into a per-check verdict.
- **`python3 -m falsegreen --selftest`**
- *Your pipeline says everything is fine. False Green checks whether it actually looked.*
- Repo: github.com/Sophia-Thickums/greenover · Demo: sophia-thickums.github.io/greenover

---

## Submission form copy (paste-ready)

**Title:** False Green — does your monitoring actually monitor?

**Short description (≤200 chars):**
> Chaos engineering for AI pipelines: injects silent failures — CPU fallback, empty output, exhausted budgets — and audits whether your monitoring catches them. ROCm-aware, fails closed.

**Long description:**
> Every AI pipeline is monitored, and almost none of the monitoring can express the failure it
> exists to catch. A health check that returns *all clear* for both "I found no problems" and
> "I could not look" is not a monitor — it manufactures confidence. In production that is where
> money dies silently: a model falls back to CPU and the dashboard stays green; a generation
> returns empty and a guard scores it a clean 0.000; a model spends its budget in a hidden
> reasoning channel and reports a result over no data.
>
> False Green is chaos engineering for AI pipelines. It does not watch your pipeline — it
> attacks it. It injects five failure classes that production AI actually dies from (empty
> output, silent CPU fallback, exhausted token budget, a monitor that never fired, truncation
> at the cap) and then reads the pipeline's own health signal to see whether it noticed. Each
> check returns one of three verdicts — REAL, GREEN_OVER_NOTHING, or UNKNOWN — and UNKNOWN is
> never treated as green: a check that cannot be judged is held, not waved through.
>
> It is AMD-native. Its ROCm residency sensor reads the actual devices (rocm-smi), pins them by
> PCI bus rather than index, and fails closed to UNKNOWN when it cannot read — because a
> workload that believes it is on the GPU while the GPU sits idle is the most expensive silent
> failure in local AI. It is demonstrated against a live Ollama-on-ROCm pipeline and deploys to
> AMD Developer Cloud unchanged.
>
> It ships with a non-vacuous selftest: it removes the rule each check exercises and confirms
> the verdict degrades to UNKNOWN rather than passing. A green suite over a test that cannot
> fail is theatre; this one has been watched going red. Pure Python standard library, MIT,
> zero setup: `python3 -m falsegreen --selftest`.

**Technology tags:** ROCm · AMD Instinct · PyTorch · observability · chaos engineering ·
AI agents · Python

**Category:** Agentic AI / Developer Tooling

**Repo:** https://github.com/Sophia-Thickums/greenover
**Demo URL:** https://sophia-thickums.github.io/greenover/
