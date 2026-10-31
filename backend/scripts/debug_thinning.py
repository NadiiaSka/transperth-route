"""Debug: show thinning rate and raw maneuvers around Clifton St after thinning."""
from app.db import pool
from app.osrm import _distance_m, match_shape

pool.open()
with pool.connection() as conn:
    rows = conn.execute(
        "SELECT lat, lon FROM shape_points WHERE shape_id = '125949' ORDER BY seq"
    ).fetchall()
pool.close()
shape = [(r["lat"], r["lon"]) for r in rows]
length_m = sum(_distance_m(a, b) for a, b in zip(shape, shape[1:]))
target = max(int(length_m / 25), 2)
print(f"points={len(shape)} length={length_m:.0f}m target={target} step={max(round(len(shape)/target),1) if len(shape) > target else 1}")

maneuvers = match_shape(shape)
print(f"maneuvers={len(maneuvers)}")
for idx, m in enumerate(maneuvers):
    if "round" in m.type or (m.road and "Clifton" in m.road):
        lo, hi = max(0, idx - 2), min(len(maneuvers), idx + 3)
        for j in range(lo, hi):
            x = maneuvers[j]
            print(">>" if j == idx else "  ", j, x.type, "|", x.modifier, "|", x.road, "| exit", x.roundabout_exit, "|", x.distance_m, "m")
        print("---")
