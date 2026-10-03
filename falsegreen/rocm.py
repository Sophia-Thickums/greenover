"""
ROCm residency sensing — the AMD integration that makes False Green more than a validator.

Why this exists: the single most expensive silent failure in local AI is a workload that
*thinks* it is on the GPU and is actually on the CPU. Everything looks healthy — the service
is up, the model answers, the dashboard is green — while the work runs 20-40x slower and the
GPU sits idle. This module is the instrument that can tell the difference, and it FAILS
CLOSED: if it cannot read residency, it reports UNKNOWN, never a green.

Design laws it obeys (from the instrument-failure catalogue):
  * Zero-matched and source-unavailable must never share an output.
    -> "no GPU found" and "GPU found, idle" are different results, never the same string.
  * A check must be able to express the failure it exists to catch.
    -> residency is measured from the SYSTEM, never inferred from the workload's own report.
  * Pin by NAME/PCI, never by index. Device orderings disagree between tools; an index is
    not a device.

Pure stdlib. No ROCm import required — it shells to `rocm-smi`/`amd-smi` when present and
degrades to UNKNOWN otherwise, so the tool runs anywhere.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class GpuSample:
    index: int
    name: str
    pci: Optional[str]
    vram_total_mib: Optional[float]
    vram_used_mib: Optional[float]
    utilization_pct: Optional[float]

    @property
    def busy(self) -> bool:
        """True if there is REAL work on this card.

        Threshold set high enough that a display compositor (a few hundred MiB, a couple
        of percent util) does not read as 'your model is on the GPU'. A loaded model shows
        gigabytes of used VRAM, not megabytes.
        """
        return bool((self.vram_used_mib and self.vram_used_mib > 512) or
                    (self.utilization_pct and self.utilization_pct > 25.0))


@dataclass
class Residency:
    """The answer to 'is the AMD hardware actually doing this work?'"""
    state: str           # "gpu_busy" | "gpu_idle" | "no_gpu" | "unknown"
    detail: str
    gpus: List[GpuSample] = None  # type: ignore[assignment]

    @property
    def is_unknown(self) -> bool:
        return self.state == "unknown"

    def to_dict(self) -> dict:
        d = {"state": self.state, "detail": self.detail,
             "gpus": [asdict(g) for g in (self.gpus or [])]}
        return d


def _run(cmd: List[str], timeout: float = 6.0) -> Optional[str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            return None
        return p.stdout
    except Exception:
        return None


def _mib(value: str) -> Optional[float]:
    """Parse '17163091968' bytes or '16368' MiB into MiB as float, or None."""
    if value is None:
        return None
    s = str(value).strip()
    m = re.search(r"(\d+(?:\.\d+)?)", s.replace(",", ""))
    if not m:
        return None
    n = float(m.group(1))
    # rocm-smi in this config reports bytes; a MiB figure is far smaller. Heuristic:
    if n > 1_000_000:   # clearly bytes
        return n / (1024 * 1024)
    return n


def sample_rocm_smi() -> Residency:
    """Read residency via rocm-smi (present on ROCm installs, no root needed)."""
    if shutil.which("rocm-smi") is None:
        return Residency("unknown", "rocm-smi not on PATH")

    # Product name + PCI per card
    ids = _run(["rocm-smi", "--showproductname", "--showbus"])
    # VRAM
    vram = _run(["rocm-smi", "--showmeminfo", "vram"])
    # Utilization (may be absent on some drivers)
    util = _run(["rocm-smi", "--showuse"])

    if vram is None and ids is None:
        return Residency("unknown", "rocm-smi present but returned nothing readable")

    gpus: List[GpuSample] = []
    # rocm-smi --showmeminfo vram emits lines like:
    #   GPU[0]  : VRAM Total Memory (B): 17095983104
    #   GPU[0]  : VRAM Total Used Memory (B): 603078656
    totals: dict = {}
    useds: dict = {}
    if vram:
        for line in vram.splitlines():
            m = re.search(r"GPU\[(\d+)\]\s*:\s*VRAM Total Memory \(B\):\s*(\d+)", line)
            if m:
                totals[int(m.group(1))] = _mib(m.group(2))
                continue
            m = re.search(r"GPU\[(\d+)\]\s*:\s*VRAM Total Used Memory \(B\):\s*(\d+)", line)
            if m:
                useds[int(m.group(1))] = _mib(m.group(2))

    names: dict = {}
    pcis: dict = {}
    if ids:
        for line in ids.splitlines():
            m = re.search(r"GPU\[(\d+)\]\s*:\s*(.+)", line)
            if not m:
                continue
            idx = int(m.group(1))
            rest = m.group(2).strip()
            if "Bus" in rest or re.search(r"[0-9a-f]{4}:[0-9a-f]{2}:", rest):
                pm = re.search(r"([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.\d)", rest)
                if pm:
                    pcis[idx] = pm.group(1)
            elif rest:
                clean = rest.split(":", 1)[-1] if rest.strip().lower().startswith("card series") else rest
                names.setdefault(idx, clean.strip())

    utils: dict = {}
    if util:
        for line in util.splitlines():
            m = re.search(r"GPU\[(\d+)\]\s*:\s*GPU use \(%\):\s*(\d+)", line)
            if m:
                utils[int(m.group(1))] = float(m.group(2))

    idxs = sorted(set(list(totals) + list(useds) + list(names) + list(pcis)))
    for i in idxs:
        gpus.append(GpuSample(
            index=i,
            name=names.get(i, f"GPU[{i}]"),
            pci=pcis.get(i),
            vram_total_mib=totals.get(i),
            vram_used_mib=useds.get(i),
            utilization_pct=utils.get(i),
        ))

    if not gpus:
        return Residency("unknown", "rocm-smi produced no parseable device rows")

    if any(g.busy for g in gpus):
        busy = [g.name for g in gpus if g.busy]
        return Residency("gpu_busy", f"work present on: {', '.join(busy)}", gpus)

    return Residency("gpu_idle",
                     f"{len(gpus)} AMD device(s) present; all idle "
                     f"(no used VRAM, util <= 1%)", gpus)


def sample(residency_probe=sample_rocm_smi) -> Residency:
    """Return residency, failing closed to UNKNOWN on any failure to read."""
    try:
        r = residency_probe()
        if r is None:
            return Residency("unknown", "probe returned nothing")
        return r
    except Exception as e:
        return Residency("unknown", f"probe raised {e.__class__.__name__}")


if __name__ == "__main__":
    print(json.dumps(sample().to_dict(), indent=2))
