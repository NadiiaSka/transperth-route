CREATE EXTENSION IF NOT EXISTS postgis;

-- Traffic control / priority nodes from OSM, loaded by scripts/import_osm_signals.py
DROP TABLE IF EXISTS road_signals;

CREATE TABLE road_signals (
    osm_id BIGINT PRIMARY KEY,
    kind   TEXT NOT NULL,  -- traffic_signals | stop | give_way | crossing
    geom   geometry(Point, 4326) NOT NULL
);
CREATE INDEX road_signals_geom_idx ON road_signals USING gist (geom);
