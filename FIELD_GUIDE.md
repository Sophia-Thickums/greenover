# A Field Guide to Silent AI Failures

*What a green dashboard does not tell you.*

Every incident here shares one shape: **the system reported success, and the report was
well-formed, confident, and about something that was not happening.** None of these throw. None
of these page anyone. They are the failures that surface weeks later as an invoice, a corrupted
eval, or a customer who stopped trusting the product.

Each entry: what you see, the minimal repro, the telemetry signature, and the detection rule.
None of these require a model — the detections are deterministic.

---

## 1 · Silent CPU fallback

**What you see.** The service is up. Requests return 200. The dashboard is green. The work is
running on the CPU, 20–40× slower, and every GPU in the box is idle.

**Minimal repro.** In a container or a fresh environment, set `ROCR_VISIBLE_DEVICES` (or fail to
pass it), then let the app auto-select a device:

```python
device = "cuda" if torch.cuda.is_available() else "cpu"   # silently degrades, never errors
```

**Telemetry signature.** The application's own logs are silent. The platform says otherwise:
flat VRAM, no compute processes on the accelerators, no GPU kernels dispatched.

**Detection rule.** Success is *not* the signal. The signal is residency: at the moment a
generation ran, did an accelerator hold the model and show compute? Ask the platform, not the
app. If you cannot read residency, that is not a pass — it is **UNKNOWN**, and unknown is not
green.

**Why it hides.** The app's health check asks a question the app can always answer (did I
respond?) instead of the question that matters (did the hardware do it?).

---

## 2 · Empty output scored as a number

**What you see.** A metric. A clean `0.000`, or a `1.0`, or a percentage. A results file with
correct-looking structure and a passing exit code.

**Minimal repro.** A model returns `""` (truncation, a refusal, a content filter, a bad prompt
assembly). Downstream, a guard turns "nothing" into a number:

```python
score = hits / max(total, 1)     # total == 0  ->  0.0, a confident number over no data
```

**Telemetry signature.** Every field is present and well-formed; the *lengths* are zero. A
results file exists and no run is inside it.

**Detection rule.** **Never score emptiness as a result.** The gate belongs *before* the
arithmetic, and the run must be able to say "I could not measure" instead of returning a figure.
A division guard that manufactures `0.000` from no data is a fabricated measurement wearing a
number.

---

## 3 · The budget spent in a hidden channel

**What you see.** `finish_reason: length`, `exit 0`, a well-formed response object — and an
empty `content` field. The model spent its entire token budget in a hidden reasoning channel
and never produced an answer. The pipeline logs success.

**Minimal repro.** Run a reasoning model with a small `max_tokens`:

```bash
# content comes back empty; finish_reason == "length"; nothing raises
```

**Telemetry signature.** Output tokens ≈ budget, visible output ≈ zero, finish reason = length.

**Detection rule.** Compare **produced output against the budget consumed.** A run that
consumed its whole budget and emitted nothing failed, whatever its status code says. If you
serve reasoning models without a reasoning parser, you cannot see this at all — it is not a
detection gap, it is a missing sensor.

---

## 4 · The truncation nobody checked

**What you see.** A valid response, a success status. The JSON is cut in the middle, or the
article ends mid-sentence, and everything downstream treats it as complete.

**Minimal repro.** Ask a model for output longer than the cap. Take the response. Do not look
at `finish_reason`.

**Telemetry signature.** `finish_reason == "length"` (or the provider's equivalent) sitting
right there in the response the pipeline already received.

**Detection rule.** Truncation is a **success with a truncated payload**; it needs an explicit
check, not an inference. This is the clearest "signal existed and was ignored" case in the
book — the answer was in the response body and the monitor never read it.

---

## 5 · The check that never ran

**What you see.** `all clear`. The monitor is present, deployed, and green.

**Minimal repro.** A monitor whose status variable initialises to a passing state, and whose
"no data" path returns the same value as its "no problems found" path:

```python
status = "healthy"          # initialised passing
if checked and found: status = "degraded"
return status               # a check that never fired reads exactly like a clean one
```

**Telemetry signature.** None from the checker itself — which is the point. The signature is
absence: no run records, no timestamps advancing, an artifact directory that has not changed.

**Detection rule.** **A check must be able to express the failure it exists to catch.** A
verification that passes when the thing it guards is absent is worse than no verification,
because it manufactures confidence. The fix is structural: initialise to **UNKNOWN**, and make
unknown **hold** rather than pass.

---

## The pattern, stated once

> An instrument rarely fails by returning a *wrong* answer. It fails by returning a **confident,
> well-formed answer about a thing it is not observing.**

Every entry above is that sentence wearing different clothes. Which is why the detection
principle is not "check more" — it is:

> **Make every check able to say "I could not look," and never let that sound like "all clear."**

## Detection gap vs. instrumentation gap

Two different failures with two different fixes. Sort every finding into one of them:

- **Existed and ignored** — the signal was in hand and the check did not read it. (Empty output,
  truncation, budget exhaustion.) *Fix: the check. Owner: the application team.*
- **Never instrumented** — the pipeline holds no sensor for it at all. (Device residency, the
  monitor's own liveness.) *Fix: add the sensor before it can fire. Owner: the platform team.*

A tool that reports only "you failed" is a script. A tool that tells you **whether the signal
was there to read** tells you which team fixes it.

---

*False Green injects each of these classes into a pipeline and grades whether its monitoring
noticed. This guide is the prose half; the tool is at
[github.com/Sophia-Thickums/greenover](https://github.com/Sophia-Thickums/greenover).*
