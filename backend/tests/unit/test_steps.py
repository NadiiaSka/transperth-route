"""Unit tests for the deterministic driver-table builder (app.steps)."""
import pytest

from app.schemas import DriverStep, Maneuver
from app.steps import (
    _maneuver_detail,
    _roundabout_turn_code,
    _turn_code,
    apply_confirmed_route_steps,
    build_steps,
)

pytestmark = pytest.mark.unit


def m(type_, modifier=None, road=None, exit=None, dist=100, rturn=None):
    return Maneuver(
        type=type_,
        modifier=modifier,
        road=road,
        roundabout_exit=exit,
        distance_m=dist,
        roundabout_turn=rturn,
    )


@pytest.mark.parametrize(
    "modifier,expected",
    [
        ("left", "L"),
        ("slight left", "L"),
        ("sharp left", "L"),
        ("right", "R"),
        ("slight right", "R"),
        ("straight", None),
        ("uturn", None),
        (None, None),
    ],
)
def test_turn_code(modifier, expected):
    assert _turn_code(modifier) == expected


@pytest.mark.parametrize(
    "geometry_turn,exit_no,expected",
    [
        ("L", 3, "L"),  # geometry wins over the exit-number fallback
        ("R", 1, "R"),
        (None, 1, "L"),  # LHT Australia: exit 1 always leaves to the left
        (None, 2, None),  # straight through
        (None, 3, "R"),
        (None, 4, "R"),
        (None, None, None),
    ],
)
def test_roundabout_turn_code(geometry_turn, exit_no, expected):
    assert _roundabout_turn_code(geometry_turn, exit_no) == expected


@pytest.mark.parametrize(
    "m_type,modifier,exit_no,road,expected",
    [
        ("turn", "right", None, "Albany Hwy", "Turn R onto Albany Hwy"),
        ("turn", "slight left", None, "Cecil Ave", "Turn L onto Cecil Ave"),
        ("turn", None, None, "Main St", "Continue onto Main St"),
        ("turn", "uturn", None, "Main St", "Make a U-turn onto Main St"),
        ("roundabout", None, 2, "New Rd", "Take exit 2 onto New Rd"),
        ("roundabout", None, None, "New Rd", "Continue onto New Rd"),
        ("end of road", "left", None, "Railway Pde", "At the end of the road, turn L onto Railway Pde"),
        ("end of road", None, None, "Railway Pde", "At the end of the road, continue onto Railway Pde"),
        ("fork", "right", None, "Hwy", "At the fork, keep R onto Hwy"),
        ("fork", None, None, "Hwy", "At the fork, continue onto Hwy"),
        ("on ramp", "left", None, "Fwy", "Take the L on ramp onto Fwy"),
        ("off ramp", None, None, "Fwy", "Take the off ramp onto Fwy"),
        ("merge", "right", None, "Fwy", "Merge R onto Fwy"),
        ("merge", None, None, "Fwy", "Merge onto Fwy"),
    ],
)
def test_maneuver_detail(m_type, modifier, exit_no, road, expected):
    assert _maneuver_detail(m_type, modifier, exit_no, road) == expected


def test_build_steps_empty():
    assert build_steps([]) == []


def test_single_turn():
    steps = build_steps([m("turn", "right", "Albany Hwy", dist=250)])
    assert len(steps) == 1
    s = steps[0]
    assert s.step == 1
    assert s.turn == "R"
    assert s.instruction == "Turn R onto Albany Hwy"
    assert s.distance_m == 250
    assert s.cumulative_m == 0


def test_same_street_distance_accumulates():
    steps = build_steps([
        m("turn", "right", "Albany Hwy", dist=250),
        m("turn", None, "Albany Hwy", dist=150),
    ])
    assert [s.distance_m for s in steps] == [400]


def test_unnamed_segment_carries_pending_turn():
    steps = build_steps([
        m("turn", "right", None, dist=50),
        m("new name", None, "Cecil Avenue", dist=300),
    ])
    assert len(steps) == 1
    assert steps[0].turn == "R"
    assert steps[0].instruction == "Turn R onto Cecil Avenue"
    assert steps[0].distance_m == 300


def test_roundabout_entry_exit_merges_into_one_row():
    steps = build_steps([
        m("roundabout", None, "Old Rd", dist=80, rturn="R"),
        m("exit roundabout", None, "New Rd", exit=2, dist=40),
    ])
    assert len(steps) == 1
    s = steps[0]
    assert s.road == "New Rd"
    assert s.distance_m == 120
    assert s.roundabout_exit == 2
    assert s.turn == "R"
    assert s.instruction == "Take exit 2 onto New Rd"


def test_roundabout_without_exit_number_continues():
    steps = build_steps([m("roundabout", None, "Old Rd", dist=80)])
    assert steps[0].turn is None
    assert steps[0].instruction == "Continue onto Old Rd"


def test_roundabout_first_exit_fallback_is_left():
    steps = build_steps([
        m("roundabout", None, None, dist=10),
        m("exit roundabout", None, "Side Rd", exit=1, dist=10),
    ])
    assert steps[0].turn == "L"


def test_roundabout_passthrough_keeps_original_turn():
    """Same road in and out: the roundabout must not reclassify the street's turn."""
    steps = build_steps([
        m("turn", "right", "Main St", dist=200),
        m("roundabout", None, "Main St", dist=30),
        m("exit roundabout", None, "Main St", exit=2, dist=30),
    ])
    assert len(steps) == 1
    assert steps[0].turn == "R"
    assert steps[0].instruction == "Turn R onto Main St"
    assert steps[0].distance_m == 260


def test_fragmented_turn_fragment_with_modifier_wins():
    """The Match API fragments a turn into several steps on one street; the
    fragment carrying the L/R modifier becomes the street's turn."""
    steps = build_steps([
        m("turn", None, "Albany Hwy", dist=30),
        m("turn", "slight right", "Albany Hwy", dist=20),
    ])
    assert len(steps) == 1
    assert steps[0].turn == "R"
    assert steps[0].instruction == "Turn R onto Albany Hwy"
    assert steps[0].distance_m == 50


def test_pending_turn_inherited_by_next_named_street():
    """Characterization: a name-change step with no modifier inherits the
    previous street's L/R turn via the pending_turn fallback."""
    steps = build_steps([
        m("turn", "left", "B St", dist=250),
        m("new name", None, "C St", dist=50),
    ])
    assert steps[1].turn == "L"
    assert steps[1].instruction == "Turn L onto C St"
    assert steps[1].cumulative_m == 250


def test_continue_when_no_pending_turn():
    steps = build_steps([
        m("turn", None, "A St", dist=100),
        m("new name", None, "B St", dist=50),
    ])
    assert steps[1].turn is None
    assert steps[1].instruction == "Continue onto B St"


def test_uturn_has_no_turn_code():
    steps = build_steps([m("turn", "uturn", "Main St", dist=20)])
    assert steps[0].turn is None
    assert steps[0].instruction == "Make a U-turn onto Main St"


def _step(road):
    return DriverStep(step=1, type="maneuver", instruction=f"onto {road}", road=road)


def test_route_51_corrections_applied():
    steps = [_step("Cecil Avenue"), _step("Railway Parade"), _step("Other St")]
    out = apply_confirmed_route_steps(steps, "51", "125825")
    assert (out[0].turn, out[0].instruction) == ("R", "Turn R onto Cecil Avenue")
    assert (out[1].turn, out[1].instruction) == ("L", "At the end of Railway Parade, turn L")
    assert out[2].instruction == "onto Other St"
    # originals are not mutated
    assert steps[0].turn is None


def test_corrections_only_for_route_51_shape_125825():
    steps = [_step("Cecil Avenue")]
    assert apply_confirmed_route_steps(steps, "240", "125950")[0].turn is None
    assert apply_confirmed_route_steps(steps, "51", "999999")[0].turn is None
