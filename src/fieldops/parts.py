"""What goes on the van: a standard kit for everyone, or a kit picked for tomorrow's jobs.

A van has room for 40 different parts. Most of it holds a core every van carries.

- **standard kit**: the 40 parts used most often across all past jobs, the same for every van.
- **job kit**: the 30 most used parts as the core, and 10 flexible slots chosen for tomorrow's route. From past jobs,
  how often each fault on each brand needed each part (smoothed towards what the fault needs on any brand, for
  brands seen rarely or never); parts are added greedily by how many of the route's jobs they are expected to fix.

A visit fixes the job first time when the part it turns out to need is on the van (or it needs none). Otherwise the
technician orders the part and comes back.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .world import Job

VAN_SLOTS = 40
CORE_SLOTS = 30  # stocked on every van; the rest are flexible


@dataclass
class PartModel:
    by_fault_brand: dict[tuple[str, str], Counter[str | None]]
    by_fault: dict[str, Counter[str | None]]
    prior: float = 2.0

    @classmethod
    def fit(cls, history: Sequence[Job], prior: float = 2.0) -> PartModel:
        fb: dict[tuple[str, str], Counter[str | None]] = defaultdict(Counter)
        f: dict[str, Counter[str | None]] = defaultdict(Counter)
        for j in history:
            fb[(j.fault, j.brand)][j.part] += 1
            f[j.fault][j.part] += 1
        return cls(dict(fb), dict(f), prior)

    def proba(self, job: Job) -> dict[str | None, float]:
        """P(part | fault, brand), shrunk towards P(part | fault) by `prior` pseudo-jobs."""
        base = self.by_fault.get(job.fault, Counter())
        nb = sum(base.values()) or 1
        own = self.by_fault_brand.get((job.fault, job.brand), Counter())
        n = sum(own.values())
        parts = set(base) | set(own)
        return {p: (own[p] + self.prior * base[p] / nb) / (n + self.prior) for p in parts}


def standard_kit(history: Sequence[Job], slots: int = VAN_SLOTS) -> set[str]:
    used = Counter(j.part for j in history if j.part)
    return {p for p, _ in sorted(used.items(), key=lambda kv: (-kv[1], kv[0]))[:slots]}


def job_kit(model: PartModel, route: Sequence[Job], core: set[str], slots: int = VAN_SLOTS) -> set[str]:
    """The core parts, then the flexible slots filled greedily: each time, the part with the most expected first-time
    fixes on this route that the van doesn't already cover."""
    probs = [model.proba(j) for j in route]
    kit = set(core)
    while len(kit) < slots:
        gain: dict[str, float] = defaultdict(float)
        for p in probs:
            for part, q in p.items():
                if part and part not in kit:
                    gain[part] += q
        if not gain:
            break
        best = max(gain.items(), key=lambda kv: (kv[1], kv[0]))[0]
        kit.add(best)
    return kit


def fixed_first_time(job: Job, kit: set[str]) -> bool:
    return job.part is None or job.part in kit
