"""A synthetic field-service region: technicians, customers' jobs with time windows, and the parts jobs need.

- **Technicians** start and end the day at home, have one to three skills, and a van with room for a limited number
  of different parts.
- **Jobs** are booked the day before. Each has a skill, a customer time window (morning, afternoon or all day), a
  duration that is only known once the work is done, and a fault on a piece of equipment of some brand.
- **Parts**: what a job needs depends on its fault and on the equipment's brand (each brand has its own part
  numbers for some faults). Sometimes nothing is needed. A visit fixes the job first time only if the technician has
  the part on the van.

`SHIFTED` is busier, with longer and more variable jobs, and brands that never appeared in the history.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SKILLS = ("hvac", "electrical", "plumbing", "appliance")
FAULTS: dict[str, tuple[str, ...]] = {
    "hvac": ("no heat", "no cooling", "noisy unit", "thermostat fault"),
    "electrical": ("tripping breaker", "dead sockets", "lighting fault", "ev charger fault"),
    "plumbing": ("leak under sink", "no hot water", "blocked drain", "running toilet"),
    "appliance": ("dishwasher not draining", "washer not spinning", "oven not heating", "fridge not cooling"),
}
BRANDS = ("Aldor", "Brisk", "Corval", "Dunmore", "Elkin", "Fenwick")
NEW_BRANDS = ("Garro", "Hollis")
WINDOWS = {"morning": (8.0, 12.0), "afternoon": (12.0, 17.0), "all day": (8.0, 17.0)}
SPEED_KMH = 35.0
ROAD = 1.3  # road distance over straight-line distance
DAY = (8.0, 17.0)
OVERTIME_END = 18.5


@dataclass(frozen=True)
class Shape:
    techs: int = 10
    km: float = 25.0
    jobs_per_tech: float = 4.0
    duration_mean_h: float = 1.0
    duration_cv: float = 0.5
    new_brand_share: float = 0.0
    history_days: int = 40
    days: int = 20


SHIFTED = Shape(jobs_per_tech=4.6, duration_mean_h=1.15, duration_cv=0.7, new_brand_share=0.25, history_days=20)


@dataclass
class Tech:
    id: int
    name: str
    home: tuple[float, float]
    skills: tuple[str, ...]


@dataclass
class Job:
    id: int
    day: int
    skill: str
    fault: str
    brand: str
    at: tuple[float, float]
    window: str
    duration: float  # hours, the real one
    part: str | None  # what the fix needs, unknown until on site
    text: str = ""

    @property
    def opens(self) -> float:
        return WINDOWS[self.window][0]

    @property
    def closes(self) -> float:
        return WINDOWS[self.window][1]


@dataclass
class Region:
    seed: int
    shape: Shape
    techs: list[Tech]
    jobs: list[Job] = field(default_factory=list)

    def day(self, d: int) -> list[Job]:
        return [j for j in self.jobs if j.day == d]

    @property
    def history(self) -> list[Job]:
        return [j for j in self.jobs if j.day < 0]


TECH_NAMES = [
    "Amara",
    "Bruno",
    "Chen",
    "Dalia",
    "Emeka",
    "Freya",
    "Gustavo",
    "Hiro",
    "Isla",
    "Jonas",
    "Kofi",
    "Lena",
    "Mateo",
    "Nadia",
    "Oscar",
    "Priya",
]


def travel_h(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1])) * ROAD / SPEED_KMH


def travel_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1])) * ROAD


def part_table(seed: int) -> dict[tuple[str, str], list[tuple[str | None, float]]]:
    """For each fault and brand: the parts a fix may need, with probabilities. The same for every region."""
    g = np.random.default_rng(seed)
    table: dict[tuple[str, str], list[tuple[str | None, float]]] = {}
    for skill, faults in FAULTS.items():
        for k, fault in enumerate(faults):
            common = [f"{skill[:3].upper()}-{k}{c}" for c in "AB"]
            for b in BRANDS + NEW_BRANDS:
                specific = f"{skill[:3].upper()}-{k}{b[:2].upper()}"
                w = g.dirichlet([3.0, 1.5, 2.5, 1.0])  # common A, common B, brand-specific, nothing
                table[(fault, b)] = [
                    (common[0], float(w[0])),
                    (common[1], float(w[1])),
                    (specific, float(w[2])),
                    (None, float(w[3])),
                ]
    return table


PARTS = part_table(2026)

PHRASES = {
    "no heat": "the heating isn't coming on",
    "no cooling": "the air conditioning blows warm air",
    "noisy unit": "the outdoor unit is making a grinding noise",
    "thermostat fault": "the thermostat screen is blank",
    "tripping breaker": "a breaker keeps tripping",
    "dead sockets": "the kitchen sockets have no power",
    "lighting fault": "the hallway lights flicker and die",
    "ev charger fault": "the car charger shows a red light",
    "leak under sink": "water is leaking under the sink",
    "no hot water": "there is no hot water",
    "blocked drain": "the shower drain is blocked",
    "running toilet": "the toilet keeps running",
    "dishwasher not draining": "the dishwasher leaves water at the bottom",
    "washer not spinning": "the washing machine won't spin",
    "oven not heating": "the oven stays cold",
    "fridge not cooling": "the fridge is warm",
}
KIND = {"hvac": "system", "electrical": "panel", "plumbing": "fixture", "appliance": "appliance"}


def make_region(seed: int, shape: Shape = Shape()) -> Region:
    g = np.random.default_rng(seed)
    techs = []
    for i in range(shape.techs):
        n = int(g.integers(1, 4))
        skills = tuple(sorted(str(s) for s in g.choice(SKILLS, n, replace=False)))
        techs.append(
            Tech(
                i,
                TECH_NAMES[i % len(TECH_NAMES)],
                (float(g.uniform(0, shape.km)), float(g.uniform(0, shape.km))),
                skills,
            )
        )
    covered = {s for t in techs for s in t.skills}
    for s in SKILLS:  # every skill needs someone
        if s not in covered:
            t = techs[int(g.integers(len(techs)))]
            t.skills = tuple(sorted({*t.skills, s}))
    region = Region(seed, shape, techs)
    jid = 0
    for d in range(-shape.history_days, shape.days):
        n = int(g.poisson(shape.jobs_per_tech * shape.techs))
        for _ in range(n):
            skill = SKILLS[int(g.integers(len(SKILLS)))]
            fault = FAULTS[skill][int(g.integers(4))]
            new = d >= 0 and g.random() < shape.new_brand_share
            brand = NEW_BRANDS[int(g.integers(2))] if new else BRANDS[int(g.integers(len(BRANDS)))]
            opts = PARTS[(fault, brand)]
            k = int(g.choice(len(opts), p=np.array([p for _, p in opts])))
            mean = shape.duration_mean_h
            sd = mean * shape.duration_cv
            dur = float(g.gamma((mean / sd) ** 2, sd**2 / mean))
            window = ("morning", "afternoon", "all day")[int(g.choice(3, p=[0.35, 0.35, 0.3]))]
            text = f"Our {brand} {KIND[skill]}: {PHRASES[fault]}."
            region.jobs.append(
                Job(
                    jid,
                    d,
                    skill,
                    fault,
                    brand,
                    (float(g.uniform(0, shape.km)), float(g.uniform(0, shape.km))),
                    window,
                    max(0.25, dur),
                    opts[k][0],
                    text,
                )
            )
            jid += 1
    return region
