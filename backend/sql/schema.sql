CREATE EXTENSION IF NOT EXISTS postgis;

DROP TABLE IF EXISTS stop_times, trips, shapes, shape_points, stops, routes CASCADE;

CREATE TABLE routes (
    route_id         TEXT PRIMARY KEY,
    agency_id        TEXT,
    route_short_name TEXT,
    route_long_name  TEXT,
    route_type       INT
);
CREATE INDEX routes_short_name_idx ON routes (route_short_name);

CREATE TABLE stops (
    stop_id   TEXT PRIMARY KEY,
    stop_code TEXT,
    stop_name TEXT,
    geom      geometry(Point, 4326) NOT NULL
);

CREATE TABLE shape_points (
    shape_id TEXT NOT NULL,
    seq      INT  NOT NULL,
    lat      DOUBLE PRECISION NOT NULL,
    lon      DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (shape_id, seq)
);

-- Built from shape_points after import.
CREATE TABLE shapes (
    shape_id TEXT PRIMARY KEY,
    geom     geometry(LineString, 4326) NOT NULL
);

CREATE TABLE trips (
    trip_id       TEXT PRIMARY KEY,
    route_id      TEXT NOT NULL REFERENCES routes (route_id),
    service_id    TEXT,
    direction_id  INT,
    trip_headsign TEXT,
    shape_id      TEXT
);
CREATE INDEX trips_route_idx ON trips (route_id, direction_id);

CREATE TABLE stop_times (
    trip_id        TEXT NOT NULL REFERENCES trips (trip_id),
    stop_sequence  INT  NOT NULL,
    stop_id        TEXT NOT NULL,
    arrival_time   TEXT,
    departure_time TEXT,
    PRIMARY KEY (trip_id, stop_sequence)
);
