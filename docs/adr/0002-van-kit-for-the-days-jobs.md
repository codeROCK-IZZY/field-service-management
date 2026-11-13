# 2. Load part of each van for the day's jobs, from what each fault needed on each brand

## Context

A visit that needs a part the van doesn't carry becomes two visits: diagnose, order, come back. Vans carry a standard
kit, the parts used most often, and that misses the brand-specific parts many faults need.

## Decision

- A van holds 40 different parts. **30 are a core** every van carries (the most used parts); **10 are flexible**,
  chosen each evening for that technician's route.
- From past jobs: how often each fault on each brand needed each part, **smoothed towards the fault on any brand**
  (0.5 pseudo-jobs, chosen on the tuning regions). A brand never seen before falls back to the fault alone.
- The flexible slots are filled greedily: each time, the part with the most expected first-time fixes on the route
  that the van doesn't already cover.
- The baseline is the same 40 slots holding the 40 most used parts.

## Results

| First-time fix | Standard kit | Kit planned for the day |
|---|---:|---:|
| Held-out regions | 72.8% | **99.6%** |
| Shifted regions (a quarter of equipment from brands never seen) | 72.0% | **90.5%** |

## Consequences

- **The held-out number is near a ceiling, and that is a property of the simulation.** About five jobs a day, each
  needing one of three or four candidate parts, fit easily into 10 flexible slots. It assumes the fault is diagnosed
  correctly when the job is booked; a wrong diagnosis would load the wrong parts. Real first-time-fix rates also
  depend on things not modelled here (access, a second fault, the customer not home).
- **New brands are where it loses ground:** without history for a brand, the model only knows what the fault needs
  in general, and brand-specific parts are missed. That is what the shifted regions show.
- Loading the van the evening before needs the part to be in stock at the depot; depot stock is not modelled.
