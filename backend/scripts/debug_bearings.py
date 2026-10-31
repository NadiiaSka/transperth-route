"""Compute true approach/departure bearings at each roundabout from leg geometry."""
import math

import httpx

from app.config import settings
from app.db import pool


def bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


pool.open()
with pool.connection() as conn:
    stops = conn.execute(
        """
        SELECT s.stop_name, ST_Y(s.geom) AS lat, ST_X(s.geom) AS lon
        FROM stop_times st JOIN stops s USING (stop_id)
        WHERE st.trip_id = '7070970'
        ORDER BY st.stop_sequence
        """
    ).fetchall()
pool.close()

coords = ";".join(f"{s['lon']:.6f},{s['lat']:.6f}" for s in stops)
resp = httpx.get(
    f"{settings.osrm_url}/route/v1/driving/{coords}",
    params={
        "steps": "true",
        "overview": "false",
        "continue_straight": "true",
        "geometries": "geojson",
    },
    timeout=30,
)
data = resp.json()

for leg in data["routes"][0]["legs"]:
    for si, step in enumerate(leg["steps"]):
        m = step["maneuver"]
        if "round" not in m["type"] or m["type"].startswith("exit"):
            continue
        geom = step["geometry"]["coordinates"]  # [[lon,lat]...] travel along circle
        # approach bearing: previous step's last geometry segment
        prev_geom = leg["steps"][si - 1]["geometry"]["coordinates"] if si > 0 else geom[:2]
        (alon, alat), (blon, blat) = prev_geom[-2], prev_geom[-1]
        approach = bearing(alat, alon, blat, blon)
        # departure bearing: last 2 points of the circle geometry onto exit road
        (clon, clat), (dlon, dlat) = geom[-2], geom[-1]
        departure = bearing(clat, clon, dlat, dlon)
        delta = (departure - approach + 540) % 360 - 180
        # positive delta = heading increased = clockwise = RIGHT turn
        verdict = "R" if delta >= 35 else ("L" if delta <= -35 else "straight")
        print(
            f"exit={m.get('exit')} -> {step.get('name'):<18} "
            f"approach={approach:5.0f} depart={departure:5.0f} delta={delta:+5.0f} => {verdict}"
        )
