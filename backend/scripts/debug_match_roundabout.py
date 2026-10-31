"""Debug: check whether OSRM match emits roundabout maneuvers with various params."""
import httpx

from app.config import settings
from app.db import pool

pool.open()
with pool.connection() as conn:
    rows = conn.execute(
        "SELECT lat, lon FROM shape_points WHERE shape_id = '125949' ORDER BY seq"
    ).fetchall()
pool.close()
shape = [(r["lat"], r["lon"]) for r in rows]

for every in (3, 4, 5, 6, 8):
    thinned = shape[::every] + [shape[-1]]
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in thinned)
    resp = httpx.get(
        f"{settings.osrm_url}/match/v1/driving/{coords}",
        params={"steps": "true", "overview": "false", "gaps": "ignore"},
        timeout=60,
    )
    data = resp.json()
    hits = []
    for matching in data.get("matchings", []):
        for leg in matching["legs"]:
            for step in leg["steps"]:
                t = step["maneuver"]["type"]
                if "round" in t or "rotary" in t:
                    hits.append(
                        f"{t} {step['maneuver'].get('modifier')} -> {step.get('name')} exit={step['maneuver'].get('exit')}"
                    )
    print(f"every={every} points={len(thinned)} code={data.get('code')} roundabouts={len(hits)}")
    for h in hits:
        print("   ", h)
