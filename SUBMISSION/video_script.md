# FALSE GREEN — 3-minute video script (ACT III submission)

**Target: 180 seconds.** Screen recording + voiceover. No jargon in the first 20 seconds —
the judges are senior engineers but the video has to land for the room. Total budget: ~430
spoken words at a calm pace.

---

### 0:00 – 0:20 · THE HOOK  (screen: a green dashboard, calm)

> "This is a health check. It says everything is fine. Let me show you how I can make it lie —
> without touching the check itself."

*(Cut: the same dashboard, still green, while a red banner says the model returned nothing.)*

> "For two minutes, this pipeline has been returning empty responses. It reported success the
> whole time. Nothing errored. That's the failure I built a tool to catch."

### 0:20 – 1:00 · THE PROBLEM  (screen: the three verdicts on screen)

> "Every AI pipeline is monitored. Almost none of the monitoring can express the failure it
> exists to catch. A check that says *all clear* for both 'I found no problems' and 'I
> couldn't look' isn't a monitor — it's a machine for manufacturing confidence. In production
> that's where money dies quietly: the model silently falls back to CPU, the dashboard stays
> green; a generation returns empty and a guard turns it into a clean zero point zero zero
> zero; the model burns its whole budget in a hidden reasoning channel and reports a result
> over no data."

### 1:00 – 2:00 · THE DEMO  (screen: terminal, run the tool live)

> "False Green is chaos engineering for AI pipelines. It doesn't watch your pipeline — it
> attacks it."

*(Run: `python3 -m falsegreen --demo`. The naive monitor scores 5 green-over-nothing.)*

> "It injects five failures that production AI actually dies from — empty output, silent CPU
> fallback, exhausted token budget, truncation at the cap, and a monitor that never fired — and
> then it reads the pipeline's **own** health signal to see if it noticed. This pipeline
> reported *healthy* for all five. Every one of those green lights was over nothing."

*(Cut: the honest monitor, 5/5 REAL.)*

> "Point it at a monitor that can actually see those failures, and it scores them all real.
> Same failures. The difference is whether the check can express them."

*(Screen: the residency panel — four AMD devices, MI25 holding the model.)*

> "And it's measured against the real hardware, not the workload's own story. This reads the
> AMD devices directly — pinned by PCI bus, never by index — and if it can't read residency, it
> says unknown. Unknown is never treated as green."

### 2:00 – 2:40 · WHY IT MATTERS / BUSINESS VALUE  (screen: the report, then the repo)

> "Here's who this is for. Anyone running inference at scale on AMD: a silent CPU fallback is
> 20 to 40 times slower, invisibly. An empty output scored as a clean metric corrupts every
> number downstream. This tool turns an invisible cost into a per-check verdict a team can act
> on — and it runs on the AMD stack it audits."

*(Screen: the GitHub repo, the selftest going red and green.)*

> "It ships with a selftest that proves each rule can go red — remove the rule, and the verdict
> degrades to unknown rather than passing. A green suite over a test that cannot fail is
> theatre. This one has been watched failing."

### 2:40 – 3:00 · CLOSE  (screen: the one command)

> "You don't need our cloud, our hardware, or our setup. One command, no install:
>
> `python3 -m falsegreen --selftest`
>
> Your pipeline says everything is fine. False Green checks whether it actually looked."

---

## Production notes
- **Record the real terminal**, not a mock. The audit output in the video must match a run the
  judge can reproduce in one command.
- **Keep the AMD residency panel visible** during the demo — it is the "Application of
  Technology" evidence.
- **No figures in the first 20 seconds** — earn the number, then show it.
- **Captions** the whole way; many judges watch muted.
- One take of the voice if possible — a steady human read beats a polished synthetic one.
