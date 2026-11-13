"""Command line: tomorrow's plan, reading a job request, the console, and the evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fieldops", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan", help="tomorrow's routes for the demo region")
    rd = sub.add_parser("read", help="read a job request (Claude with ANTHROPIC_API_KEY, rules otherwise)")
    rd.add_argument("text")
    sv = sub.add_parser("serve", help="the console with the demo region")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    ev = sub.add_parser("evaluate", help="planners and van kits on held-out and shifted regions")
    ev.add_argument("--out", default="eval/reports")
    ev.add_argument("--gate", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "evaluate":
        from .evaluate import run_all, save

        result = run_all(gate=args.gate)
        save(result, Path(args.out))
        print((Path(args.out) / "report.md").read_text(encoding="utf-8"))
        return 1 if args.gate and not result["gate"]["passed"] else 0
    if args.cmd == "serve":
        import uvicorn

        from .app import demo_app

        uvicorn.run(demo_app(), host=args.host, port=args.port)
        return 0
    if args.cmd == "read":
        import os

        from .app import request_json
        from .intake import Reader, rules

        req = Reader().read(args.text) if os.environ.get("ANTHROPIC_API_KEY") else rules(args.text)
        print(json.dumps(request_json(req), indent=2))
        return 0
    from .app import demo_console, hhmm
    from .schedule import route_km, timeline

    c = demo_console()
    for t in c.region.techs:
        route = c.plan.routes[t.id]
        arrivals, back, _ = timeline(t, route, c.dur)
        stops = ", ".join(f"{hhmm(a)} {j.fault}" for j, a in zip(route, arrivals, strict=True))
        print(f"{t.name:8s} {route_km(t, route):5.0f} km  home {hhmm(back)}  {stops}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
