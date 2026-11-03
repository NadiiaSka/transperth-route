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


def _roundabout_turn_code(
    geometry_turn: str | None, exit_no: int | None
) -> str | None:
    """L/R for a roundabout exit, from the driver's seat.

    Prefers the geometry-based turn computed in osrm.get_legs (approach vs
    departure heading). When geometry is unavailable or near-straight, fall
    back to the exit number: in left-hand-traffic Australia drivers circulate
    clockwise, so exit 1 always leaves to the left and exit 3+ wraps right.
    """
    if geometry_turn:
        return geometry_turn
    if exit_no == 1:
        return "L"
    if exit_no and exit_no >= 3:
        return "R"
    return None


def _maneuver_detail(
    m_type: str, modifier: str | None, exit_no: int | None, road: str
) -> str:
    side = modifier.rsplit(" ", 1)[-1] if modifier and modifier.endswith(("left", "right")) else None
    side_code = {"left": "L", "right": "R"}.get(side)
    if m_type in _ROUNDABOUT:
        return f"Take exit {exit_no} onto {road}" if exit_no else f"Continue onto {road}"
    if m_type == "end of road":
        return f"At the end of the road, turn {side_code} onto {road}" if side_code else f"At the end of the road, continue onto {road}"
    if m_type == "fork":
        return f"At the fork, keep {side_code} onto {road}" if side_code else f"At the fork, continue onto {road}"
    if m_type in ("on ramp", "off ramp"):
        return f"Take the {side_code} {m_type} onto {road}" if side_code else f"Take the {m_type} onto {road}"
    if m_type == "merge":
        return f"Merge {side_code} onto {road}" if side_code else f"Merge onto {road}"
    if modifier == "uturn":
        return f"Make a U-turn onto {road}"
    if side_code:
        return f"Turn {side_code} onto {road}"
    return f"Continue onto {road}"


def build_steps(maneuvers: list[Maneuver]) -> list[DriverStep]:
    streets: list[dict] = []
    pending_turn: Maneuver | None = None
    i = 0
    while i < len(maneuvers):
        maneuver = maneuvers[i]
        road, distance, exit_no = maneuver.road, maneuver.distance_m, maneuver.roundabout_exit
        is_roundabout = maneuver.type in _ROUNDABOUT
        if is_roundabout and i + 1 < len(maneuvers) and maneuvers[i + 1].type in _EXIT:
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
            # Roundabout pairs always describe the entry onto their exit road;
            # plain maneuvers only qualify via a L/R modifier, else fall back
            # to a turn carried over an unnamed segment.
            if is_roundabout:
                turn = maneuver
            else:
                turn = maneuver if _turn_code(maneuver.modifier) else pending_turn or maneuver
            streets.append(
                {
                    "road": road,
                    "distance": 0,
                    "turn": turn,
                    "exit": exit_no or turn.roundabout_exit,
                    "passed_roundabouts": 0,
                }
            )
            pending_turn = None
        else:
            current = streets[-1]["turn"]
            if is_roundabout:
                # Same road in and out: the bus passes straight through this
                # roundabout, so it must not reclassify the street's turn.
                streets[-1]["passed_roundabouts"] += 1
            elif (
                _turn_code(maneuver.modifier)
                and not _turn_code(current.modifier)
                and current.type not in _ROUNDABOUT
            ):
                # Match API fragments a turn into several steps on the same
                # street; the fragment carrying the L/R modifier is the turn.
                streets[-1]["turn"] = maneuver

        streets[-1]["distance"] += distance
        if _turn_code(maneuver.modifier):
            pending_turn = maneuver

    rows = []
    cumulative = 0
    for street in streets:
        turn = street["turn"]
        if turn.type in _ROUNDABOUT:
            turn_code = _roundabout_turn_code(turn.roundabout_turn, street["exit"])
        else:
            turn_code = _turn_code(turn.modifier)
        instruction = _maneuver_detail(
            turn.type, turn.modifier, street["exit"], street["road"]
        )
        rows.append(
            DriverStep(
                step=len(rows) + 1,
                type="maneuver",
                turn=turn_code,
                instruction=instruction,
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
        "Cecil Avenue": ("R", "Turn R onto Cecil Avenue"),
        "Railway Parade": ("L", "At the end of Railway Parade, turn L"),
    }
    return [
        step.model_copy(
            update={"turn": corrections[step.road][0], "instruction": corrections[step.road][1]}
        )
        if step.road in corrections
        else step
        for step in steps
    ]
