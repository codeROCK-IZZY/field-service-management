# Known limitations

- **Synthetic regions.** Locations, durations, faults and parts are generated; the results show how the planners and
  kits behave on these patterns, not what a particular business would gain.
- **Travel is simple:** straight-line distance times a road factor at a fixed speed, no traffic, no road network.
- **Plans are made the evening before and not changed during the day.** No emergency jobs inserted mid-day, no
  re-routing when a job runs long; such jobs push the rest of the day later or to tomorrow.
- **The first-time-fix result is near a ceiling** because the fault is assumed to be diagnosed correctly at booking
  and a day's jobs fit in the flexible slots (ADR 2). Depot stock, wrong diagnoses and second faults are not
  modelled.
- **The optimiser ignores booking order** (ADR 1).
- **Job requests read with Claude are not measured** for accuracy (ADR 3).
- **The console is a demo:** one region and one day, no logins and no live tracking.
