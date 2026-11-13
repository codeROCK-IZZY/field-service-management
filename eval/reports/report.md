# Field service: evaluation

Synthetic regions of 10 technicians over four weeks. An appointment is kept when the job is done on the day booked, inside the customer's window. First-time fix: the part the job turned out to need was on the van.

Chosen on the tuning regions: planning buffers {'greedy': 1.0, 'optimised': 1.15}, part-model smoothing 0.5.

## Held-out regions: 10 regions, 100 technicians

| Planner | Appointments kept | km per job | Overtime h per tech-day | Avg days waited | Backlog at end |
|---|---:|---:|---:|---:|---:|
| Dispatcher's list (nearest free technician, in booking order) | 75.7% | 18.7 | 0.09 | 0.27 | 205 |
| Optimised (tight windows first, cheapest insertion, moves between routes) | 91.7% | 10.7 | 0.09 | 0.10 | 125 |

First-time fix: standard van kit 72.8%, kit planned for the day's jobs 99.6%.

## Shifted regions (held back): busier, new brands, less history: 6 regions, 60 technicians

| Planner | Appointments kept | km per job | Overtime h per tech-day | Avg days waited | Backlog at end |
|---|---:|---:|---:|---:|---:|
| Dispatcher's list (nearest free technician, in booking order) | 60.3% | 17.9 | 0.43 | 0.46 | 250 |
| Optimised (tight windows first, cheapest insertion, moves between routes) | 84.4% | 11.1 | 0.28 | 0.16 | 196 |

First-time fix: standard van kit 71.9%, kit planned for the day's jobs 90.4%.

## Tuning regions: 4 regions, 40 technicians

| Planner | Appointments kept | km per job | Overtime h per tech-day | Avg days waited | Backlog at end |
|---|---:|---:|---:|---:|---:|
| Dispatcher's list (nearest free technician, in booking order) | 75.4% | 18.9 | 0.09 | 0.32 | 109 |
| Optimised (tight windows first, cheapest insertion, moves between routes) | 88.9% | 10.4 | 0.10 | 0.15 | 90 |

First-time fix: standard van kit 73.8%, kit planned for the day's jobs 99.5%.

## Tuning

| Planner | Buffer | Kept | km per job | Overtime h per tech-day |
|---|---:|---:|---:|---:|
| greedy | 1.0 | 75.4% | 18.9 | 0.09 |
| greedy | 1.15 | 73.0% | 19.0 | 0.05 |
| greedy | 1.3 | 69.2% | 18.8 | 0.04 |
| greedy | 1.5 | 50.4% | 18.5 | 0.01 |
| optimised | 1.0 | 88.5% | 9.6 | 0.19 |
| optimised | 1.15 | 88.9% | 10.4 | 0.10 |
| optimised | 1.3 | 86.8% | 11.0 | 0.03 |
| optimised | 1.5 | 84.0% | 11.6 | 0.02 |

## Gate (limits written before the held-out run)

- PASS heldout_km_ratio_max: 0.5717 (limit 0.75)
- PASS heldout_kept_gain_min: 0.1599 (limit 0.05)
- PASS heldout_first_time_fix_gain_min: 0.2685 (limit 0.1)
- PASS shifted_km_ratio_max: 0.6196 (limit 0.8)
- PASS shifted_first_time_fix_gain_min: 0.185 (limit 0.05)
