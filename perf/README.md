# Performance tests (k6)

Measures the directions-building pipeline end-to-end against the **live dev
stack** (unlike pytest, which uses fixtures/TestClient).

## Prereqs

- k6 (`winget install k6` / `choco install k6`)
- Dev stack up: `docker compose up -d db osrm` and the backend on :8000
  (`uvicorn app.main:app` from `backend/`)

## Run

```powershell
k6 run perf/directions.k6.js                       # smoke: 1 VU, 20 s
k6 run -e K6_SCENARIO=load perf/directions.k6.js   # load: 5 VUs, 1 min
k6 run -e TRIP_ID=7070981 perf/directions.k6.js    # different trip
```

## What it watches

| Metric        | Endpoint                             | Guards against                                    |
| ------------- | ------------------------------------ | ------------------------------------------------- |
| `steps_no_ai` | `GET /api/trips/{id}/steps?ai=false` | PostGIS spheroid drift, `build_steps` regressions |
| `maneuvers`   | `GET /api/trips/{id}/maneuvers`      | OSRM round-trip + httpx `trust_env` regression    |

Thresholds fail the run at p(95): smoke 1.5 s, load 3 s. Baseline measured
2026-11-07: `maneuvers` 80 ms, `steps_no_ai` 143 ms. These deterministic
budgets are the regression tripwire. The `ai=true` Gemini path is excluded —
LLM latency (~8-34 s) is external and not a code regression signal.

Note: `http.batch` issues the calls sequentially per iteration; raise
`duration` for more samples.
