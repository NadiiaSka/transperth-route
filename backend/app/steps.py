"""Build driver table rows from OSRM legs; the server owns structure, the AI only rewords."""
from .schemas import DriverStep, Leg

_ROUNDABOUT = {"roundabout", "rotary", "roundabout turn"}
_EXIT = {"exit roundabout", "exit rotary"}


def _turn_code(modifier: str | None) -> str | None:
    if modifier and modifier.endswith("left"):
        return "L"
    if modifier and modifier.endswith("right"):
        return "R"
    return None


def _maneuver_detail(m_type: str, modifier: str | None, exit_no: int | None) -> str:
    side = modifier.rsplit(" ", 1)[-1] if modifier else None
    if m_type in _ROUNDABOUT:
        return f"Roundabout, exit {exit_no}" if exit_no else "Roundabout"
    if m_type == "end of road":
        return f"End of street, turn {side}" if side else "End of street"
    if m_type == "fork":
        return f"Fork, keep {side}" if side else "Fork, continue"
    if m_type in ("on ramp", "off ramp"):
        return f"Take the {m_type}{f' {side}' if side else ''}"
    if m_type == "merge":
        return f"Merge {side}" if side else "Merge"
    if modifier == "uturn":
        return "U-turn"
    if side:
        return f"1st turn {side}"
    return "Continue"


def build_steps(legs: list[Leg]) -> list[DriverStep]:
    rows: list[DriverStep] = []
    cumulative = 0
    current_road = None

    for leg in legs:
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
            street_changed = road is not None and road != current_road
            if street_changed:
                instruction = _maneuver_detail(s.type, s.modifier, exit_no)
                rows.append(
                    DriverStep(
                        step=len(rows) + 1,
                        type="maneuver",
                        turn=_turn_code(s.modifier),
                        instruction=instruction,
                        maneuver=s.type,
                        modifier=s.modifier,
                        road=road,
                        roundabout_exit=exit_no,
                        distance_m=dist,
                        cumulative_m=cumulative,
                    )
                )
            cumulative += dist
            if road is not None:
                current_road = road
    return rows
