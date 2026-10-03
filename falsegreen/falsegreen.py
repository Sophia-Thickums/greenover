#!/usr/bin/env python3
"""
False Green — chaos engineering for AI pipelines.

One question about a monitored pipeline:

    does the check actually check?

It does not watch your pipeline. It ATTACKS it with the exact silent failures that
production AI dies from, then reads the pipeline's OWN monitoring to see whether it
noticed. Every check gets one of three verdicts:

    REAL               the monitor caught the injected failure
    GREEN_OVER_NOTHING the monitor reported healthy while the failure was live
    UNKNOWN            the check could not be judged   (never treated as green)

The failure classes are drawn from a first-person catalogue of measured instrument
failures. The governing principle:

    A check must be able to express the failure it exists to catch.

Everything works offline with no GPU; --selftest runs with no arguments and proves
each rule can go RED, and that the negative control stays GREEN.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Callable, Dict, List, Optional


# ---------------------------------------------------------------- verdicts

class Verdict(str, Enum):
    REAL = "REAL"
    GREEN_OVER_NOTHING = "GREEN_OVER_NOTHING"
    UNKNOWN = "UNKNOWN"


class Injection(str, Enum):
    """The conditions a healthy pipeline is supposed to survive *and report*."""
    NONE = "none"
    EMPTY_OUTPUT = "empty_output"          # model returns "" ; scored as a clean 0.000
    CPU_FALLBACK = "cpu_fallback"          # GPU residency lost ; dashboard stays green
    BUDGET_EXHAUSTED = "budget_exhausted"  # model spent everything in a hidden channel
    CHECK_NOT_RUN = "check_not_run"        # the monitor itself never fired
    TRUNCATED = "truncated"                # output cut at the cap ; reported as success


DESCRIPTIONS: Dict[Injection, str] = {
    Injection.EMPTY_OUTPUT: "model returns an empty string, and a guard turns 'no data' into a tidy 0.000",
    Injection.CPU_FALLBACK: "GPU residency is lost and the workload silently runs on CPU while the dashboard reads healthy",
    Injection.BUDGET_EXHAUSTED: "the model spends its whole budget in a hidden reasoning channel and reports a clean result over no data",
    Injection.CHECK_NOT_RUN: "the monitor itself fails to fire, so 'zero problems' and 'could not look' share one output",
    Injection.TRUNCATED: "the output is cut at the token cap and the run is reported as success",
}


@dataclass
class Finding:
    injection: Injection
    verdict: Verdict
    monitor_said: str
    truth: str
    detail: str = ""


@dataclass
class AuditReport:
    pipeline: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def false_greens(self) -> List[Finding]:
        return [f for f in self.findings if f.verdict is Verdict.GREEN_OVER_NOTHING]

    def to_markdown(self) -> str:
        lines = [f"# False Green audit — `{self.pipeline}`", ""]
        n = len(self.findings)
        bad = len(self.false_greens)
        unknown = sum(1 for f in self.findings if f.verdict is Verdict.UNKNOWN)
        lines.append(f"**{n} checks audited — {n - bad - unknown} real, **{bad} green-over-nothing**, {unknown} unknown.**")
        if bad:
            lines.append("")
            lines.append("> A green light over a room the monitor was never observing is worse than no monitor at all.")
        lines += ["", "| injected failure | monitor reported | truth | verdict |", "|---|---|---|---|"]
        for f in self.findings:
            lines.append(f"| {f.injection.value} | {f.monitor_said} | {f.truth} | **{f.verdict.value}** |")
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------- the pipelines under audit

class Pipeline:
    """What False Green audits. A pipeline runs work and has its own monitoring."""
    name = "pipeline"

    def run(self, injection: Injection) -> dict:
        raise NotImplementedError

    def monitor(self) -> dict:
        """Return {'status': 'healthy'|'degraded'|'unknown', 'detail': str}."""
        raise NotImplementedError


class NaivePipeline(Pipeline):
    """The common real-world shape: a monitor that only reads the exit code."""
    name = "naive (exit-code monitor)"

    def __init__(self) -> None:
        self._last: Optional[dict] = None

    def run(self, injection: Injection) -> dict:
        if injection is Injection.EMPTY_OUTPUT:
            out = {"output": "", "exit": 0, "gpu": True, "budget_spent": 0.2, "truncated": False}
        elif injection is Injection.CPU_FALLBACK:
            out = {"output": "ok", "exit": 0, "gpu": False, "budget_spent": 0.3, "truncated": False}
        elif injection is Injection.BUDGET_EXHAUSTED:
            out = {"output": "", "exit": 0, "gpu": True, "budget_spent": 1.0, "truncated": False}
        elif injection is Injection.TRUNCATED:
            out = {"output": "partial…", "exit": 0, "gpu": True, "budget_spent": 0.9, "truncated": True}
        else:
            out = {"output": "a real answer", "exit": 0, "gpu": True, "budget_spent": 0.4, "truncated": False}
        self._last = out
        return out

    def monitor(self) -> dict:
        # The failure: exit code is the only signal, so every silent failure reads healthy.
        # And a fresh monitor with no data at all defaults to healthy — the status variable
        # is initialised to a passing state, which is the classic check-that-never-fired bug.
        if self._last is None:
            return {"status": "healthy", "detail": "no data; defaulting to healthy"}
        ok = self._last["exit"] == 0
        return {"status": "healthy" if ok else "degraded", "detail": "exit code"}


class HonestPipeline(Pipeline):
    """What a monitor *should* be: it can express every failure it exists to catch."""
    name = "honest (content + residency aware)"

    def __init__(self) -> None:
        self._last: Optional[dict] = None

    def run(self, injection: Injection) -> dict:
        return NaivePipeline.run(self, injection)

    def monitor(self) -> dict:
        r = self._last
        if r is None:
            return {"status": "unknown", "detail": "no run recorded"}
        if not r["output"].strip():
            return {"status": "degraded", "detail": "empty output"}
        if not r["gpu"]:
            return {"status": "degraded", "detail": "not on GPU"}
        if r["budget_spent"] >= 1.0 and not r["output"].strip():
            return {"status": "degraded", "detail": "budget spent, no output"}
        if r["truncated"]:
            return {"status": "degraded", "detail": "output truncated at cap"}
        return {"status": "healthy", "detail": "content present, on GPU, not truncated"}


# ---------------------------------------------------------------- the auditor

def _truth_of(injection: Injection) -> str:
    return {
        Injection.EMPTY_OUTPUT: "empty output",
        Injection.CPU_FALLBACK: "ran on CPU",
        Injection.BUDGET_EXHAUSTED: "no data produced",
        Injection.CHECK_NOT_RUN: "monitor never fired",
        Injection.TRUNCATED: "output truncated",
    }[injection]


def audit(pipeline: Pipeline, injections: Optional[List[Injection]] = None,
          probe: Optional[Callable[[Pipeline, Injection], Optional[dict]]] = None) -> AuditReport:
    """Run each injected failure and judge whether the pipeline's monitor noticed."""
    if injections is None:
        injections = [i for i in Injection if i is not Injection.NONE]

    rep = AuditReport(pipeline=pipeline.name)
    for inj in injections:
        # CHECK_NOT_RUN is about the monitor firing at all: we do not run the pipeline
        # and see whether the monitor can tell "I didn't look" from "all clear".
        if inj is Injection.CHECK_NOT_RUN:
            try:
                m = pipeline.monitor()
            except Exception as e:  # a monitor that blows up has not looked either
                m = {"status": "unknown", "detail": f"monitor raised: {e.__class__.__name__}"}
            status = str(m.get("status", "unknown")).lower()
            if status == "healthy":
                v = Verdict.GREEN_OVER_NOTHING
            elif status == "unknown":
                v = Verdict.UNKNOWN
            else:
                v = Verdict.REAL
            rep.findings.append(Finding(inj, v, status, _truth_of(inj),
                                        m.get("detail", "")))
            continue

        # Run the pipeline with the failure injected (via a probe seam when supplied).
        run = probe(pipeline, inj) if probe else pipeline.run(inj)
        if run is None:
            rep.findings.append(Finding(inj, Verdict.UNKNOWN, "n/a",
                                        _truth_of(inj), "probe could not apply the injection"))
            continue

        m = pipeline.monitor()
        status = str(m.get("status", "unknown")).lower()
        if status == "healthy":
            v = Verdict.GREEN_OVER_NOTHING
        elif status == "unknown":
            v = Verdict.UNKNOWN
        else:
            v = Verdict.REAL
        rep.findings.append(Finding(inj, v, status, _truth_of(inj), m.get("detail", "")))
    return rep


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    """Prove each rule can go RED and the negative control stays GREEN.

    Returns process exit code: 0 = all pass, 1 = a rule did not behave.
    """
    failures: List[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    print("False Green — selftest")

    # 1. The naive monitor must be caught as green-over-nothing on the silent failures.
    naive = audit(NaivePipeline(), [Injection.EMPTY_OUTPUT, Injection.CPU_FALLBACK,
                                    Injection.BUDGET_EXHAUSTED, Injection.TRUNCATED])
    check("naive monitor flagged GREEN_OVER_NOTHING on all four silent failures",
          len(naive.false_greens) == 4)

    # 2. The negative control: a monitor that CAN express the failures must never be
    #    falsely green — a checker that fires on healthy code gets ignored.
    honest = audit(HonestPipeline(), [Injection.EMPTY_OUTPUT, Injection.CPU_FALLBACK,
                                      Injection.BUDGET_EXHAUSTED, Injection.TRUNCATED])
    check("honest monitor produces ZERO false greens on the same injections",
          len(honest.false_greens) == 0)
    check("honest monitor returns REAL on every injection",
          all(f.verdict is Verdict.REAL for f in honest.findings))

    # 3. THE NON-VACUOUS PROOF — remove the content rule and watch it DEGRADE to
    #    UNKNOWN rather than sail through as allow/healthy.
    class BrokenHonest(HonestPipeline):
        def monitor(self) -> dict:
            r = self._last
            if r is None:
                return {"status": "unknown", "detail": "no run recorded"}
            # the empty-output rule has been removed; the monitor can no longer
            # express the failure it exists to catch. It must not claim healthy.
            if not r["gpu"]:
                return {"status": "degraded", "detail": "not on GPU"}
            if r["truncated"]:
                return {"status": "degraded", "detail": "output truncated at cap"}
            return {"status": "unknown", "detail": "cannot judge: no content rule"}

    broken = audit(BrokenHonest(), [Injection.EMPTY_OUTPUT])
    f0 = broken.findings[0]
    check("removing the content rule degrades EMPTY_OUTPUT to UNKNOWN (not healthy)",
          f0.verdict is Verdict.UNKNOWN)
    check("the degradation is NOT 'healthy' — the failure is never waved through",
          f0.verdict is not Verdict.GREEN_OVER_NOTHING)

    # 4. A monitor that cannot look must not read green.
    class BlindPipeline(NaivePipeline):
        def monitor(self) -> dict:
            return {"status": "unknown", "detail": "no telemetry"}

    blind = audit(BlindPipeline(), [Injection.EMPTY_OUTPUT])
    check("a blind monitor reads UNKNOWN, never GREEN",
          blind.findings[0].verdict is Verdict.UNKNOWN)

    print()
    if failures:
        print(f"selftest FAILED — {len(failures)} rule(s) did not behave:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("selftest PASSED — every rule can go red, the control stays green, and the "
          "guard degrades rather than waving a failure through.")
    return 0


# ---------------------------------------------------------------- cli

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="falsegreen",
                                description="Does your monitoring actually monitor? "
                                            "Attack your AI pipeline with the silent failures "
                                            "production dies from, and see whether it notices.")
    p.add_argument("--selftest", action="store_true",
                   help="run the built-in proof (no setup, no GPU, no network)")
    p.add_argument("--demo", action="store_true",
                   help="audit two example pipelines and print the report")
    p.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.demo:
        for pl in (NaivePipeline(), HonestPipeline()):
            rep = audit(pl)
            if args.json:
                print(json.dumps({"pipeline": rep.pipeline,
                                  "findings": [asdict(f) for f in rep.findings]}, indent=2, default=str))
            else:
                print(rep.to_markdown())
                print()
        return 0

    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
