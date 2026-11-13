"""The dispatcher's console: tomorrow's routes on a map, each technician's day with arrival times and van kit, why each
part is on the van, and reading a new job request."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

import numpy as np
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .intake import Reader, Request, rules
from .parts import CORE_SLOTS, PartModel, job_kit, standard_kit
from .schedule import Plan, greedy, optimised, route_km, timeline
from .world import Job, Region, Shape, make_region

e = html.escape
SEED = 7
BUFFERS = {"greedy": 1.0, "optimised": 1.15}  # chosen on the tuning regions (see the evaluation report)
PRIOR = 0.5
COLOURS = ["#7aa2ff", "#3ccf8e", "#f5b54a", "#ff6b6b", "#c58bff", "#4fd1d9", "#ff9f68", "#a3e635", "#f472b6", "#94a3b8"]
SAMPLE = "Hi, our Elkin dishwasher leaves water at the bottom after every wash. Someone is home in the morning."

CSS = """
:root{--bg:#0d1117;--panel:#151b24;--line:#263041;--ink:#e8edf4;--ink2:#97a3b6;--ok:#3ccf8e;--bad:#ff6b6b;--mid:#f5b54a;
--acc:#7aa2ff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Inter,system-ui,
sans-serif}a{color:inherit}header{padding:14px 26px;border-bottom:1px solid var(--line);display:flex;gap:18px;
align-items:baseline;flex-wrap:wrap}header b{font-size:17px}header nav a{color:var(--ink2);text-decoration:none;
margin-right:14px}main{padding:20px 26px 48px;max-width:1260px;margin:0 auto}.grid{display:grid;
grid-template-columns:repeat(4,1fr);gap:12px}.card{background:var(--panel);border:1px solid var(--line);
border-radius:12px;padding:14px 16px}.card b{display:block;font-size:24px}.muted{color:var(--ink2)}table{width:100%;
border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{padding:7px 11px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--ink2);
font-weight:500;font-size:12px}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.b{display:inline-block;padding:1px 9px;border-radius:99px;font-size:11.5px;font-weight:600;white-space:nowrap}
.ok{background:#3ccf8e22;color:var(--ok)}.warn{background:#f5b54a22;color:var(--mid)}.bad{background:#ff6b6b22;
color:var(--bad)}.info{background:#7aa2ff22;color:var(--acc)}h1{font-size:22px;margin:0 0 4px}h2{font-size:13px;
color:var(--ink2);text-transform:uppercase;letter-spacing:.05em;margin:24px 0 8px}textarea{width:100%;min-height:110px;
background:#0f141c;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:8px 10px;font:inherit}
button{background:var(--acc);color:#0b1020;border:0;border-radius:6px;padding:8px 14px;font:inherit;font-weight:600;
cursor:pointer}.two{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:16px}.dot{display:inline-block;
width:10px;height:10px;border-radius:50%;margin-right:6px}@media(max-width:900px){.grid{grid-template-columns:1fr 1fr}
.two{grid-template-columns:1fr}}
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
        f"initial-scale=1'><title>{e(title)}</title><style>{CSS}</style><header><b>Fieldops</b><nav>"
        "<a href='/'>Tomorrow</a><a href='/intake'>New job</a></nav><span class='muted'>demo region, 10 technicians"
        f"</span></header><main>{body}</main></html>"
    )


def hhmm(t: float) -> str:
    return f"{int(t):02d}:{round((t % 1) * 60):02d}"


@dataclass
class Console:
    region: Region
    jobs: list[Job]
    plan: Plan
    baseline: Plan
    dur: dict[int, float]
    model: PartModel
    core: set[str]
    reader: Reader | None = None

    def kit(self, tid: int) -> set[str]:
        return job_kit(self.model, self.plan.routes[tid], self.core)


def demo_console(reader: Reader | None = None) -> Console:
    region = make_region(SEED, Shape())
    hist = region.history
    mean = {s: float(np.mean([j.duration for j in hist if j.skill == s])) for s in {j.skill for j in hist}}
    jobs = region.day(0)
    plan = optimised(jobs, region.techs, {j.id: mean[j.skill] * BUFFERS["optimised"] for j in jobs})
    base = greedy(jobs, region.techs, {j.id: mean[j.skill] * BUFFERS["greedy"] for j in jobs})
    dur = {j.id: mean[j.skill] * BUFFERS["optimised"] for j in jobs}
    return Console(region, jobs, plan, base, dur, PartModel.fit(hist, PRIOR), standard_kit(hist, CORE_SLOTS), reader)


class JobIn(BaseModel):
    text: str


def request_json(r: Request) -> dict[str, Any]:
    return {
        "skill": r.skill,
        "fault": r.fault,
        "brand": r.brand,
        "window": r.window,
        "source": r.source,
        "notes": r.notes,
    }


def routes_svg(c: Console) -> str:
    size = c.region.shape.km
    s = 520 / size
    parts = [
        "<svg viewBox='0 0 540 540' width='100%' role='img' aria-label='Tomorrow's routes'><rect x='0' y='0' "
        "width='540' height='540' rx='12' fill='#10151d'/>"
    ]
    for t in c.region.techs:
        col = COLOURS[t.id % len(COLOURS)]
        pts = [t.home, *[j.at for j in c.plan.routes[t.id]], t.home]
        path = " ".join(f"{10 + x * s:.1f},{10 + y * s:.1f}" for x, y in pts)
        parts.append(f"<polyline points='{path}' fill='none' stroke='{col}' stroke-width='2' opacity='.85'/>")
        parts.append(
            f"<rect x='{10 + t.home[0] * s - 5:.1f}' y='{10 + t.home[1] * s - 5:.1f}' width='10' height='10' "
            f"fill='{col}'/>"
        )
        for j in c.plan.routes[t.id]:
            parts.append(f"<circle cx='{10 + j.at[0] * s:.1f}' cy='{10 + j.at[1] * s:.1f}' r='4.5' fill='{col}'/>")
    for j in c.plan.unplanned:
        parts.append(
            f"<circle cx='{10 + j.at[0] * s:.1f}' cy='{10 + j.at[1] * s:.1f}' r='5' fill='none' "
            "stroke='#ff6b6b' stroke-width='2'/>"
        )
    parts.append("</svg>")
    return "".join(parts)


def create_app(c: Console) -> FastAPI:
    app = FastAPI(title="Field service")
    techs = {t.id: t for t in c.region.techs}

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "jobs": len(c.jobs), "claude": c.reader is not None}

    @app.get("/api/plan")
    def api_plan() -> list[dict[str, Any]]:
        out = []
        for tid, route in c.plan.routes.items():
            arrivals, back, _ = timeline(techs[tid], route, c.dur)
            out.append(
                {
                    "technician": techs[tid].name,
                    "km": round(route_km(techs[tid], route), 1),
                    "back": hhmm(back),
                    "stops": [
                        {"job": j.id, "arrive": hhmm(a), "window": j.window, "fault": j.fault}
                        for j, a in zip(route, arrivals, strict=True)
                    ],
                }
            )
        return out

    @app.post("/api/jobs")
    def api_job(body: JobIn) -> dict[str, Any]:
        if not body.text.strip():
            raise HTTPException(422, "describe the job")
        return request_json(c.reader.read(body.text) if c.reader else rules(body.text))

    @app.get("/", response_class=HTMLResponse)
    def tomorrow() -> str:
        rows = []
        total = base_total = 0.0
        for t in c.region.techs:
            route = c.plan.routes[t.id]
            km = route_km(t, route)
            total += km
            base_total += route_km(t, c.baseline.routes[t.id])
            _, back, _ = timeline(t, route, c.dur)
            flex = sorted(c.kit(t.id) - c.core)
            rows.append(
                f"<tr><td><span class='dot' style='background:{COLOURS[t.id % len(COLOURS)]}'></span>"
                f"<a href='/techs/{t.id}'>{e(t.name)}</a><div class='muted'>{e(', '.join(t.skills))}</div></td>"
                f"<td class='num'>{len(route)}</td><td class='num'>{km:.0f} km</td><td class='num'>{hhmm(back)}</td>"
                f"<td class='muted'>{e(', '.join(flex[:6]))}{'…' if len(flex) > 6 else ''}</td></tr>"
            )
        body = (
            "<h1>Tomorrow</h1><p class='muted'>Jobs booked for tomorrow, planned with tight windows first and each job "
            "inserted where it adds the least driving without making anyone late. Every van carries the 30 most used "
            "parts plus 10 picked for that technician's jobs.</p><div class='grid'>"
            f"<div class='card'><b>{len(c.jobs)}</b><span class='muted'>jobs booked</span></div>"
            f"<div class='card'><b>{total:.0f} km</b><span class='muted'>planned driving ({base_total:.0f} km working "
            "down the list)</span></div>"
            f"<div class='card'><b>{len(c.plan.unplanned)}</b><span class='muted'>jobs that don't fit (moved to the "
            f"next day; {len(c.baseline.unplanned)} working down the list)</span></div>"
            f"<div class='card'><b>{sum(len(r) for r in c.plan.routes.values())}</b><span class='muted'>visits planned"
            "</span></div></div><div class='two' style='margin-top:16px'><div class='card'>"
            + routes_svg(c)
            + "<p class='muted'>Squares are technicians' homes; red rings are jobs that didn't fit.</p></div><div>"
            "<table><tr><th>Technician</th><th class='num'>Jobs</th><th class='num'>Driving</th><th class='num'>Home by"
            "</th><th>Parts added for the day</th></tr>" + "".join(rows) + "</table></div></div>"
        )
        return _page("Tomorrow", body)

    @app.get("/techs/{tid}", response_class=HTMLResponse)
    def tech(tid: int) -> str:
        if tid not in techs:
            raise HTTPException(404, "no such technician")
        t = techs[tid]
        route = c.plan.routes[tid]
        arrivals, back, _ = timeline(t, route, c.dur)
        kit = c.kit(tid)
        rows = []
        for j, a in zip(route, arrivals, strict=True):
            probs = sorted(((p, q) for p, q in c.model.proba(j).items() if p), key=lambda pq: -pq[1])
            cover = sum(q for p, q in c.model.proba(j).items() if p is None or p in kit)
            likely = ", ".join(f"{p} {q:.0%}{' ✓' if p in kit else ''}" for p, q in probs[:3])
            rows.append(
                f"<tr><td class='num'>{hhmm(a)}</td><td><span class='b info'>{e(j.window)}</span></td><td>"
                f"{e(j.fault)}<div class='muted'>{e(j.brand)} · “{e(j.text)}”</div></td><td class='muted'>"
                f"{e(likely)}</td><td class='num'>{cover:.0%}</td></tr>"
            )
        body = (
            f"<h1>{e(t.name)}</h1><p class='muted'>Skills: {e(', '.join(t.skills))} · {len(route)} jobs · "
            f"{route_km(t, route):.0f} km · home by {hhmm(back)}</p><h2>The day</h2><table><tr><th class='num'>Arrive"
            "</th><th>Window</th><th>Job</th><th>Most likely parts (✓ on the van)</th><th class='num'>Chance the van "
            "has what it needs</th></tr>"
            + "".join(rows)
            + "</table><h2>Parts added for the day</h2><p>"
            + e(", ".join(sorted(kit - c.core)) or "none")
            + "</p><p class='muted'>Probabilities come from past jobs: "
            "how often this fault on this brand needed each part, smoothed towards the fault on any brand.</p>"
        )
        return _page(t.name, body)

    def intake_page(text: str, r: Request, note: str) -> str:
        notes = "".join(f"<li>{e(n)}</li>" for n in r.notes)
        likely = ""
        if r.fault:
            probe = Job(-1, 0, r.skill or "", r.fault, r.brand or "", (0.0, 0.0), r.window, 1.0, None)
            probs = sorted(((p or "no part", q) for p, q in c.model.proba(probe).items()), key=lambda pq: -pq[1])
            likely = "".join(f"<tr><td>{e(p)}</td><td class='num'>{q:.0%}</td></tr>" for p, q in probs)
        body = (
            f"<h1>New job</h1><p class='muted'>Paste what the customer wrote. {e(note)}</p><form method='post' "
            f"action='/intake'><textarea name='text'>{e(text)}</textarea><p><button>Read</button></p></form>"
            f"<div class='grid'><div class='card'><b>{e(r.skill or '?')}</b><span class='muted'>skill</span></div>"
            f"<div class='card'><b>{e(r.fault or '?')}</b><span class='muted'>fault</span></div><div class='card'>"
            f"<b>{e(r.brand or '?')}</b><span class='muted'>brand</span></div><div class='card'><b>{e(r.window)}</b>"
            "<span class='muted'>window</span></div></div>"
            + (f"<ul class='muted'>{notes}</ul>" if notes else "")
            + (
                f"<h2>Parts this job is likely to need</h2><table><tr><th>Part</th><th class='num'>Chance</th></tr>"
                f"{likely}</table>"
                if likely
                else ""
            )
        )
        return _page("New job", body)

    @app.get("/intake", response_class=HTMLResponse)
    def intake() -> str:
        return intake_page(SAMPLE, rules(SAMPLE), "Example, read with rules.")

    @app.post("/intake", response_class=HTMLResponse)
    def intake_post(text: str = Form("")) -> str:
        if not text.strip():
            raise HTTPException(422, "describe the job")
        if c.reader is not None:
            return intake_page(text, c.reader.read(text), "Read with Claude.")
        return intake_page(text, rules(text), "Read with rules (no API key set).")

    return app


def demo_app() -> FastAPI:
    import os

    return create_app(demo_console(Reader() if os.environ.get("ANTHROPIC_API_KEY") else None))


__all__ = ["Console", "create_app", "demo_app", "demo_console"]
