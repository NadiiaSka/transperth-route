"""Check _roundabout_turn values from get_legs for trip 7070970."""
from app.db import pool
from app.osrm import get_legs
from app.routes import trip_pattern

pool.open()
pattern = trip_pattern("7070970")
pool.close()

for leg in get_legs(pattern.stops):
    for m in leg.steps:
        if "round" in m.type:
            print(
                f"{m.type:<16} {str(m.modifier):<13} -> {str(m.road):<18} "
                f"exit={m.roundabout_exit} geometry_turn={m.roundabout_turn}"
            )
