"""Load Transperth GTFS (bus routes only) into Postgres/PostGIS."""
import csv
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
GTFS = ROOT / "data" / "gtfs"
SCHEMA = ROOT / "backend" / "sql" / "schema.sql"
DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://transperth:transperth@localhost:5432/transperth"
)
BUS_ROUTE_TYPE = "3"


def rows(name):
    # Some feeds have spaces after commas in the header.
    with open(GTFS / name, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, skipinitialspace=True)
        header = [h.strip() for h in next(reader)]
        for r in reader:
            yield dict(zip(header, r))


def copy(cur, table, cols, it):
    n = 0
    with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
        for r in it:
            cp.write_row(r)
            n += 1
    print(f"{table}: {n} rows")


def main():
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))

        bus_routes = set()

        def route_rows():
            for r in rows("routes.txt"):
                if r["route_type"] == BUS_ROUTE_TYPE:
                    bus_routes.add(r["route_id"])
                    yield (
                        r["route_id"],
                        r["agency_id"] or None,
                        r["route_short_name"] or None,
                        r["route_long_name"] or None,
                        int(r["route_type"]),
                    )

        copy(cur, "routes", ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type"], route_rows())

        bus_trips, bus_shapes = set(), set()

        def trip_rows():
            for r in rows("trips.txt"):
                if r["route_id"] in bus_routes:
                    bus_trips.add(r["trip_id"])
                    if r["shape_id"]:
                        bus_shapes.add(r["shape_id"])
                    yield (
                        r["trip_id"],
                        r["route_id"],
                        r["service_id"] or None,
                        int(r["direction_id"]) if r["direction_id"] else None,
                        r["trip_headsign"] or None,
                        r["shape_id"] or None,
                    )

        copy(cur, "trips", ["trip_id", "route_id", "service_id", "direction_id", "trip_headsign", "shape_id"], trip_rows())

        def stop_rows():
            for r in rows("stops.txt"):
                if r["stop_lat"] and r["stop_lon"]:
                    yield (
                        r["stop_id"],
                        r.get("stop_code") or None,
                        r["stop_name"],
                        f"SRID=4326;POINT({r['stop_lon']} {r['stop_lat']})",
                    )

        copy(cur, "stops", ["stop_id", "stop_code", "stop_name", "geom"], stop_rows())

        def shape_rows():
            for r in rows("shapes.txt"):
                if r["shape_id"] in bus_shapes:
                    yield (r["shape_id"], int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"]))

        copy(cur, "shape_points", ["shape_id", "seq", "lat", "lon"], shape_rows())

        cur.execute(
            """
            INSERT INTO shapes (shape_id, geom)
            SELECT shape_id,
                   ST_MakeLine(ST_SetSRID(ST_MakePoint(lon, lat), 4326) ORDER BY seq)
            FROM shape_points
            GROUP BY shape_id
            HAVING count(*) >= 2
            """
        )

        def stop_time_rows():
            for r in rows("stop_times.txt"):
                if r["trip_id"] in bus_trips:
                    yield (r["trip_id"], int(r["stop_sequence"]), r["stop_id"], r["arrival_time"], r["departure_time"])

        copy(cur, "stop_times", ["trip_id", "stop_sequence", "stop_id", "arrival_time", "departure_time"], stop_time_rows())

        cur.execute("ANALYZE")
        conn.commit()


if __name__ == "__main__":
    sys.exit(main())
