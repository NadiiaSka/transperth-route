"""Load OSM traffic-control nodes (signals/stop/give_way/crossing) into PostGIS."""
import os
import sys
from pathlib import Path

import osmium
import psycopg

ROOT = Path(__file__).resolve().parents[2]
PBF = ROOT / "data" / "osm" / "perth.osm.pbf"
SCHEMA = ROOT / "backend" / "sql" / "signals.sql"
DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://transperth:transperth@localhost:5432/transperth"
)

KINDS = {
    "traffic_signals": "traffic_signals",
    "stop": "stop",
    "give_way": "give_way",
    "crossing": "crossing",
}


class SignalHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []

    def node(self, n):
        highway = n.tags.get("highway")
        kind = KINDS.get(highway)
        if kind and n.location.valid():
            self.rows.append((n.id, kind, n.location.lon, n.location.lat))


def main():
    handler = SignalHandler()
    print(f"scanning {PBF} ...")
    handler.apply_file(str(PBF), locations=False)
    print(f"found {len(handler.rows)} signal nodes")

    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
        with cur.copy(
            "COPY road_signals (osm_id, kind, geom) FROM STDIN"
        ) as cp:
            for osm_id, kind, lon, lat in handler.rows:
                cp.write_row((osm_id, kind, f"SRID=4326;POINT({lon} {lat})"))
        cur.execute("SELECT kind, count(*) FROM road_signals GROUP BY kind ORDER BY 1")
        for kind, n in cur.fetchall():
            print(f"  {kind}: {n}")


if __name__ == "__main__":
    sys.exit(main())
