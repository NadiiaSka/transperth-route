// k6 performance test for the directions-building pipeline.
//
//   k6 run perf/directions.k6.js                      # smoke: 1 VU, 20 s
//   k6 run -e K6_SCENARIO=load perf/directions.k6.js  # load: 5 VUs, 1 m
//
// Requires the dev stack up: backend on :8000, db + osrm via docker compose.
// BASE_URL and TRIP_ID are overridable; defaults match the golden fixture.
import http from "k6/http";
import { check } from "k6";
import { Trend } from "k6/metrics";
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.1/index.js";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const TRIP_ID = __ENV.TRIP_ID || "7070981"; // route 240 / shape 125950

// Directions-building is the hot path: GTFS pattern -> OSRM legs ->
// build_steps -> signal annotation -> (optional) Gemini rewording.
export const options =
  __ENV.K6_SCENARIO === "load"
    ? { vus: 5, duration: "1m", thresholds: thresholds("3000") }
    : { vus: 1, duration: "20s", thresholds: thresholds("1500") };

// Budgets in ms. steps_no_ai/maneuvers guard the 4,500 ms -> ~100 ms
// regression class (spheroid drift, httpx trust_env): tight and failing.
function thresholds(p95NoAi) {
  return {
    "http_req_duration{endpoint:steps_no_ai}": [`p(95)<${p95NoAi}`],
    "http_req_duration{endpoint:maneuvers}": [`p(95)<${p95NoAi}`],
    http_req_failed: ["rate<0.01"],
  };
}

const stepsNoAi = new Trend("directions_steps_no_ai_ms", true);
const maneuvers = new Trend("directions_maneuvers_ms", true);

export default function () {
  const reqs = [
    ["GET", `${BASE_URL}/api/trips/${TRIP_ID}/steps?ai=false`, null, { tags: { endpoint: "steps_no_ai" } }],
    ["GET", `${BASE_URL}/api/trips/${TRIP_ID}/maneuvers`, null, { tags: { endpoint: "maneuvers" } }],
  ];
  const [noai, man] = http.batch(reqs);

  check(noai, { "steps ai=false 200": (r) => r.status === 200 });
  check(man, { "maneuvers 200": (r) => r.status === 200 });

  stepsNoAi.add(noai.timings.duration);
  maneuvers.add(man.timings.duration);
}

export function handleSummary(data) {
  return { stdout: textSummary(data, { indent: " ", enableColors: true }) };
}
