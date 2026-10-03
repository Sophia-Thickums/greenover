"""Tests for False Green. Run with: python3 -m unittest discover -s tests

The suite includes the non-vacuous proof: it removes the rule each check exists to
exercise and confirms the verdict DEGRADES to UNKNOWN rather than passing.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from falsegreen import (  # noqa: E402
    Injection, Verdict, NaivePipeline, HonestPipeline, audit,
)


class TestAuditor(unittest.TestCase):
    def test_naive_monitor_is_green_over_nothing(self):
        rep = audit(NaivePipeline(), [Injection.EMPTY_OUTPUT, Injection.CPU_FALLBACK,
                                      Injection.BUDGET_EXHAUSTED, Injection.TRUNCATED])
        self.assertEqual(len(rep.false_greens), 4)

    def test_honest_monitor_is_never_falsely_green(self):
        rep = audit(HonestPipeline(), [Injection.EMPTY_OUTPUT, Injection.CPU_FALLBACK,
                                       Injection.BUDGET_EXHAUSTED, Injection.TRUNCATED])
        self.assertEqual(len(rep.false_greens), 0)
        self.assertTrue(all(f.verdict is Verdict.REAL for f in rep.findings))

    def test_check_not_run_is_judged(self):
        rep = audit(NaivePipeline(), [Injection.CHECK_NOT_RUN])
        self.assertIs(rep.findings[0].verdict, Verdict.GREEN_OVER_NOTHING)

    def test_blind_monitor_is_unknown_not_green(self):
        class Blind(NaivePipeline):
            def monitor(self):
                return {"status": "unknown", "detail": "no telemetry"}
        rep = audit(Blind(), [Injection.EMPTY_OUTPUT])
        self.assertIs(rep.findings[0].verdict, Verdict.UNKNOWN)


class TestNonVacuity(unittest.TestCase):
    """Remove the mechanism and watch the check degrade — never silently pass."""

    def test_removing_content_rule_degrades_to_unknown(self):
        class Broken(HonestPipeline):
            def monitor(self):
                r = self._last
                if r is None:
                    return {"status": "unknown", "detail": "no run"}
                if not r["gpu"]:
                    return {"status": "degraded", "detail": "not on GPU"}
                if r["truncated"]:
                    return {"status": "degraded", "detail": "truncated"}
                return {"status": "unknown", "detail": "no content rule"}

        rep = audit(Broken(), [Injection.EMPTY_OUTPUT])
        self.assertIs(rep.findings[0].verdict, Verdict.UNKNOWN)
        self.assertIsNot(rep.findings[0].verdict, Verdict.GREEN_OVER_NOTHING)

    def test_selftest_returns_zero(self):
        from falsegreen import selftest
        self.assertEqual(selftest(), 0)


if __name__ == "__main__":
    unittest.main()
