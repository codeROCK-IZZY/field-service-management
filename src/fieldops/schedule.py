"""Building each technician's day, then living it.

Plans are made the evening before from the booked jobs, using a planning duration for each job (the true duration
is only known on site). Two planners:

- **greedy**: the way a busy dispatcher works down the list. Jobs in booking order; each goes to the end of the route
  of the qualified technician who can reach it soonest and still arrive before its window closes.
- **optimised**: tight windows first; each job is inserted wherever, across all qualified technicians and all
  positions in their routes, it adds the least travel without making anyone late; then jobs are moved between and
  within routes while that shortens the total. Jobs that can't fit go to tomorrow.

Then the day is lived with the real durations: a technician waits if they arrive before a window opens, a job
reached after its window closes is late, and work past 17:00 is overtime (nothing starts after 18:30).
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field

from .world import DAY, OVERTIME_END, Job, Tech, travel_h, travel_km


@dataclass
class Plan:
    routes: dict[int, list[Job]] = field(default_factory=dict)
    unplanned: list[Job] = field(default_factory=list)


def timeline(tech: Tech, route: Sequence[Job], dur: dict[int, float]) -> tuple[list[float], float, bool]:
    """Planned arrival at each job, the time back home, and whether every job starts inside its window."""
    t, here, ok, arrivals = DAY[0], tech.home, True, []
    for j in route:
        t += travel_h(here, j.at)
        t = max(t, j.opens)
        arrivals.append(t)
        ok = ok and t <= j.closes
        t += dur[j.id]
        here = j.at
    t += travel_h(here, tech.home)
    return arrivals, t, ok and t <= OVERTIME_END


def route_km(tech: Tech, route: Sequence[Job]) -> float:
    pts = [tech.home, *[j.at for j in route], tech.home]
    return sum(travel_km(a, b) for a, b in itertools.pairwise(pts))


def feasible(tech: Tech, route: Sequence[Job], dur: dict[int, float]) -> bool:
    _, end, ok = timeline(tech, route, dur)
    return ok and end <= DAY[1] + 0.5  # plan to finish by 17:30 at the latest


def greedy(jobs: Sequence[Job], techs: Sequence[Tech], dur: dict[int, float]) -> Plan:
    plan = Plan({t.id: [] for t in techs})
    for j in jobs:
        best: tuple[float, int] | None = None
        for t in techs:
            if j.skill not in t.skills:
                continue
            route = plan.routes[t.id]
            arrivals, _, _ = timeline(t, [*route, j], dur)
            if feasible(t, [*route, j], dur) and (best is None or arrivals[-1] < best[0]):
                best = (arrivals[-1], t.id)
        if best is None:
            plan.unplanned.append(j)
        else:
            plan.routes[best[1]].append(j)
    return plan


def _cheapest(j: Job, techs: Sequence[Tech], plan: Plan, dur: dict[int, float]) -> tuple[float, int, int] | None:
    best: tuple[float, int, int] | None = None
    for t in techs:
        if j.skill not in t.skills:
            continue
        route = plan.routes[t.id]
        base = route_km(t, route)
        for pos in range(len(route) + 1):
            cand = [*route[:pos], j, *route[pos:]]
            if not feasible(t, cand, dur):
                continue
            cost = route_km(t, cand) - base
            if best is None or cost < best[0] - 1e-9:
                best = (cost, t.id, pos)
    return best


def optimised(jobs: Sequence[Job], techs: Sequence[Tech], dur: dict[int, float], rounds: int = 3) -> Plan:
    plan = Plan({t.id: [] for t in techs})
    width = {j.id: j.closes - j.opens for j in jobs}
    for j in sorted(jobs, key=lambda j: (width[j.id], j.closes, j.id)):
        best = _cheapest(j, techs, plan, dur)
        if best is None:
            plan.unplanned.append(j)
        else:
            plan.routes[best[1]].insert(best[2], j)
    by_id = {t.id: t for t in techs}
    for _ in range(rounds):
        moved = False
        for tid in list(plan.routes):
            for j in list(plan.routes[tid]):
                route = plan.routes[tid]
                without = [x for x in route if x is not j]
                saving = route_km(by_id[tid], route) - route_km(by_id[tid], without)
                plan.routes[tid] = without
                best = _cheapest(j, techs, plan, dur)
                if best is not None and best[0] < saving - 0.05:
                    plan.routes[best[1]].insert(best[2], j)
                    moved = True
                else:
                    plan.routes[tid] = route
        # retry anything that didn't fit
        for j in list(plan.unplanned):
            best = _cheapest(j, techs, plan, dur)
            if best is not None:
                plan.routes[best[1]].insert(best[2], j)
                plan.unplanned.remove(j)
                moved = True
        if not moved:
            break
    return plan


@dataclass
class Visit:
    job: Job
    tech: int
    arrive: float
    start: float
    end: float
    on_time: bool


def live(plan: Plan, techs: Sequence[Tech]) -> tuple[list[Visit], list[Job], dict[str, float]]:
    """Run the plan with the real durations. Jobs that can't start by 18:30 are carried to tomorrow."""
    visits: list[Visit] = []
    carried: list[Job] = list(plan.unplanned)
    km = overtime = 0.0
    for t in techs:
        time, here = DAY[0], t.home
        for j in plan.routes.get(t.id, []):
            arrive = time + travel_h(here, j.at)
            if arrive > OVERTIME_END:
                carried.append(j)
                continue
            km += travel_km(here, j.at)
            start = max(arrive, j.opens)
            end = start + j.duration
            visits.append(Visit(j, t.id, arrive, start, end, start <= j.closes))
            time, here = end, j.at
        km += travel_km(here, t.home)
        back = time + travel_h(here, t.home)
        overtime += max(0.0, back - DAY[1])
    return visits, carried, {"km": km, "overtime_h": overtime}
