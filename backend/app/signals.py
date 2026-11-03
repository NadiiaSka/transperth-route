"""Traffic-control signals projected onto a route shape to annotate turns."""
from .db import pool
from .schemas import DriverStep

_SIGNAL_LABEL = {
    "traffic_signals": "traffic lights",
}

# A signal belongs to a turn when it sits within this distance of the
# position where the new street begins.
_TURN_WINDOW_M = 40

# Query-shape notes (benchmarked on route 240, 2026-11-03: 4575 ms -> 37 ms):
# - ST_Length/ST_DWithin on geography default to spheroid maths (~1 ms per
#   line-point pair) — used only where exactness matters, on few rows.
# - ST_DWithin(geometry, 0.0001) is a Cartesian pre-filter so the existing
#   geometry GiST index applies; 0.0001 deg >= 9.4 m at Perth latitudes, a
#   safe superset of the exact 8 m check.
# - length_m uses spherical geography (~0.3% shorter than spheroid, i.e. a
#   few metres per shape) and is computed once, not per candidate row.
_SQL = """
WITH line AS (
    SELECT geom, ST_Length(geom::geography, false) AS length_m
    FROM shapes WHERE shape_id = %(sid)s
),
near AS (
    SELECT rs.kind,
           ST_LineLocatePoint(l.geom, rs.geom) AS frac,
           l.length_m
    FROM road_signals rs, line l
    WHERE rs.kind = ANY(%(kinds)s)
      AND ST_DWithin(l.geom, rs.geom, 0.0001)
      AND ST_DWithin(l.geom::geography, rs.geom::geography, 8)
)
SELECT kind, round(frac * length_m)::int AS at_m
FROM near
ORDER BY at_m
"""


def signals_along_shape(shape_id: str | None) -> list[dict]:
    """Traffic signals on the route line: [{kind, at_m}], at_m = metres along shape."""
    if not shape_id:
        return []
    with pool.connection() as conn:
        return conn.execute(
            _SQL, {"sid": shape_id, "kinds": list(_SIGNAL_LABEL)}
        ).fetchall()


def annotate_turn_signals(
    steps: list[DriverStep], signals: list[dict]
) -> list[DriverStep]:
    """Tag turns that have a traffic-signal node at them. Signals away from
    any turn are dropped. The UI surfaces the tag in the street/landmark
    column; the instruction text itself stays free of signal wording."""
    if not signals:
        return steps
    by_kind = {s["kind"] for s in signals}
    if not any(k in _SIGNAL_LABEL for k in by_kind):
        return steps
    positions = [s["at_m"] for s in signals]
    for step in steps:
        if step.type != "maneuver" or not step.turn:
            continue
        if not step.instruction.startswith(("Turn", "Merge")):
            # Roundabouts, end-of-road and forks already anchor on a place.
            continue
        if any(abs(p - step.cumulative_m) <= _TURN_WINDOW_M for p in positions):
            step.traffic_signal = True
    return steps
