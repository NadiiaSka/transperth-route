"""Shared pytest fixtures.

Unit tests are pure and need nothing external. Integration/golden tests seed a
throwaway PostGIS database from the checked-in fixtures and replay a recorded
OSRM response, so no live services are needed beyond Docker (or a scratch
database via TEST_DATABASE_URL).
"""
import csv
import importlib.util
import os
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / "tests" / "fixtures"
GOLDEN = BACKEND / "tests" / "golden"
OSRM_MOCK_URL = "http://osrm.test"

# app.config.Settings / app.db.pool / app.osrm._client are built at import time,
# so the env must be in place before any `app.*` module is imported.
if "TEST_DATABASE_URL" in os.environ:
    os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
os.environ.setdefault("OSRM_URL", OSRM_MOCK_URL)
os.environ.setdefault("GEMINI_API_KEY", "")


def _load_import_gtfs():
    """Import scripts/import_gtfs.py so tests reuse the real GTFS import logic."""
    spec = importlib.util.spec_from_file_location(
        "import_gtfs", BACKEND / "scripts" / "import_gtfs.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def db_url():
    """Scratch database URL. Seeding runs sql/schema.sql, which DROPs tables —
    this must never point at real data."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        dbname = url.rsplit("/", 1)[-1].split("?")[0].lower()
        if "test" not in dbname:
            pytest.skip("TEST_DATABASE_URL database name must contain 'test'")
        yield url
        return
    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed; pip install -r requirements-dev.txt")
    try:
        container = PostgresContainer("postgis/postgis:16-3.4")
        container.start()
    except Exception as exc:
        pytest.skip(f"cannot start PostGIS testcontainer (is Docker running?): {exc}")
    # get_connection_url() may embed a '+driver' scheme suffix psycopg rejects.
    yield "postgresql://" + container.get_connection_url().split("://", 1)[1]
    container.stop()


@pytest.fixture(scope="session")
def seeded_db(db_url):
    """Fresh scratch DB loaded from tests/fixtures: schema + route 240 GTFS + signals."""
    import psycopg

    import_gtfs = _load_import_gtfs()
    import_gtfs.GTFS = FIXTURES / "gtfs_mini"  # point the real importer at the mini feed
    import_gtfs.DB_URL = db_url
    import_gtfs.main()

    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute((BACKEND / "sql" / "signals.sql").read_text(encoding="utf-8"))
        with open(FIXTURES / "road_signals_240.csv", newline="", encoding="utf-8") as f:
            with cur.copy("COPY road_signals (osm_id, kind, geom) FROM STDIN") as cp:
                for osm_id, kind, geom in csv.reader(f):
                    cp.write_row((int(osm_id), kind, geom))
    return db_url


@pytest.fixture(scope="session")
def client(seeded_db, db_url):
    """FastAPI TestClient bound to the scratch DB. OSRM_URL is a fake host that
    tests intercept with respx; Gemini is disabled (ADR 0001)."""
    os.environ["DATABASE_URL"] = db_url
    os.environ["OSRM_URL"] = OSRM_MOCK_URL
    os.environ["GEMINI_API_KEY"] = ""

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
