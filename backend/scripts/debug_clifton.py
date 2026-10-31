"""Debug: replay match_shape maneuvers around Clifton St for shape 125949."""
from app.db import pool
from app.osrm import match_shape
from app.steps import build_steps

pool.open()
with pool.connection() as conn:
    rows = conn.execute(
        "SELECT lat, lon FROM shape_points WHERE shape_id = '125949' ORDER BY seq"
    ).fetchall()
pool.close()

maneuvers = match_shape([(r["lat"], r["lon"]) for r in rows])
for idx, m in enumerate(maneuvers):
    interesting = (m.road and ("Clifton" in m.road or "Gilwell" in m.road)) or "round" in m.type
    if not interesting:
        continue
    lo, hi = max(0, idx - 3), min(len(maneuvers), idx + 4)
    for j in range(lo, hi):
        x = maneuvers[j]
        marker = ">>" if j == idx else "  "
        print(marker, j, x.type, "|", x.modifier, "|", x.road, "| exit", x.roundabout_exit, "|", x.distance_m, "m")
    print("---")

print("=== build_steps output (Clifton/Gilwell/Martin) ===")
for s in build_steps(maneuvers):
    if s.road and ("Clifton" in s.road or "Gilwell" in s.road or "Martin" in s.road):
        print(s.step, s.turn, s.maneuver, s.modifier, s.road, s.roundabout_exit, "|", s.instruction)
