"""Compare street sequences: match_shape vs get_legs for trip 7070970."""
from app.db import pool
from app.osrm import get_legs, match_shape
from app.routes import trip_pattern
from app.steps import build_steps

pool.open()
pattern = trip_pattern("7070970")
pool.close()

match_steps = build_steps(match_shape(pattern.shape))
leg_maneuvers = [m for leg in get_legs(pattern.stops) for m in leg.steps]
legs_steps = build_steps(leg_maneuvers)

print(f"{'MATCH':<55} {'LEGS':<55}")
print(f"{'-'*55} {'-'*55}")
for a, b in zip(match_steps, legs_steps):
    ta = f"{a.step:>2} {a.turn or '-'} {a.maneuver or '':<15} {a.road or ''} exit={a.roundabout_exit}"
    tb = f"{b.step:>2} {b.turn or '-'} {b.maneuver or '':<15} {b.road or ''} exit={b.roundabout_exit}"
    mark = " " if (a.road, a.turn) == (b.road, b.turn) else "*"
    print(mark, f"{ta:<53} {tb:<53}")
print("match rows:", len(match_steps), "| legs rows:", len(legs_steps))
