"""False Green — chaos engineering for AI pipelines.

Does your monitoring actually monitor? Point it at a pipeline and it injects the silent
failures that production AI dies from, then reads the pipeline's own health signal to see
whether it noticed. Verdict per check: REAL / GREEN_OVER_NOTHING / UNKNOWN, and UNKNOWN is
never treated as green.
"""
from .falsegreen import (  # noqa: F401
    Verdict, Injection, Finding, AuditReport, Pipeline,
    NaivePipeline, HonestPipeline, audit, selftest, main,
)
from .rocm import sample as rocm_residency  # noqa: F401

__version__ = "0.1.0"
