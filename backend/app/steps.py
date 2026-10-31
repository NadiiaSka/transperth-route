"""Build driver table rows from OSRM legs; the server owns structure, the AI only rewords."""
from .schemas import DriverStep, Leg, PatternStop

_ROUNDABOUT = {"roundabout", "rotary", "roundabout turn"}
_EXIT = {"exit roundabout", "exit rotary"}


def _maneuver_text(m_type: str, modifier: str | None, road: str | None, exit_no: int | None) -> str:
    onto = f" onto {road}" if road else ""
    if m_type == "depart":
        return f"Continue along {road}" if road else "Continue straight"
    if m_type in _ROUNDABOUT:
        return f"At the roundabout take exit {exit_no}{onto}" if exit_no else f"At the roundabout{onto}"
    if m_type == "fork":
        return f"Keep {modifier or 'straight'} at the fork{onto}"
    if m_type in ("on ramp", "off ramp"):
        return f"Take the {m_type}{onto}"
    if m_type == "merge":
        return f"Merge{onto}"
    if modifier in (None, "straight") or m_type in ("new name", "continue"):
        if modifier in (None, "straight"):
            return f"Continue straight{onto}" if m_type != "new name" else f"Continue{onto}"
    if modifier == "uturn":
        return f"Make a U-turn{onto}"
    return f"Turn {modifier}{onto}"


def build_steps(legs: list[Leg], stops: list[PatternStop]) -> list[DriverStep]:
    rows: list[DriverStep] = []
    cumulative = 0

    def add(**kw):
        rows.append(DriverStep(step=len(rows) + 1, cumulative_m=cumulative, **kw))

    first = stops[0]
    add(
        type="stop",
        instruction=f"Start at {first.stop_name}",
        stop_sequence=first.sequence,
        stop_code=first.stop_code,
        stop_name=first.stop_name,
    )

    for leg, stop in zip(legs, stops[1:]):
        steps = leg.steps
        i = 0
        while i < len(steps):
            s = steps[i]
            road, dist, exit_no = s.road, s.distance_m, s.roundabout_exit
            if s.type in _ROUNDABOUT and i + 1 < len(steps) and steps[i + 1].type in _EXIT:
                nxt = steps[i + 1]
                road, dist, exit_no = nxt.road, dist + nxt.distance_m, nxt.roundabout_exit or exit_no
                i += 1
            i += 1
            cumulative += dist
            add(
                type="maneuver",
                instruction=_maneuver_text(s.type, s.modifier, road, exit_no),
                maneuver=s.type,
                modifier=s.modifier,
                road=road,
                distance_m=dist,
            )
        add(
            type="stop",
            instruction=f"Stop at {stop.stop_name}",
            stop_sequence=stop.sequence,
            stop_code=stop.stop_code,
            stop_name=stop.stop_name,
        )
    return rows
