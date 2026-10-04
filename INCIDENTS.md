# Incidents: when the health check lied, in production, in public

False Green is built against a thesis. These are the receipts that the thesis is not theoretical —
each one is a real, public, dated report where a system reported healthy while it was not serving.

Every entry is a link to the primary source. Nothing here is paraphrased into a story; the quotes
are the reporters' own words.

---

## 1 · vLLM: `/health` returns 200 while every request hangs forever

**Reported:** 2026-06-10 · **Upstream:** `vllm-project/vllm`

Issue **#45094** — *"TP=2 PP=2 NCCL P2P decode deadlock — prefill works at full throughput,
generation 0 tok/s."* In their words:

> *"the engine enters a deadlock state in which **prefill runs at full throughput (~20k tok/s) but
> generation reports 0.0 tok/s indefinitely** ... The deadlock survives `docker restart` of the
> vLLM container and only clears on a full host reboot."*

Pull request **#45097** was opened to add a probe for this, and its own description states the
failure that makes it a False Green case:

> *"The standard `/health` endpoint only asks 'is the engine task alive?'. It does not probe
> whether the engine is actually decoding. When the engine deadlocks at the GPU layer ... the
> FastAPI task stays alive, **`/health` continues returning 200, and every in-flight request hangs
> forever**."*

**Class:** a check that cannot express the failure it exists to catch. The health endpoint was
asking *"is the process up?"* — a question the process can always answer yes to — instead of
*"is it serving?"*

**Which False Green class this is:** `check_not_run` (the monitor fired and reported healthy about
a thing it was not observing) compounded by a missing sensor (engine forward-progress — an
**instrumentation gap** that no HTTP health check can close).

---

## 2 · The standard serving-stack patterns

Across documented vLLM and llama.cpp operations guidance, the same shape recurs:

| what the check reads | why it reads green over a stuck server |
|---|---|
| `GET /health` → 200 | confirms the HTTP process is listening, **not** that the model loaded or the engine decodes |
| `GET /v1/models` → 200 | confirms the engine registered the model — still not that a generation completes |
| `/metrics` reachable | `vllm:num_requests_running` at **zero** while HTTP 200s flow |

The documented operational rule that falls out of it — *"a tiny `max_tokens=1` chat request is the
real readiness check; alert when `/health` passes but the chat smoke times out"* — is precisely the
distinction False Green formalises as **`existed_and_ignored` vs `never_instrumented`**.

---

## What these establish

None of these are bugs in the ordinary sense. Every component did what it was designed to do. The
failure is in the **monitoring layer**: a signal that returns success for both *"I checked and it's
fine"* and *"I cannot see the thing that matters."* That is the failure False Green injects on
purpose, so you find out before your users do.

> **A check must be able to express the failure it exists to catch.**

---

*Primary sources:*
- `vllm-project/vllm` **issue #45094** — decode deadlock, survive-restart
- `vllm-project/vllm` **pull request #45097** — `/health/decode`: "`/health` continues returning 200,
  and every in-flight request hangs forever"

*If you have a production incident of this shape you are willing to cite, open an issue — a
catalogue of real false-greens is more useful than any one tool.*
