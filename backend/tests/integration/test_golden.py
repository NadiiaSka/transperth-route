"""Data-driven golden tests: full /api pipeline against fixture DB + recorded OSRM.

Cases are pure data — to add one (e.g. route 51), record its OSRM response
into fixtures/osrm/, then add an entry to tests/golden/manifest.json. No new
Python required. After an *intended* behaviour change, regenerate goldens with:

    GOLDEN_UPDATE=1 pytest tests/integration/test_golden.py
"""
import json
import os
from pathlib import Path

import httpx
import pytest
from respx import MockRouter

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND / "tests" / "fixtures"
GOLDEN_DIR = BACKEND / "tests" / "golden"
OSRM_MOCK_URL = "http://osrm.test"  # must match conftest.OSRM_MOCK_URL

pytestmark = pytest.mark.integration


def _load_cases():
    manifest = json.loads((GOLDEN_DIR / "manifest.json").read_text(encoding="utf-8"))
    cases = []
    for entry in manifest["cases"]:
        meta_path = FIXTURES / entry["osrm_meta"]
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        body = json.loads((meta_path.parent / meta["response_file"]).read_text(encoding="utf-8"))
        cases.append({**entry, "meta": meta, "body": body})
    return cases


def pytest_generate_tests(metafunc):
    if "case" in metafunc.fixturenames:
        cases = _load_cases()
        metafunc.parametrize("case", cases, ids=[c["name"] for c in cases])


def test_find_routes(client, case):
    resp = client.get("/api/routes", params={"number": case["route_number"]})
    assert resp.status_code == 200
    variants = resp.json()
    assert variants, f"expected at least one route {case['route_number']} variant"
    assert all(v["route_number"] == case["route_number"] for v in variants)


def test_find_routes_unknown_number_404(client):
    assert client.get("/api/routes", params={"number": "987654"}).status_code == 404


def test_trip_pattern_matches_fixture(client, case):
    meta = case["meta"]
    resp = client.get(f"/api/trips/{meta['trip_id']}/pattern")
    assert resp.status_code == 200
    pattern = resp.json()
    assert pattern["variant"]["route_number"] == case["route_number"]
    assert pattern["variant"]["shape_id"] == meta["shape_id"]
    assert len(pattern["stops"]) == meta["stop_count"]
    assert len(pattern["shape"]) > 50


def test_trip_steps_golden(client, case):
    meta = case["meta"]
    router = MockRouter(assert_all_called=False)
    router.get(url__startswith=f"{OSRM_MOCK_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json=case["body"])
    )
    with router:
        resp = client.get(f"/api/trips/{meta['trip_id']}/steps", params={"ai": "false"})
    assert resp.status_code == 200, resp.text
    steps = resp.json()
    assert any(
        s["traffic_signal"] for s in steps
    ), "fixture signals: expected at least one tagged turn"

    golden_path = GOLDEN_DIR / case["golden_file"]
    if os.environ.get("GOLDEN_UPDATE"):
        golden_path.write_text(json.dumps(steps, indent=2) + "\n", encoding="utf-8")
        pytest.skip(f"wrote {golden_path}")
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert steps == golden
