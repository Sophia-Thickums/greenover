"""
A real pipeline under audit — a local model served by Ollama, running on AMD hardware.

This is what makes False Green more than a fixture test: the auditor can point at an actual
generation pipeline on ROCm and ask whether the pipeline's own health signal would have
noticed the failures that matter. The naive monitor here is the shape almost everyone ships:
it checks that the HTTP call succeeded, and calls that "up".
"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

try:
    from .rocm import sample, Residency
except ImportError:  # running as a loose module
    from rocm import sample, Residency  # type: ignore


OLLAMA = "http://127.0.0.1:11434"


def _chat(model: str, prompt: str, num_predict: int = 64, timeout: float = 300.0) -> dict:
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "stream": False,
               "options": {"num_predict": num_predict, "temperature": 0.0}}
    req = urllib.request.Request(OLLAMA + "/api/chat",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class OllamaPipeline:
    """A pipeline whose OWN monitoring is the thing under audit.

    `monitor_style` selects what the pipeline believes counts as health:
      - 'naive'  : the HTTP call returned 200 and status is 'success'  (what most ship)
      - 'honest' : the output is non-empty AND the work landed on the GPU   (what it should)
    """

    def __init__(self, model: str, monitor_style: str = "naive") -> None:
        self.model = model
        self.monitor_style = monitor_style
        self.name = f"ollama:{model} ({monitor_style} monitor)"
        self._last_output: Optional[str] = None
        self._last_ok: bool = False
        self._residency: Optional[Residency] = None

    def run(self, prompt: str, num_predict: int = 64) -> dict:
        try:
            d = _chat(self.model, prompt, num_predict=num_predict)
            self._last_ok = True
            self._last_output = (d.get("message", {}) or {}).get("content", "") or ""
        except Exception:
            self._last_ok = False
            self._last_output = ""
        self._residency = sample()
        return {"ok": self._last_ok, "output": self._last_output,
                "residency": self._residency.to_dict() if self._residency else None}

    def monitor(self) -> dict:
        """The pipeline's own health signal — the thing False Green judges."""
        if self.monitor_style == "naive":
            # Success == the call didn't throw. This is the whole bug.
            return {"status": "healthy" if self._last_ok else "degraded",
                    "detail": "http call succeeded"}
        # honest: a check that can express the failures it exists to catch
        if not self._last_ok:
            return {"status": "degraded", "detail": "call failed"}
        if not (self._last_output or "").strip():
            return {"status": "degraded", "detail": "empty output"}
        r = self._residency
        if r is None or r.is_unknown:
            return {"status": "unknown", "detail": "cannot judge residency"}
        if r.state == "gpu_idle":
            return {"status": "degraded", "detail": "answered, but no AMD device is doing work"}
        return {"status": "healthy", "detail": "content present, AMD device busy"}


if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "huihui_ai/qwen3.5-abliterated:9b"
    p = OllamaPipeline(model, "honest")
    out = p.run("Reply with exactly: FALSE GREEN LIVE.")
    print(json.dumps(out, indent=2)[:900])
    print("monitor:", p.monitor())
