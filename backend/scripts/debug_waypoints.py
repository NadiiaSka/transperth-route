"""Debug: match with waypoints at bus-stop shape indices."""
import httpx

from app.config import settings
from app.db import pool
from app.osrm import _distance_m

pool.open()
with pool.connection() as conn:
    shape_rows = conn.execute(
        "SELECT lat, lon FROM shape_points WHERE shape_id = '125949' ORDER BY seq"
    ).fetchall()
    stop_rows = conn.execute(
        """
        SELECT DISTINCT ST_Y(s.geom) AS lat, ST_X(s.geom) AS lon
        FROM stop_times st JOIN stops s USING (stop_id)
        WHERE st.trip_id = '7070970'
        ORDER BY 1, 2
        """
    ).fetchall()
pool.close()

shape = [(r["lat"], r["lon"]) for r in shape_rows]
stops = [(r["lat"], r["lon"]) for r in stop_rows]

# nearest shape index per stop
waypoint_idx = []
for s in stops:
    best = min(range(len(shape)), key=lambda i: _distance_m(s, shape[i]))
    waypoint_idx.append(best)
waypoint_idx = sorted(set(waypoint_idx))
if waypoint_idx[0] != 0:
    waypoint_idx = [0] + waypoint_idx
if waypoint_idx[-1] != len(shape) - 1:
    waypoint_idx.append(len(shape) - 1)

coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in shape)
resp = httpx.get(
    f"{settings.osrm_url}/match/v1/driving/{coords}",
    params={
        "steps": "true",
        "overview": "false",
        "gaps": "ignore",
        "waypoints": ";".join(str(i) for i in waypoint_idx),
    },
    timeout=60,
)
data = resp.json()
print("code:", data.get("code"))
n = 0
for matching in data.get("matchings", []):
    for leg in matching["legs"]:
        for step in leg["steps"]:
            t = step["maneuver"]["type"]
            if "round" in t or (step.get("name") and "Clifton" in step["name"]):
                n += 1
                print(
                    t, step["maneuver"].get("modifier"), "|",
                    step.get("name"), "| exit", step["maneuver"].get("exit"),
                    "|", round(step["distance"]), "m",
                )
print("hits:", n)
