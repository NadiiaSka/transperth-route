"""Traffic-control signals projected onto a route shape to annotate turns."""
from .db import pool
from .schemas import DriverStep

_SIGNAL_LABEL = {
    "traffic_signals": "traffic lights",
}

# A signal belongs to a turn when it sits within this distance of the
# position where the new street begins.
_TURN_WINDOW_M = 40

_SQL = """
WITH line AS (
    SELECT geom FROM shapes WHERE shape_id = %(sid)s
),
near AS (
    SELECT rs.kind,
           ST_LineLocatePoint(l.geom, rs.geom) AS frac,
           ST_Length(l.geom::geography) AS length_m
    FROM road_signals rs, line l
    WHERE ST_DWithin(l.geom::geography, rs.geom::geography, 8)
      AND rs.kind = ANY(%(kinds)s)
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
    """Rewrite a turn's instruction to mention traffic lights when a signal
    sits at the turn. Signals away from any turn are dropped."""
    if not signals:
        return steps
    by_kind = {s["kind"] for s in signals}
    label = next((v for k, v in _SIGNAL_LABEL.items() if k in by_kind), None)
    if not label:
        return steps
    positions = [s["at_m"] for s in signals]
    for step in steps:
        if step.type != "maneuver" or not step.turn:
            continue
        if not step.instruction.startswith(("Turn", "Merge")):
            # Roundabouts, end-of-road and forks already anchor on a place.
            continue
        if any(abs(p - step.cumulative_m) <= _TURN_WINDOW_M for p in positions):
            step.instruction = f"At the {label}, {step.instruction[0].lower() + step.instruction[1:]}"
    return steps
