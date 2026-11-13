"""The evaluation: more appointments kept with less driving, and more jobs fixed on the first visit.

Three banks of synthetic regions (10 technicians each, four weeks measured after a history period), never mixed:

- **tuning** (4 regions): the only place settings are chosen: each planner's planning buffer (how much longer than
  the historical average a job is planned to take), and the part model's smoothing.
- **held-out** (10 regions): run after the settings and this file were committed.
- **shifted** (6 regions, held back): busier, longer and more variable jobs, a quarter of equipment from brands never
  seen in the history, and half as much history.

Each planner gets its own best buffer, so the greedy baseline is tuned as carefully as the optimiser.

**An appointment is kept** when the job is done on the day it was booked for, inside the customer's window. Jobs that
don't fit wait for the next day and count against the planner.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .parts import CORE_SLOTS, PartModel, fixed_first_time, job_kit, standard_kit
from .schedule import Plan, greedy, live, optimised
from .world import SHIFTED, Job, Region, Shape, Tech, make_region

BANKS: dict[str, tuple[tuple[int, ...], Shape]] = {
    "tuning": ((1, 2, 3, 4), Shape()),
    "heldout": (tuple(range(101, 111)), Shape()),
    "shifted": (tuple(range(201, 207)), SHIFTED),
}
PLANNERS: dict[str, Callable[[Sequence[Job], Sequence[Tech], dict[int, float]], Plan]] = {
    "greedy": greedy,
    "optimised": optimised,
}
BUFFERS = (1.0, 1.15, 1.3, 1.5)
PRIORS = (0.5, 2.0, 5.0, 10.0)

# Written before the held-out and shifted banks were run.
GATE = {
    "heldout_km_ratio_max": 0.75,  # km per job done, optimised over greedy
    "heldout_kept_gain_min": 0.05,  # kept-appointment share, optimised minus greedy
    "heldout_first_time_fix_gain_min": 0.10,  # job kit minus standard kit
    "shifted_km_ratio_max": 0.80,
    "shifted_first_time_fix_gain_min": 0.05,
}


def run_region(region: Region, planner: str, buffer: float, prior: float) -> dict[str, float]:
    hist = region.history
    mean = {s: float(np.mean([j.duration for j in hist if j.skill == s])) for s in {j.skill for j in hist}}
    model = PartModel.fit(hist, prior)
    std = standard_kit(hist)
    core = standard_kit(hist, CORE_SLOTS)
    carry: list[Job] = []
    out = {
        "booked": 0.0,
        "done": 0.0,
        "kept": 0.0,
        "km": 0.0,
        "overtime_h": 0.0,
        "wait_days": 0.0,
        "ftf_standard": 0.0,
        "ftf_kit": 0.0,
        "tech_days": 0.0,
    }
    for d in range(region.shape.days):
        jobs = carry + region.day(d)
        dur = {j.id: mean.get(j.skill, 1.0) * buffer for j in jobs}
        plan = PLANNERS[planner](jobs, region.techs, dur)
        visits, carry, m = live(plan, region.techs)
        out["booked"] += len(region.day(d))
        out["done"] += len(visits)
        out["kept"] += sum(v.on_time and v.job.day == d for v in visits)
        out["wait_days"] += sum(d - v.job.day for v in visits)
        out["km"] += m["km"]
        out["overtime_h"] += m["overtime_h"]
        out["tech_days"] += len(region.techs)
        for tid, route in plan.routes.items():
            kit = job_kit(model, route, core)
            done = [v.job for v in visits if v.tech == tid]
            out["ftf_standard"] += sum(fixed_first_time(j, std) for j in done)
            out["ftf_kit"] += sum(fixed_first_time(j, kit) for j in done)
    out["backlog"] = float(len(carry))
    return out


def totals(rows: Sequence[dict[str, float]]) -> dict[str, float]:
    t = {k: float(sum(r[k] for r in rows)) for k in rows[0]}
    return {
        **t,
        "kept_share": t["kept"] / max(1.0, t["booked"]),
        "km_per_job": t["km"] / max(1.0, t["done"]),
        "overtime_h_per_tech_day": t["overtime_h"] / max(1.0, t["tech_days"]),
        "avg_wait_days": t["wait_days"] / max(1.0, t["done"]),
        "first_time_fix_standard": t["ftf_standard"] / max(1.0, t["done"]),
        "first_time_fix_kit": t["ftf_kit"] / max(1.0, t["done"]),
    }


def run_bank(seeds: Sequence[int], shape: Shape, buffers: dict[str, float], prior: float) -> dict[str, Any]:
    regions = [make_region(s, shape) for s in seeds]
    out: dict[str, Any] = {"regions": len(seeds), "techs": sum(len(r.techs) for r in regions), "planners": {}}
    for name in PLANNERS:
        out["planners"][name] = totals([run_region(r, name, buffers[name], prior) for r in regions])
    g, o = out["planners"]["greedy"], out["planners"]["optimised"]
    out["km_ratio"] = o["km_per_job"] / g["km_per_job"]
    out["kept_difference"] = o["kept_share"] - g["kept_share"]
    out["first_time_fix_gain"] = o["first_time_fix_kit"] - o["first_time_fix_standard"]
    return out


def tune() -> dict[str, Any]:
    seeds, shape = BANKS["tuning"]
    regions = [make_region(s, shape) for s in seeds]
    grid: list[dict[str, Any]] = []
    for name in PLANNERS:
        for b in BUFFERS:
            t = totals([run_region(r, name, b, 2.0) for r in regions])
            grid.append(
                {
                    "planner": name,
                    "buffer": b,
                    "kept_share": t["kept_share"],
                    "km_per_job": t["km_per_job"],
                    "overtime_h_per_tech_day": t["overtime_h_per_tech_day"],
                }
            )
    buffers: dict[str, float] = {}
    for name in PLANNERS:
        rows = [g for g in grid if g["planner"] == name]
        best = max(rows, key=lambda g: (round(g["kept_share"], 4), -g["overtime_h_per_tech_day"]))
        buffers[name] = float(best["buffer"])
    priors: list[dict[str, float]] = []
    for p in PRIORS:
        t = totals([run_region(r, "optimised", buffers["optimised"], p) for r in regions])
        priors.append({"prior": p, "first_time_fix_kit": t["first_time_fix_kit"]})
    prior = max(priors, key=lambda g: (round(g["first_time_fix_kit"], 4), -g["prior"]))["prior"]
    return {"grid": grid, "buffers": buffers, "priors": priors, "prior": prior}


def run_all(gate: bool = False) -> dict[str, Any]:
    t0 = time.time()
    tuning = tune()
    result: dict[str, Any] = {"tuning": tuning, "banks": {}}
    for name, (seeds, shape) in BANKS.items():
        result["banks"][name] = run_bank(seeds, shape, tuning["buffers"], tuning["prior"])
    result["seconds"] = round(time.time() - t0, 1)
    if gate:
        result["gate"] = check_gate(result)
    return result


def check_gate(r: dict[str, Any]) -> dict[str, Any]:
    h, s = r["banks"]["heldout"], r["banks"]["shifted"]
    checks = {
        "heldout_km_ratio_max": h["km_ratio"],
        "heldout_kept_gain_min": h["kept_difference"],
        "heldout_first_time_fix_gain_min": h["first_time_fix_gain"],
        "shifted_km_ratio_max": s["km_ratio"],
        "shifted_first_time_fix_gain_min": s["first_time_fix_gain"],
    }
    ok = {k: (v <= GATE[k] if k.endswith("_max") else v >= GATE[k]) for k, v in checks.items()}
    return {"passed": all(ok.values()), "checks": {k: round(v, 4) for k, v in checks.items()}, "ok": ok, "limits": GATE}


def save(result: dict[str, Any], out: Path) -> None:
    from .report import html_report, markdown

    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "report.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    (out / "report.html").write_text(html_report(result), encoding="utf-8", newline="\n")
