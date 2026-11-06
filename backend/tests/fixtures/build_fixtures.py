"""Rebuild the checked-in test fixtures.

Run with the dev services up (docker compose up -d db osrm):

    python backend/tests/fixtures/build_fixtures.py

Sources:
  - data/gtfs/*.txt           -> fixtures/gtfs_mini/          (route 240 rows only)
  - dev database road_signals -> fixtures/road_signals_240.csv (within 300 m of route-240 shapes)
  - live OSRM (OSRM_URL)      -> fixtures/osrm/               (route response for the golden trip)

The dev database is only READ. Nothing is written to it.
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg

FIXTURES = Path(__file__).resolve().parent
ROOT = FIXTURES.parents[2]  # backend/tests/fixtures -> repo root
GTFS = ROOT / "data" / "gtfs"
MINI = FIXTURES / "gtfs_mini"

ROUTE_NUMBER = "240"
GOLDEN_SHAPE = "125950"  # route 240 shape pinned by the golden test (see repo notes)
DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://transperth:transperth@localhost:5432/transperth"
)
OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5001")


def read_gtfs(name, base):
    with open(base / name, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, skipinitialspace=True)
        header = [h.strip() for h in next(reader)]
        return header, [dict(zip(header, r)) for r in reader]


def write_gtfs(name, header, rows):
    with open(MINI / name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in rows:
            writer.writerow([r.get(h, "") for h in header])


def build_gtfs_mini():
    MINI.mkdir(parents=True, exist_ok=True)

    header, routes = read_gtfs("routes.txt", GTFS)
    routes = [
        r
        for r in routes
        if r.get("route_type") == "3" and r.get("route_short_name") == ROUTE_NUMBER
    ]
    route_ids = {r["route_id"] for r in routes}
    write_gtfs("routes.txt", header, routes)

    header, trips = read_gtfs("trips.txt", GTFS)
    trips = [t for t in trips if t.get("route_id") in route_ids]
    write_gtfs("trips.txt", header, trips)
    trip_ids = {t["trip_id"] for t in trips}

    header, stop_times = read_gtfs("stop_times.txt", GTFS)
    stop_times = [s for s in stop_times if s.get("trip_id") in trip_ids]
    write_gtfs("stop_times.txt", header, stop_times)
    stop_ids = {s["stop_id"] for s in stop_times}

    header, stops = read_gtfs("stops.txt", GTFS)
    stops = [s for s in stops if s.get("stop_id") in stop_ids]
    write_gtfs("stops.txt", header, stops)

    header, shapes = read_gtfs("shapes.txt", GTFS)
    shape_ids = {t["shape_id"] for t in trips if t.get("shape_id")}
    shapes = [s for s in shapes if s.get("shape_id") in shape_ids]
    write_gtfs("shapes.txt", header, shapes)

    print(
        f"gtfs_mini: {len(routes)} routes, {len(trips)} trips, "
        f"{len(stop_times)} stop_times, {len(stops)} stops, {len(shapes)} shape points"
    )
    return trips


def build_signals():
    # Cartesian ST_DWithin pre-filter uses the road_signals GiST index; the
    # exact spheroid check runs only on survivors (0.005 deg >= 470 m at Perth
    # latitudes, a safe superset of 300 m). Same pattern as app/signals.py.
    sql = """
    SELECT DISTINCT rs.osm_id, rs.kind, ST_X(rs.geom) AS lon, ST_Y(rs.geom) AS lat
    FROM road_signals rs
    WHERE EXISTS (
        SELECT 1
        FROM shapes s
        JOIN trips t ON t.shape_id = s.shape_id
        JOIN routes r ON r.route_id = t.route_id
        WHERE r.route_short_name = %(number)s
          AND ST_DWithin(s.geom, rs.geom, 0.005)
          AND ST_DWithin(s.geom::geography, rs.geom::geography, 300)
    )
    ORDER BY rs.osm_id
    """
    with psycopg.connect(DB_URL) as conn:
        rows = conn.execute(sql, {"number": ROUTE_NUMBER}).fetchall()
    out = FIXTURES / "road_signals_240.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for osm_id, kind, lon, lat in rows:
            writer.writerow([osm_id, kind, f"SRID=4326;POINT({lon} {lat})"])
    print(f"road_signals_240.csv: {len(rows)} signals within 300 m of route {ROUTE_NUMBER} shapes")


def build_osrm_recording(trips):
    golden_trips = sorted(t["trip_id"] for t in trips if t.get("shape_id") == GOLDEN_SHAPE)
    if not golden_trips:
        sys.exit(f"no trips with shape {GOLDEN_SHAPE} in gtfs_mini; update GOLDEN_SHAPE")
    trip_id = golden_trips[0]

    _, stop_times = read_gtfs("stop_times.txt", MINI)
    _, stops = read_gtfs("stops.txt", MINI)
    by_id = {s["stop_id"]: s for s in stops}
    seq = sorted(
        (s for s in stop_times if s["trip_id"] == trip_id),
        key=lambda s: int(s["stop_sequence"]),
    )
    # Same coordinate string the app builds in osrm._coords.
    coords = ";".join(
        f"{float(by_id[s['stop_id']]['stop_lon']):.6f},{float(by_id[s['stop_id']]['stop_lat']):.6f}"
        for s in seq
    )
    with httpx.Client(trust_env=False) as client:
        resp = client.get(
            f"{OSRM_URL}/route/v1/driving/{coords}",
            params={
                "steps": "true",
                "overview": "false",
                "continue_straight": "true",
                "geometries": "geojson",
            },
            timeout=30,
        )
    data = resp.json()
    if resp.status_code != 200 or data.get("code") != "Ok":
        sys.exit(f"OSRM error: {resp.status_code} {data.get('code')} {data.get('message', '')}")

    out = FIXTURES / "osrm"
    out.mkdir(exist_ok=True)
    response_file = f"route_{ROUTE_NUMBER}_trip_{trip_id}.json"
    (out / response_file).write_text(json.dumps(data), encoding="utf-8")
    (out / f"route_{ROUTE_NUMBER}.meta.json").write_text(
        json.dumps(
            {
                "trip_id": trip_id,
                "route_number": ROUTE_NUMBER,
                "shape_id": GOLDEN_SHAPE,
                "stop_count": len(seq),
                "response_file": response_file,
                "osrm_url": OSRM_URL,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"osrm recording: {response_file} ({len(seq)} stops, trip {trip_id})")


def main():
    trips = build_gtfs_mini()
    build_signals()
    build_osrm_recording(trips)


if __name__ == "__main__":
    main()
