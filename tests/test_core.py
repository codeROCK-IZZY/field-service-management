"""The region world, planning, living the day, and van kits."""

from __future__ import annotations

import dataclasses

import numpy as np

from fieldops.parts import CORE_SLOTS, VAN_SLOTS, PartModel, fixed_first_time, job_kit, standard_kit
from fieldops.schedule import Plan, feasible, greedy, live, optimised, route_km, timeline
from fieldops.world import BRANDS, FAULTS, NEW_BRANDS, PARTS, SHIFTED, SKILLS, Job, Shape, Tech, make_region

SMALL = dataclasses.replace(Shape(), techs=4, days=3, history_days=30)


def job(i: int, at: tuple[float, float], window: str = "all day", skill: str = "plumbing") -> Job:
    return Job(i, 0, skill, FAULTS[skill][0], BRANDS[0], at, window, 1.0, None)


def test_region_is_deterministic_and_covers_every_skill() -> None:
    a, b = make_region(3, SMALL), make_region(3, SMALL)
    assert [j.at for j in a.jobs] == [j.at for j in b.jobs]
    assert {s for t in a.techs for s in t.skills} == set(SKILLS)
    assert a.history and all(j.day < 0 for j in a.history) and a.day(0)
    shifted = make_region(4, dataclasses.replace(SHIFTED, techs=4, days=5))
    assert any(j.brand in NEW_BRANDS for j in shifted.jobs if j.day >= 0)
    assert not any(j.brand in NEW_BRANDS for j in shifted.history)


def test_part_table_is_a_distribution_per_fault_and_brand() -> None:
    for opts in PARTS.values():
        assert abs(sum(p for _, p in opts) - 1) < 1e-9 and any(part is None for part, _ in opts)


def test_timeline_waits_for_windows_and_flags_lateness() -> None:
    t = Tech(0, "T", (0.0, 0.0), ("plumbing",))
    pm = job(1, (1.0, 0.0), "afternoon")
    arrivals, back, ok = timeline(t, [pm], {1: 1.0})
    assert arrivals == [12.0] and ok and back > 13.0
    am = job(2, (1.0, 0.0), "morning")
    jobs = [job(i, (1.0, 0.0)) for i in range(3, 8)]
    _, _, ok = timeline(t, [*jobs, am], {j.id: 1.0 for j in [*jobs, am]})
    assert not ok  # five hours of work first: the morning job is reached after noon
    assert not feasible(t, [*jobs, am], {j.id: 1.0 for j in [*jobs, am]})


def test_planners_respect_skills_and_windows() -> None:
    region = make_region(5, SMALL)
    jobs = region.day(0)
    dur = {j.id: 1.0 for j in jobs}
    for planner in (greedy, optimised):
        plan = planner(jobs, region.techs, dur)
        planned = [j for r in plan.routes.values() for j in r]
        assert sorted(j.id for j in planned + plan.unplanned) == sorted(j.id for j in jobs)
        for t in region.techs:
            assert all(j.skill in t.skills for j in plan.routes[t.id])
            assert feasible(t, plan.routes[t.id], dur)


def test_optimised_drives_less_than_the_list() -> None:
    region = make_region(6, dataclasses.replace(Shape(), days=3))
    jobs = region.day(0)
    dur = {j.id: 1.0 for j in jobs}
    km = {}
    for name, planner in (("greedy", greedy), ("optimised", optimised)):
        plan = planner(jobs, region.techs, dur)
        km[name] = sum(route_km(t, plan.routes[t.id]) for t in region.techs) / max(1, len(jobs) - len(plan.unplanned))
    assert km["optimised"] < km["greedy"]


def test_live_day_uses_real_durations_and_carries_what_cannot_start() -> None:
    t = Tech(0, "T", (0.0, 0.0), ("plumbing",))
    long = dataclasses.replace(job(1, (1.0, 0.0)), duration=11.0)
    late = job(2, (2.0, 0.0))
    plan = Plan({0: [long, late]}, [])
    visits, carried, m = live(plan, [t])
    assert [v.job.id for v in visits] == [1] and [j.id for j in carried] == [2]
    assert m["overtime_h"] > 0 and visits[0].on_time


def test_part_model_shrinks_towards_the_fault_and_kits_fill_the_van() -> None:
    region = make_region(7, Shape())
    model = PartModel.fit(region.history, prior=2.0)
    j = region.history[0]
    p = model.proba(j)
    assert abs(sum(p.values()) - 1) < 1e-6
    unseen = dataclasses.replace(j, brand=NEW_BRANDS[0])
    assert model.proba(unseen)  # falls back to the fault on any brand
    std = standard_kit(region.history)
    core = standard_kit(region.history, CORE_SLOTS)
    assert len(std) == VAN_SLOTS and core <= std
    route = region.day(0)[:5]
    kit = job_kit(model, route, core)
    assert core <= kit and len(kit) <= VAN_SLOTS
    assert fixed_first_time(dataclasses.replace(j, part=None), set())
    assert not fixed_first_time(dataclasses.replace(j, part="X-1"), {"Y-2"})


def test_planned_kit_fixes_more_first_time_than_the_standard_kit() -> None:
    region = make_region(8, dataclasses.replace(Shape(), days=4))
    model = PartModel.fit(region.history, 0.5)
    std = standard_kit(region.history)
    core = standard_kit(region.history, CORE_SLOTS)
    jobs = [j for d in range(4) for j in region.day(d)]
    routes = [jobs[i : i + 5] for i in range(0, len(jobs), 5)]
    planned = sum(fixed_first_time(j, job_kit(model, r, core)) for r in routes for j in r)
    standard = sum(fixed_first_time(j, std) for j in jobs)
    assert planned > standard
    assert np.isclose(sum(len(r) for r in routes), len(jobs))
