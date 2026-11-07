# Backend tests

## Layout

- `unit/` — pure logic, no services. Fast: `pytest -m unit`
- `integration/` — FastAPI + PostGIS fixture DB + recorded OSRM response.
  Needs Docker (or `TEST_DATABASE_URL`): `pytest -m integration`
- `fixtures/` — checked-in inputs: GTFS mini feed (route 240 only), OSM
  `road_signals` near route 240, recorded OSRM route response + `meta.json`
- `golden/` — `manifest.json` (the golden test cases, pure data) plus one
  snapshot per case: the `/api/trips/{trip_id}/steps` response
  (`ai=false`, i.e. deterministic text). Current case: route 240 / shape 125950

Golden cases are data-driven — adding a route means recording its OSRM
response into `fixtures/osrm/` and adding a manifest entry; no new Python.

## Running

```powershell
cd backend
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
pytest                 # everything
pytest -m unit         # fast loop
pytest --cov=app       # coverage
```

The integration tests start a throwaway `postgis/postgis:16-3.4` container
(needs Docker). To use an existing scratch database instead:

```powershell
$env:TEST_DATABASE_URL = "postgresql://transperth:transperth@localhost:5432/transperth_test"
```

The database name must contain `test` — seeding runs `sql/schema.sql`, which
DROPs tables. Never point it at real data.

## Updating the golden file

After an _intended_ change to step building / signal annotation:

```powershell
$env:GOLDEN_UPDATE = "1"
pytest tests/integration/test_golden.py
Remove-Item Env:\GOLDEN_UPDATE
```

Review the diff in `golden/*.json` before committing.

## Rebuilding fixtures

With the dev stack up (`docker compose up -d db osrm`):

```powershell
python tests/fixtures/build_fixtures.py
```

This re-filters `data/gtfs` to route 240, re-exports signals near route 240
from the dev DB (read-only), and re-records the OSRM route response. Rebuild
after GTFS/OSM/OSRM data refreshes, then review + update the golden.

## Notes

- AI rewording is frozen (ADR 0001) and excluded from all tests; the golden
  pins deterministic `instruction` text with `ai=false`.
- The OSRM recording pins the external routing input, so golden failures mean
  _our_ code changed, not OSRM.- Latency/load performance tests live in `../perf/` (k6, run against the live
  dev stack) — see `../perf/README.md`.
