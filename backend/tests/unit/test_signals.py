"""Unit tests for annotate_turn_signals (app.signals) — the pure half of the
signal-annotation pipeline. signals_along_shape needs PostGIS and is covered
by the integration/golden tests."""
import pytest

from app.schemas import DriverStep
from app.signals import annotate_turn_signals

pytestmark = pytest.mark.unit


def step(instruction, turn, cumulative_m):
    return DriverStep(
        step=1, type="maneuver", turn=turn, instruction=instruction, cumulative_m=cumulative_m
    )


def signal(at_m, kind="traffic_signals"):
    return {"kind": kind, "at_m": at_m}


def test_turn_within_window_tagged():
    steps = [step("Turn R onto Davis Rd", "R", 1000)]
    out = annotate_turn_signals(steps, [signal(1030)])
    assert out[0].traffic_signal is True


def test_window_is_inclusive_40m():
    assert annotate_turn_signals([step("Turn R onto X St", "R", 1000)], [signal(1040)])[0].traffic_signal is True
    assert annotate_turn_signals([step("Turn R onto X St", "R", 1000)], [signal(1041)])[0].traffic_signal is False


def test_merge_can_be_tagged():
    steps = [step("Merge L onto Kwinana Fwy", "L", 500)]
    assert annotate_turn_signals(steps, [signal(500)])[0].traffic_signal is True


def test_roundabout_never_tagged():
    """Roundabouts anchor on a place; they stay signal-free by design."""
    steps = [step("Take exit 2 onto Main St", "L", 500)]
    assert annotate_turn_signals(steps, [signal(500)])[0].traffic_signal is False


def test_end_of_road_never_tagged():
    steps = [step("At the end of the road, turn L onto X St", "L", 500)]
    assert annotate_turn_signals(steps, [signal(500)])[0].traffic_signal is False


def test_step_without_turn_skipped():
    steps = [step("Continue onto A St", None, 500)]
    assert annotate_turn_signals(steps, [signal(500)])[0].traffic_signal is False


def test_unknown_signal_kinds_ignored():
    steps = [step("Turn R onto Davis Rd", "R", 1000)]
    assert annotate_turn_signals(steps, [signal(1000, kind="stop")])[0].traffic_signal is False


def test_empty_signals_returns_steps_unchanged():
    steps = [step("Turn R onto Davis Rd", "R", 1000)]
    assert annotate_turn_signals(steps, [])[0].traffic_signal is False
