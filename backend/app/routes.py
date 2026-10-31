import httpx
from fastapi import APIRouter, HTTPException, Query

from . import osrm
from .ai import reword
from .db import pool
from .schemas import DriverStep, Leg, PatternStop, RoutePattern, RouteVariant
from .steps import build_steps

router = APIRouter(prefix="/api")

# One row per distinct (route, direction, headsign, shape), with its most common trip as sample.
VARIANTS_SQL = """
SELECT r.route_id,
       r.route_short_name AS route_number,
       r.agency_id,
       t.direction_id,
       t.trip_headsign AS headsign,
       t.shape_id,
       count(*) AS trip_count,
    min(t.trip_id) AS sample_trip_id,
    (SELECT s.stop_name
     FROM stop_times st JOIN stops s USING (stop_id)
     WHERE st.trip_id = min(t.trip_id)
     ORDER BY st.stop_sequence ASC LIMIT 1) AS origin_stop,
    (SELECT s.stop_name
     FROM stop_times st JOIN stops s USING (stop_id)
     WHERE st.trip_id = min(t.trip_id)
     ORDER BY st.stop_sequence DESC LIMIT 1) AS destination_stop
FROM routes r
JOIN trips t USING (route_id)
WHERE r.route_short_name = %(number)s
GROUP BY r.route_id, r.route_short_name, r.agency_id, t.direction_id, t.trip_headsign, t.shape_id
ORDER BY r.route_id, t.direction_id, trip_count DESC
"""


@router.get("/routes", response_model=list[RouteVariant])
def find_routes(number: str = Query(min_length=1, max_length=10)):
    with pool.connection() as conn:
        rows = conn.execute(VARIANTS_SQL, {"number": number.strip()}).fetchall()
    if not rows:
        raise HTTPException(404, f"No bus route found for '{number}'")
    return rows


@router.get("/trips/{trip_id}/pattern", response_model=RoutePattern)
def trip_pattern(trip_id: str):
    with pool.connection() as conn:
        variant = conn.execute(
            VARIANTS_SQL.replace(
                "WHERE r.route_short_name = %(number)s",
                "WHERE t.shape_id IS NOT DISTINCT FROM (SELECT shape_id FROM trips WHERE trip_id = %(trip_id)s)"
                " AND t.route_id = (SELECT route_id FROM trips WHERE trip_id = %(trip_id)s)",
            ),
            {"trip_id": trip_id},
        ).fetchone()
        if not variant:
            raise HTTPException(404, "Trip not found")

        stops = conn.execute(
            """
            SELECT st.stop_sequence AS sequence, st.stop_id, s.stop_code, s.stop_name,
                   ST_Y(s.geom) AS lat, ST_X(s.geom) AS lon, st.arrival_time
            FROM stop_times st
            JOIN stops s USING (stop_id)
            WHERE st.trip_id = %(trip_id)s
            ORDER BY st.stop_sequence
            """,
            {"trip_id": trip_id},
        ).fetchall()

        shape = conn.execute(
            "SELECT lat, lon FROM shape_points WHERE shape_id = %(sid)s ORDER BY seq",
            {"sid": variant["shape_id"]},
        ).fetchall()

    return RoutePattern(
        variant=RouteVariant(**{**variant, "sample_trip_id": trip_id}),
        stops=[PatternStop(**s) for s in stops],
        shape=[(p["lat"], p["lon"]) for p in shape],
    )


@router.get("/trips/{trip_id}/maneuvers", response_model=list[Leg])
def trip_maneuvers(trip_id: str):
    pattern = trip_pattern(trip_id)
    try:
        return osrm.get_legs(pattern.stops)
    except (RuntimeError, httpx.HTTPError) as e:
        raise HTTPException(502, f"Routing service failed: {e}")


@router.get("/trips/{trip_id}/steps", response_model=list[DriverStep])
def trip_steps(trip_id: str, ai: bool = True):
    pattern = trip_pattern(trip_id)
    try:
        legs = osrm.get_legs(pattern.stops)
    except (RuntimeError, httpx.HTTPError) as e:
        raise HTTPException(502, f"Routing service failed: {e}")
    steps = build_steps(legs)
    return reword(steps) if ai else steps
