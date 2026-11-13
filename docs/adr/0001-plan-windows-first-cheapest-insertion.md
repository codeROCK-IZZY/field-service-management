# 1. Plan tight windows first, insert each job where it adds the least driving, and keep a planning buffer

## Context

A dispatcher building tomorrow's routes usually works down the list of bookings: each job goes to whichever
qualified technician can get there soonest, at the end of their day. It is fast and fair to the order people called
in, and it scatters each technician across the region. Driving eats the day, so fewer jobs fit, jobs spill to the
next day, and customers wait in for a window that is missed.

## Decision

- **Tight windows first:** morning and afternoon jobs are placed before all-day ones.
- **Cheapest insertion:** each job goes into the route and position, across every technician with the skill, that
  adds the least driving while every job on that route still starts inside its window and the day ends by 17:30.
- **Improve:** jobs are moved between and within routes while that shortens the total; jobs that didn't fit are
  retried after each round. What still doesn't fit goes to the next day.
- **A planning buffer:** jobs are planned at the historical average duration for their skill times a buffer, because
  the real duration is only known on site. The buffer is tuned **separately for each planner** on the tuning regions,
  so the baseline is tuned as carefully: 1.0 for the list, 1.15 for the optimiser.

## Results

10 held-out regions (100 technicians, four weeks, 7,913 jobs). An appointment is kept when the job is done on the
day it was booked for, inside the customer's window:

| Planner | Appointments kept | km per job | Overtime h per tech-day | Average days waited |
|---|---:|---:|---:|---:|
| Working down the list | 75.7% | 18.7 | 0.09 | 0.27 |
| **Optimised** | **91.7%** | **10.7** | 0.09 | 0.10 |

In the shifted regions (busier, longer and more variable jobs), 84.4% against 60.3% kept, with less overtime too
(0.28 h against 0.43 h per technician-day).

## Consequences

- The optimiser doesn't respect booking order: a later caller can be served before an earlier one. Every job still
  gets its window or is moved to the next day with the reason shown.
- With no buffer the optimiser packed routes too tight and ran late; the tuning table shows the trade-off between
  kept appointments and overtime for each buffer.
- Travel is straight-line distance times a road factor at a fixed speed. Real road networks and traffic would change
  the numbers for both planners.
