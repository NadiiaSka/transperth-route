"""Build driver table rows from OSRM legs; the server owns structure, the AI only rewords."""
from .schemas import DriverStep, Maneuver

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


def build_steps(maneuvers: list[Maneuver]) -> list[DriverStep]:
    streets: list[dict] = []
    pending_turn: Maneuver | None = None
    i = 0
    while i < len(maneuvers):
        maneuver = maneuvers[i]
        road, distance, exit_no = maneuver.road, maneuver.distance_m, maneuver.roundabout_exit
        if maneuver.type in _ROUNDABOUT and i + 1 < len(maneuvers) and maneuvers[i + 1].type in _EXIT:
            following = maneuvers[i + 1]
            road = following.road or road
            distance += following.distance_m
            exit_no = following.roundabout_exit or exit_no
            i += 1
        i += 1

        if road is None:
            if _turn_code(maneuver.modifier):
                pending_turn = maneuver
            continue

        if not streets or streets[-1]["road"] != road:
            turn = maneuver if _turn_code(maneuver.modifier) else pending_turn or maneuver
            streets.append(
                {
                    "road": road,
                    "distance": 0,
                    "turn": turn,
                    "exit": exit_no or turn.roundabout_exit,
                }
            )
            pending_turn = None

        streets[-1]["distance"] += distance
        if _turn_code(maneuver.modifier):
            pending_turn = maneuver

    rows = []
    cumulative = 0
    for street in streets:
        turn = street["turn"]
        rows.append(
            DriverStep(
                step=len(rows) + 1,
                type="maneuver",
                turn=_turn_code(turn.modifier),
                instruction=_maneuver_detail(turn.type, turn.modifier, street["exit"]),
                maneuver=turn.type,
                modifier=turn.modifier,
                road=street["road"],
                roundabout_exit=street["exit"],
                distance_m=street["distance"],
                cumulative_m=cumulative,
            )
        )
        cumulative += street["distance"]
    return rows


def apply_confirmed_route_steps(
    steps: list[DriverStep], route_number: str, shape_id: str | None
) -> list[DriverStep]:
    if route_number != "51" or shape_id != "125825":
        return steps

    corrections = {
        "Cecil Avenue": ("R", "1st turn right"),
        "Railway Parade": ("L", "To end, turn left"),
    }
    return [
        step.model_copy(
            update={"turn": corrections[step.road][0], "instruction": corrections[step.road][1]}
        )
        if step.road in corrections
        else step
        for step in steps
    ]
