"""Markdown and HTML versions of the evaluation."""

from __future__ import annotations

import html
from typing import Any

BANKS = {
    "heldout": "Held-out regions",
    "shifted": "Shifted regions (held back): busier, new brands, less history",
    "tuning": "Tuning regions",
}
LABELS = {
    "greedy": "Dispatcher's list (nearest free technician, in booking order)",
    "optimised": "Optimised (tight windows first, cheapest insertion, moves between routes)",
}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def markdown(r: dict[str, Any]) -> str:
    t = r["tuning"]
    out = [
        "# Field service: evaluation",
        "",
        "Synthetic regions of 10 technicians over four weeks. An appointment is kept when the job is done on the day "
        "booked, inside the customer's window. First-time fix: the part the job turned out to need was on the van.",
        "",
        f"Chosen on the tuning regions: planning buffers {t['buffers']}, part-model smoothing {t['prior']}.",
        "",
    ]
    for b, label in BANKS.items():
        x = r["banks"][b]
        out += [
            f"## {label}: {x['regions']} regions, {x['techs']} technicians",
            "",
            "| Planner | Appointments kept | km per job | Overtime h per tech-day | Avg days waited | Backlog at end |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for k, name in LABELS.items():
            p = x["planners"][k]
            out.append(
                f"| {name} | {pct(p['kept_share'])} | {p['km_per_job']:.1f} | {p['overtime_h_per_tech_day']:.2f} | "
                f"{p['avg_wait_days']:.2f} | {p['backlog']:.0f} |"
            )
        o = x["planners"]["optimised"]
        out += [
            "",
            f"First-time fix: standard van kit {pct(o['first_time_fix_standard'])}, kit planned for the day's "
            f"jobs {pct(o['first_time_fix_kit'])}.",
            "",
        ]
    out += [
        "## Tuning",
        "",
        "| Planner | Buffer | Kept | km per job | Overtime h per tech-day |",
        "|---|---:|---:|---:|---:|",
    ]
    out += [
        f"| {g['planner']} | {g['buffer']} | {pct(g['kept_share'])} | {g['km_per_job']:.1f} | "
        f"{g['overtime_h_per_tech_day']:.2f} |"
        for g in t["grid"]
    ]
    g = r.get("gate")
    if g:
        out += ["", "## Gate (limits written before the held-out run)", ""]
        out += [
            f"- {'PASS' if g['ok'][k] else 'FAIL'} {k}: {v} (limit {g['limits'][k]})" for k, v in g["checks"].items()
        ]
    return "\n".join(out) + "\n"


CSS = """
:root{--bg:#0d1016;--panel:#151b24;--line:#263042;--ink:#e8edf4;--ink2:#97a3b6;--ok:#3ccf8e;--bad:#ff6b6b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Inter,system-ui,sans-serif}
main{max-width:1180px;margin:0 auto;padding:34px 28px 56px}h1{font-size:28px;margin:0 0 4px}h2{font-size:18px;
margin:28px 0 12px}.sub{color:var(--ink2);margin:0 0 20px}.tiles{display:grid;grid-template-columns:repeat(4,1fr);
gap:12px}.tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}.tile b{
display:block;font-size:26px}.tile span{color:var(--ink2);font-size:13px}table{width:100%;border-collapse:collapse;
background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13.5px;margin-bottom:10px}
th,td{padding:8px 12px;border-bottom:1px solid var(--line);text-align:right}th:first-child,td:first-child{text-align:left}
th{color:var(--ink2);font-weight:500;font-size:12px}.good{color:var(--ok);font-weight:600}.bad{color:var(--bad);
font-weight:600}@media(max-width:800px){.tiles{grid-template-columns:1fr 1fr}}
"""


def html_report(r: dict[str, Any]) -> str:
    e = html.escape
    h = r["banks"]["heldout"]
    s = r["banks"]["shifted"]
    g, o = h["planners"]["greedy"], h["planners"]["optimised"]
    tiles = [
        (
            f"{pct(o['kept_share'])} vs {pct(g['kept_share'])}",
            "appointments kept: optimised plans vs the dispatcher's list (held-out)",
        ),
        (
            f"{100 * (1 - h['km_ratio']):.0f}% less",
            f"driving per job ({o['km_per_job']:.1f} km vs {g['km_per_job']:.1f})",
        ),
        (
            f"{pct(o['first_time_fix_kit'])} vs {pct(o['first_time_fix_standard'])}",
            "first-time fix: van kit planned for the day vs a standard kit",
        ),
        (
            pct(s["planners"]["optimised"]["first_time_fix_kit"]),
            "first-time fix with the planned kit in the shifted regions, where a quarter of brands were new",
        ),
    ]
    out = [
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
        f"initial-scale=1'><title>Field service evaluation</title><style>{CSS}</style><main><h1>Field service: "
        "evaluation</h1><p class='sub'>Synthetic regions of 10 technicians over four weeks; settings chosen on separate "
        "tuning regions.</p><div class='tiles'>"
    ]
    out += [f"<div class='tile'><b>{e(v)}</b><span>{e(t)}</span></div>" for v, t in tiles]
    out.append("</div>")
    for b, label in BANKS.items():
        x = r["banks"][b]
        out.append(
            f"<h2>{e(label)}: {x['regions']} regions</h2><table><tr><th>Planner</th><th>Appointments kept</th>"
            "<th>km per job</th><th>Overtime h / tech-day</th><th>Avg days waited</th><th>Backlog</th></tr>"
        )
        for k, name in LABELS.items():
            p = x["planners"][k]
            out.append(
                f"<tr><td>{e(name)}</td><td class='{'good' if k == 'optimised' else ''}'>{pct(p['kept_share'])}</td>"
                f"<td>{p['km_per_job']:.1f}</td><td>{p['overtime_h_per_tech_day']:.2f}</td><td>"
                f"{p['avg_wait_days']:.2f}</td><td>{p['backlog']:.0f}</td></tr>"
            )
        q = x["planners"]["optimised"]
        out.append(
            f"</table><p class='sub'>First-time fix: standard kit {pct(q['first_time_fix_standard'])}, planned kit "
            f"{pct(q['first_time_fix_kit'])}.</p>"
        )
    gt = r.get("gate")
    if gt:
        out.append(
            "<h2>Gate (limits written before the held-out run)</h2><table><tr><th>Check</th><th>Value</th>"
            "<th>Limit</th><th>Result</th></tr>"
        )
        for k, v in gt["checks"].items():
            ok = gt["ok"][k]
            out.append(
                f"<tr><td>{e(k)}</td><td>{v}</td><td>{gt['limits'][k]}</td><td class='{'good' if ok else 'bad'}'>"
                f"{'pass' if ok else 'fail'}</td></tr>"
            )
        out.append("</table>")
    out.append("</main></html>")
    return "".join(out) + "\n"
