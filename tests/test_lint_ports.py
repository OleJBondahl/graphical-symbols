"""Ports group: the seven `port-*` rules, and the wire lane."""

import math
from dataclasses import replace
from pathlib import Path

import pytest
from build_symbol import plain_symbol
from fixture_pipeline import run_fixture_by_file
from hypothesis import given, settings
from hypothesis import strategies as st

from graphical_symbols.build import load_library
from graphical_symbols.geometry import (
    Arc,
    Circle,
    Direction,
    Fill,
    Line,
    Orientation,
    Point,
    Polyline,
    Text,
)
from graphical_symbols.lint import CHECKS, RULES, lint
from graphical_symbols.lint.ports import (
    port_duplicate_id,
    port_lane_clear,
    port_off_geometry,
    port_off_wiring_grid,
    port_on_body_edge,
    port_position_shared,
    port_spacing,
)
from graphical_symbols.model import Allow, Node, PathKind, Port, Severity, Slot
from graphical_symbols.model import Path as SymbolPath
from graphical_symbols.orient import orient

P = Point
N, E, S, W = Direction.N, Direction.E, Direction.S, Direction.W
GUIDE = Path(__file__).resolve().parent / "fixtures" / "guide"
PORT_RULES = (
    "port-duplicate-id",
    "port-off-wiring-grid",
    "port-off-geometry",
    "port-on-body-edge",
    "port-lane-clear",
    "port-spacing",
    "port-position-shared",
)


def where(findings):
    return [(f.rule, f.location) for f in findings]


def port(id_, x, y, direction):
    return Port(id_, P(x, y), direction)


def slot(id_, x, y, side, size):
    return Slot(id_, P(x, y), side, size)


@pytest.fixture(scope="module")
def library():
    return load_library(GUIDE)


class TestRegistration:
    @pytest.mark.parametrize("rule_id", PORT_RULES)
    def test_every_ports_rule_is_registered_with_a_check(self, rule_id):
        rule = RULES[rule_id]
        assert (rule.group, rule.severity) == ("Ports", Severity.ERROR)
        assert rule_id in CHECKS

    def test_only_the_body_edge_and_lane_rules_depend_on_the_orientation(self):
        dependent = {r for r in PORT_RULES if RULES[r].orientation_dependent}
        assert dependent == {"port-on-body-edge", "port-lane-clear"}


# The lane of a north port at (0, -2) is x in (-0.25, 0.25), y < -2, and likewise turned.
LANES = {
    N: (port("p", 0, -2, N), Line(P(-1, -3), P(1, -3)), Line(P(-1, -1), P(1, -1))),
    S: (port("p", 0, 2, S), Line(P(-1, 3), P(1, 3)), Line(P(-1, 1), P(1, 1))),
    E: (port("p", 2, 0, E), Line(P(3, -1), P(3, 1)), Line(P(1, -1), P(1, 1))),
    W: (port("p", -2, 0, W), Line(P(-3, -1), P(-3, 1)), Line(P(-1, -1), P(-1, 1))),
}


class TestPortLaneClear:
    def test_no_ports_are_clean(self):
        assert port_lane_clear(plain_symbol()) == ()

    @pytest.mark.parametrize("direction", list(Direction))
    def test_an_element_across_the_lane_fires_at_the_port(self, direction):
        p, across, _ = LANES[direction]
        (found,) = port_lane_clear(plain_symbol(ports=(p,), elements=(across,)))
        assert (found.rule, found.severity, found.location) == (
            "port-lane-clear",
            Severity.ERROR,
            "ports[0]",
        )
        assert found.orientation is None
        assert "'p'" in found.message
        assert "elements[0]" in found.message

    @pytest.mark.parametrize("direction", list(Direction))
    def test_an_element_behind_the_port_is_not_in_the_lane(self, direction):
        p, _, behind = LANES[direction]
        assert port_lane_clear(plain_symbol(ports=(p,), elements=(behind,))) == ()

    def test_the_ports_own_lead_ends_at_t_zero_and_is_clean(self):
        symbol = plain_symbol(ports=(port("in", 0, -2, N),), elements=(Line(P(0, -2), P(0, -1)),))
        assert port_lane_clear(symbol) == ()

    def test_a_lead_that_runs_on_past_the_port_fires(self):
        symbol = plain_symbol(ports=(port("in", 0, -2, N),), elements=(Line(P(0, -3), P(0, -1)),))
        assert where(port_lane_clear(symbol)) == [("port-lane-clear", "ports[0]")]

    def test_the_lane_is_unbounded(self):
        symbol = plain_symbol(
            ports=(port("in", 0, -2, N),), elements=(Line(P(-1, -1000), P(1, -1000)),)
        )
        assert where(port_lane_clear(symbol)) == [("port-lane-clear", "ports[0]")]

    def test_an_element_a_quarter_module_beside_the_wire_only_touches_the_lane(self):
        p = port("in", 0, -2, N)
        assert (
            port_lane_clear(plain_symbol(ports=(p,), elements=(Line(P(0.25, -5), P(0.25, -3)),)))
            == ()
        )
        assert (
            port_lane_clear(plain_symbol(ports=(p,), elements=(Line(P(-0.25, -5), P(-0.25, -3)),)))
            == ()
        )
        assert port_lane_clear(
            plain_symbol(ports=(p,), elements=(Line(P(0.125, -5), P(0.125, -3)),))
        )

    def test_a_slot_box_across_the_lane_fires_and_names_the_slot(self):
        symbol = plain_symbol(
            ports=(port("in", 0, -2, N),),
            slots=(slot("marking.in", -0.5, -3, E, (1.5, 1)),),
        )
        (found,) = port_lane_clear(symbol)
        assert found.location == "ports[0]"
        assert "slots.marking.in" in found.message

    def test_a_marking_box_a_quarter_module_beside_the_wire_only_touches_the_lane(self):
        symbol = plain_symbol(
            ports=(port("in", 0, -2, N),),
            slots=(
                slot("marking.in", 0.25, -3, E, (1.5, 1)),
                slot("value", -0.25, -3, W, (1.5, 1)),
            ),
        )
        assert port_lane_clear(symbol) == ()

    def test_moving_the_touching_box_inward_by_one_grid_step_makes_it_fire(self):
        touching = plain_symbol(
            ports=(port("in", 0, -2, N),), slots=(slot("m", 0.25, -3, E, (1.5, 1)),)
        )
        moved = replace(touching, slots=(slot("m", 0.125, -3, E, (1.5, 1)),))
        assert port_lane_clear(touching) == ()
        assert where(port_lane_clear(moved)) == [("port-lane-clear", "ports[0]")]

    def test_a_slot_box_beside_the_lead_and_behind_the_port_is_clean(self):
        symbol = plain_symbol(
            ports=(port("in", 0, -3, N),),
            elements=(Line(P(0, -3), P(0, -1)),),
            slots=(slot("marking.in", -0.5, -2, E, (1.5, 1)),),
        )
        assert port_lane_clear(symbol) == ()

    def test_a_circle_and_an_arc_and_text_in_the_lane_fire(self):
        p = port("in", 0, -2, N)
        for element in (
            Circle(P(0, -4), 1),
            Circle(P(0, -4), 1, Fill.SOLID),
            Arc(P(0, -4), 1, 0, 90),
            Text("M", P(0, -3), 1),
            Polyline((P(-1, -4), P(1, -4), P(1, -3), P(-1, -3)), closed=True, fill=Fill.SOLID),
        ):
            assert port_lane_clear(plain_symbol(ports=(p,), elements=(element,))), element

    def test_an_empty_body_outline_around_the_wire_is_not_in_the_lane_when_behind(self):
        outline = Polyline((P(-2, -1), P(2, -1), P(2, 1), P(-2, 1)), closed=True)
        symbol = plain_symbol(ports=(port("in", 0, -3, N),), elements=(outline,))
        assert port_lane_clear(symbol) == ()

    def test_one_finding_per_port_lists_every_offender(self):
        symbol = plain_symbol(
            ports=(port("a", 0, -2, N), port("b", 4, -2, N), port("c", 8, 2, S)),
            elements=(Line(P(-1, -3), P(1, -3)), Line(P(-1, -4), P(1, -4))),
            slots=(slot("s", 3.5, -3, E, (1, 1)),),
        )
        found = port_lane_clear(symbol)
        assert [f.location for f in found] == ["ports[0]", "ports[1]"]
        assert "elements[0]" in found[0].message
        assert "elements[1]" in found[0].message
        assert "slots.s" in found[1].message

    def test_a_port_is_tested_in_its_own_direction(self):
        # a line above an east port is behind neither: the east lane is to its right
        symbol = plain_symbol(ports=(port("p", 0, 0, E),), elements=(Line(P(-1, -3), P(1, -3)),))
        assert port_lane_clear(symbol) == ()

    def test_a_far_away_port_still_has_a_lane_that_reaches_the_symbol(self):
        symbol = plain_symbol(ports=(port("p", 0, 100, N),), elements=(Line(P(-1, 0), P(1, 0)),))
        assert where(port_lane_clear(symbol)) == [("port-lane-clear", "ports[0]")]


def orientations_of(findings):
    return {f.orientation for f in findings}


# The symbol of the orientation-only fixture, built by hand: clean as it stands, but its slot
# box does not turn with the symbol and lands in a wire lane after R90.
TURNED_INTO_A_LANE = plain_symbol(
    ports=(port("in", 0, -2, N), port("out", 0, 2, S)),
    paths=(SymbolPath("in", "out", PathKind.CONDUCTOR),),
    elements=(Line(P(0, -2), P(0, -1)), Line(P(0, 2), P(0, 1))),
    slots=(slot("marking.in", 0.75, -3, N, (1, 3)),),
)


class TestPortLaneClearInEveryOrientation:
    def test_the_base_orientation_of_the_hand_built_symbol_is_clean(self):
        assert port_lane_clear(TURNED_INTO_A_LANE) == ()

    def test_after_a_turn_the_box_lands_in_the_lane(self):
        turned = orient(TURNED_INTO_A_LANE, Orientation.R90)
        (found,) = port_lane_clear(turned)
        assert found.location == "ports[0]"
        assert "slots.marking.in" in found.message

    def test_lint_reports_the_orientations_it_fires_in_and_not_the_base_one(self):
        found = lint(TURNED_INTO_A_LANE)
        assert {f.rule for f in found} == {"port-lane-clear"}
        assert Orientation.R0 not in orientations_of(found)
        assert Orientation.R90 in orientations_of(found)

    def test_the_orientation_only_fixture_fires_only_outside_the_base_orientation(self):
        findings = run_fixture_by_file("port-lane-clear")["S00002"]
        assert {f.rule for f in findings} == {"port-lane-clear"}
        orientations = orientations_of(findings)
        assert orientations
        assert Orientation.R0 not in orientations
        assert orientations == orientations_of(lint(TURNED_INTO_A_LANE))

    def test_the_base_fixture_fires_in_the_base_orientation(self):
        findings = run_fixture_by_file("port-lane-clear")["S00001"]
        assert Orientation.R0 in orientations_of(findings)

    def test_an_exemption_covers_an_orientation_the_rule_fires_in_and_is_not_unused(self):
        exempted = replace(TURNED_INTO_A_LANE, lint_allow=(Allow("port-lane-clear", "a test"),))
        assert lint(exempted) == ()

    def test_an_exemption_of_a_rule_that_fires_in_no_orientation_is_unused(self):
        clean = replace(
            TURNED_INTO_A_LANE, slots=(), lint_allow=(Allow("port-lane-clear", "a test"),)
        )
        assert where(lint(clean)) == [("allow-unused", "lint_allow[0]")]


class TestPortDuplicateId:
    def test_distinct_ids_and_no_ports_are_clean(self):
        assert port_duplicate_id(plain_symbol()) == ()
        assert port_duplicate_id(plain_symbol(ports=(port("a", 0, 0, N), port("b", 0, 1, S)))) == ()

    def test_a_shared_id_fires_at_the_later_port_and_names_the_id(self):
        symbol = plain_symbol(ports=(port("in", 0, 0, N), port("x", 1, 0, N), port("in", 2, 0, S)))
        (found,) = port_duplicate_id(symbol)
        assert (found.rule, found.severity, found.location) == (
            "port-duplicate-id",
            Severity.ERROR,
            "ports[2]",
        )
        assert "'in'" in found.message
        assert "ports[0]" in found.message

    def test_three_with_one_id_give_two_findings(self):
        symbol = plain_symbol(ports=tuple(port("a", i, 0, N) for i in range(3)))
        assert [f.location for f in port_duplicate_id(symbol)] == ["ports[1]", "ports[2]"]

    def test_ids_are_compared_exactly(self):
        assert port_duplicate_id(plain_symbol(ports=(port("a", 0, 0, N), port("A", 1, 0, N)))) == ()


class TestPortOffWiringGrid:
    @pytest.mark.parametrize("at", [(0, 0), (1, -2), (-3, 4), (1e6, -1e6), (2.0, 0.0), (-0.0, 3)])
    def test_whole_modules_are_on_the_grid(self, at):
        assert port_off_wiring_grid(plain_symbol(ports=(port("p", at[0], at[1], N),))) == ()

    @pytest.mark.parametrize("at", [(0.5, 0), (0, 0.125), (1.0000001, 0), (0, -2.75), (0.5, 0.5)])
    def test_anything_else_is_off_it(self, at):
        (found,) = port_off_wiring_grid(plain_symbol(ports=(port("p", at[0], at[1], N),)))
        assert (found.rule, found.severity, found.location) == (
            "port-off-wiring-grid",
            Severity.ERROR,
            "ports[0]",
        )
        assert "'p'" in found.message

    def test_the_message_names_each_coordinate_that_is_off(self):
        (both,) = port_off_wiring_grid(plain_symbol(ports=(port("p", 0.5, 0.25, N),)))
        assert "x 0.5" in both.message
        assert "y 0.25" in both.message
        (only_y,) = port_off_wiring_grid(plain_symbol(ports=(port("p", 1, 0.25, N),)))
        assert "x 1" not in only_y.message
        assert "y 0.25" in only_y.message

    def test_each_port_off_the_grid_gets_its_own_finding(self):
        symbol = plain_symbol(
            ports=(port("a", 0.5, 0, N), port("b", 0, 0, N), port("c", 0, 1.5, S))
        )
        assert [f.location for f in port_off_wiring_grid(symbol)] == ["ports[0]", "ports[2]"]

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_non_finite_positions_are_off_the_grid(self, bad):
        assert port_off_wiring_grid(plain_symbol(ports=(port("p", bad, 0, N),)))
        assert port_off_wiring_grid(plain_symbol(ports=(port("p", 0, bad, N),)))


LEAD = (Line(P(0, -2), P(0, -1)),)


class TestPortOffGeometry:
    def fires(self, at, *elements):
        return bool(
            port_off_geometry(plain_symbol(ports=(port("p", at[0], at[1], N),), elements=elements))
        )

    def test_a_port_at_either_end_of_a_line_is_on_geometry(self):
        assert not self.fires((0, -2), *LEAD)
        assert not self.fires((0, -1), *LEAD)

    def test_a_port_in_the_middle_of_a_line_is_not(self):
        assert self.fires((0, -1.5), *LEAD)

    def test_a_port_beside_a_line_and_a_port_with_no_elements_are_not(self):
        assert self.fires((1, -2), *LEAD)
        assert self.fires((0, 0))

    def test_the_finding_is_at_the_port(self):
        (found,) = port_off_geometry(plain_symbol(ports=(port("p", 5, 5, N),), elements=LEAD))
        assert (found.rule, found.severity, found.location) == (
            "port-off-geometry",
            Severity.ERROR,
            "ports[0]",
        )
        assert "'p'" in found.message

    def test_a_port_is_at_the_ends_of_an_open_polyline_and_not_at_its_bends(self):
        chain = Polyline((P(0, -2), P(0, 0), P(2, 0)))
        assert not self.fires((0, -2), chain)
        assert not self.fires((2, 0), chain)
        assert self.fires((0, 0), chain)
        assert self.fires((0, -1), chain)

    def test_a_port_is_anywhere_on_a_closed_outline(self):
        outline = Polyline((P(-2, -1), P(2, -1), P(2, 1), P(-2, 1)), closed=True)
        for at in ((-2, -1), (0, -1), (2, 0), (0, 1), (-2, 0)):
            assert not self.fires(at, outline), at
        assert self.fires((0, 0), outline)

    def test_a_port_in_a_filled_closed_polyline_counts_as_on_geometry(self):
        filled = Polyline((P(-2, -1), P(2, -1), P(2, 1), P(-2, 1)), closed=True, fill=Fill.SOLID)
        assert not self.fires((0, 0), filled)
        assert self.fires((0, 0), Polyline(filled.points, closed=False, fill=Fill.SOLID))

    def test_a_port_is_on_a_circle_and_in_a_filled_one(self):
        assert not self.fires((1, 0), Circle(P(0, 0), 1))
        assert self.fires((0, 0), Circle(P(0, 0), 1))
        assert not self.fires((0, 0), Circle(P(0, 0), 1, Fill.SOLID))
        assert self.fires((3, 0), Circle(P(0, 0), 1, Fill.SOLID))

    def test_a_port_is_on_an_arc_within_its_sweep_only(self):
        arc = Arc(P(0, 0), 2, 0, 90)
        assert not self.fires((2, 0), arc)
        assert not self.fires((0, 2), arc)
        assert self.fires((-2, 0), arc)
        assert self.fires((0, 0), arc)

    def test_text_is_not_geometry(self):
        assert self.fires((0, 0), Text("M", P(0, 0), 1))


class TestPortOnBodyEdge:
    def fires(self, port_, *elements):
        return bool(port_on_body_edge(plain_symbol(ports=(port_,), elements=elements)))

    @pytest.mark.parametrize("direction", list(Direction))
    def test_a_port_on_the_matching_side_is_clean(self, direction):
        x, y = {N: (0, -2), S: (0, 2), E: (2, 0), W: (-2, 0)}[direction]
        body = (Line(P(0, -2), P(0, 2)), Line(P(-2, 0), P(2, 0)))
        assert not self.fires(port("p", x, y, direction), *body)

    @pytest.mark.parametrize("direction", list(Direction))
    def test_a_port_on_the_opposite_side_fires(self, direction):
        x, y = {N: (0, 2), S: (0, -2), E: (-2, 0), W: (2, 0)}[direction]
        body = (Line(P(0, -2), P(0, 2)), Line(P(-2, 0), P(2, 0)))
        symbol = plain_symbol(ports=(port("p", x, y, direction),), elements=body)
        (found,) = port_on_body_edge(symbol)
        assert (found.rule, found.severity, found.location) == (
            "port-on-body-edge",
            Severity.ERROR,
            "ports[0]",
        )
        assert "'p'" in found.message
        assert direction.name in found.message

    def test_a_port_short_of_the_side_fires(self):
        body = (Line(P(0, -2), P(0, 0)),)
        assert not self.fires(port("p", 0, -2, N), *body)
        assert self.fires(port("p", 0, -1, N), *body)
        assert self.fires(port("p", 0, -3, N), *body)

    def test_the_port_must_lie_within_the_side_and_not_only_on_its_line(self):
        body = (Line(P(0, -2), P(0, 2)),)
        assert not self.fires(port("p", 0, -2, N), *body)
        assert self.fires(port("p", 1, -2, N), *body)
        assert self.fires(port("p", 0, 3, E), *body)

    def test_a_port_at_a_corner_is_on_both_sides_that_meet_there(self):
        body = (Polyline((P(-2, -2), P(2, -2), P(2, 2), P(-2, 2)), closed=True),)
        assert not self.fires(port("p", -2, -2, N), *body)
        assert not self.fires(port("p", -2, -2, W), *body)
        assert self.fires(port("p", -2, -2, S), *body)

    def test_the_comparison_is_exact(self):
        body = (Line(P(0, -2), P(0, 2)),)
        assert self.fires(port("p", 0, -2.0000001, N), *body)

    def test_a_wide_text_element_widens_the_body_and_can_push_the_side_away(self):
        # the text box is 4.8 M wide: it reaches x = 2.4 while the lead stops at x = 2
        body = (Line(P(2, 0), P(0, 0)), Text("ABCDEFGH", P(0, 0), 1))
        assert self.fires(port("p", 2, 0, E), *body)

    def test_the_side_is_the_body_box_of_the_oriented_symbol(self):
        # text does not turn: the lead's port is on the body edge in R0 but not after R90
        symbol = plain_symbol(
            ports=(port("p", 0, -2, N),),
            elements=(Line(P(0, -2), P(0, 0)), Text("ABCDEFGH", P(0, -1), 1)),
        )
        assert port_on_body_edge(symbol) == ()
        assert where(port_on_body_edge(orient(symbol, Orientation.R90))) == [
            ("port-on-body-edge", "ports[0]")
        ]

    def test_the_orientation_only_fixture_is_clean_in_the_base_orientation(self):
        findings = run_fixture_by_file("port-on-body-edge")["S00002"]
        assert {f.rule for f in findings} == {"port-on-body-edge"}
        assert orientations_of(findings)
        assert Orientation.R0 not in orientations_of(findings)


class TestPortSpacing:
    @pytest.mark.parametrize("gap", [0, 2, 4, 10, -2, 2.0])
    def test_a_multiple_of_two_modules_along_the_side_is_clean(self, gap):
        symbol = plain_symbol(ports=(port("a", 0, -2, N), port("b", gap, -2, N)))
        assert port_spacing(symbol) == ()

    @pytest.mark.parametrize("gap", [1, 3, 0.5, -1, 2.125, 1e-9])
    def test_anything_else_fires_at_the_later_port(self, gap):
        symbol = plain_symbol(ports=(port("a", 0, -2, N), port("b", gap, -2, N)))
        (found,) = port_spacing(symbol)
        assert (found.rule, found.severity, found.location) == (
            "port-spacing",
            Severity.ERROR,
            "ports[1]",
        )
        assert "'a'" in found.message
        assert "'b'" in found.message

    def test_it_is_measured_along_x_for_north_and_south_ports(self):
        assert port_spacing(plain_symbol(ports=(port("a", 0, -2, N), port("b", 0, -3, N)))) == ()
        assert port_spacing(plain_symbol(ports=(port("a", 0, 2, S), port("b", 1, 2, S))))

    def test_it_is_measured_along_y_for_east_and_west_ports(self):
        assert port_spacing(plain_symbol(ports=(port("a", 2, 0, E), port("b", 3, 0, E)))) == ()
        assert port_spacing(plain_symbol(ports=(port("a", 2, 0, W), port("b", 2, 1, W))))

    def test_ports_with_different_directions_are_never_compared(self):
        symbol = plain_symbol(
            ports=(
                port("a", 0, -2, N),
                port("b", 1, -2, S),
                port("c", 1, -2, E),
                port("d", 1, -2, W),
            )
        )
        assert port_spacing(symbol) == ()

    def test_each_later_port_is_tested_against_the_earlier_ones(self):
        symbol = plain_symbol(ports=(port("a", 0, -2, N), port("b", 1, -2, N), port("c", 2, -2, N)))
        assert [f.location for f in port_spacing(symbol)] == ["ports[1]", "ports[2]"]
        symbol = plain_symbol(ports=(port("a", 0, -2, N), port("b", 2, -2, N), port("c", 5, -2, N)))
        assert [f.location for f in port_spacing(symbol)] == ["ports[2]"]

    def test_ports_at_the_same_coordinate_are_fine(self):
        symbol = plain_symbol(ports=(port("a", 1, -2, N), port("b", 1, -2, N)))
        assert port_spacing(symbol) == ()

    def test_a_non_finite_coordinate_is_not_a_multiple(self):
        symbol = plain_symbol(ports=(port("a", 0, -2, N), port("b", math.inf, -2, N)))
        assert port_spacing(symbol)


class TestPortPositionShared:
    def test_ports_at_different_positions_are_clean(self):
        symbol = plain_symbol(ports=(port("a", 0, 0, N), port("b", 0, 1, N)))
        assert port_position_shared(symbol) == ()

    def test_two_ports_of_different_nodes_at_one_position_fire_at_the_later_one(self):
        symbol = plain_symbol(ports=(port("a", 0, 0, N), port("b", 1, 0, N), port("c", 0, 0, E)))
        (found,) = port_position_shared(symbol)
        assert (found.rule, found.severity, found.location) == (
            "port-position-shared",
            Severity.ERROR,
            "ports[2]",
        )
        assert "'a'" in found.message
        assert "'c'" in found.message

    def test_ports_of_one_node_may_share_a_position(self):
        symbol = plain_symbol(
            ports=(port("a", 0, 0, N), port("b", 0, 0, E)), nodes=(Node(("a", "b")),)
        )
        assert port_position_shared(symbol) == ()

    def test_a_port_in_a_node_and_a_port_in_no_node_are_different_nodes(self):
        symbol = plain_symbol(
            ports=(port("a", 0, 0, N), port("b", 0, 0, E), port("c", 0, 0, S)),
            nodes=(Node(("a", "b")),),
        )
        (found,) = port_position_shared(symbol)
        assert found.location == "ports[2]"

    def test_the_first_earlier_port_of_another_node_is_named(self):
        symbol = plain_symbol(
            ports=(port("a", 0, 0, N), port("b", 0, 0, E), port("c", 0, 0, S)),
            nodes=(Node(("a", "b")),),
        )
        (found,) = port_position_shared(symbol)
        assert "'a'" in found.message

    def test_two_nodes_each_with_ports_at_one_position_fire_once_per_later_port(self):
        symbol = plain_symbol(
            ports=tuple(port(i, 0, 0, d) for i, d in zip("abcd", Direction, strict=True)),
            nodes=(Node(("a", "b")), Node(("c", "d"))),
        )
        assert [f.location for f in port_position_shared(symbol)] == ["ports[2]", "ports[3]"]

    def test_unknown_and_repeated_port_names_in_nodes_do_not_raise_and_the_first_node_wins(self):
        symbol = plain_symbol(
            ports=(port("a", 0, 0, N), port("b", 0, 0, E)),
            nodes=(Node(("a", "ghost", "a")), Node(("b", "a"))),
        )
        assert where(port_position_shared(symbol)) == [("port-position-shared", "ports[1]")]

    def test_two_ports_with_one_id_are_one_node_however_declared(self):
        symbol = plain_symbol(ports=(port("a", 0, 0, N), port("a", 0, 0, E)))
        assert port_position_shared(symbol) == ()

    def test_positions_are_compared_exactly(self):
        symbol = plain_symbol(ports=(port("a", 0, 0, N), port("b", 1e-12, 0, E)))
        assert port_position_shared(symbol) == ()

    def test_a_negative_zero_is_the_same_position_as_zero(self):
        symbol = plain_symbol(ports=(port("a", 0, 0, N), port("b", -0.0, 0.0, E)))
        assert where(port_position_shared(symbol)) == [("port-position-shared", "ports[1]")]


class TestGuideExamples:
    ATOMIC = ("S00227", "S00230", "S00305", "S00171")

    @pytest.mark.parametrize("number", ATOMIC)
    @pytest.mark.parametrize("orientation", list(Orientation))
    def test_the_lane_of_every_port_is_clear_in_every_orientation(
        self, library, number, orientation
    ):
        assert port_lane_clear(orient(library.get(number), orientation)) == ()

    @pytest.mark.parametrize("number", ATOMIC)
    def test_lint_finds_nothing_of_the_ports_group(self, library, number):
        assert [f for f in lint(library.get(number)) if f.rule in PORT_RULES] == []


odd = st.sampled_from(
    [math.nan, math.inf, -math.inf, 1e300, -1e300, 1e-300, 0.0, -0.0, 0.125, 1.0, -2.0, 1e6]
)
numbers = st.one_of(st.floats(-8, 8), odd)
points = st.builds(Point, numbers, numbers)
elements = st.one_of(
    st.builds(Line, points, points),
    st.builds(
        Polyline,
        st.lists(points, max_size=4).map(tuple),
        st.booleans(),
        st.sampled_from(list(Fill)),
    ),
    st.builds(Circle, points, numbers, st.sampled_from(list(Fill))),
    st.builds(Arc, points, numbers, numbers, numbers),
    st.builds(Text, st.text(max_size=3), points, numbers),
)
ports = st.builds(Port, st.sampled_from(["a", "b", "in"]), points, st.sampled_from(list(Direction)))
slots = st.builds(
    Slot,
    st.sampled_from(["tag", "m"]),
    points,
    st.sampled_from(list(Direction)),
    st.tuples(numbers, numbers),
)
symbols = st.builds(
    plain_symbol,
    elements=st.lists(elements, max_size=4).map(tuple),
    ports=st.lists(ports, max_size=4).map(tuple),
    slots=st.lists(slots, max_size=3).map(tuple),
    nodes=st.lists(
        st.builds(
            Node, st.lists(st.sampled_from(["a", "b", "in", "ghost"]), max_size=3).map(tuple)
        ),
        max_size=2,
    ).map(tuple),
)


class TestGuideConnectionPoint:
    """S00016 has four ports at one position; the guide exempts two rules and passes the rest."""

    def test_before_its_exemptions_it_fires_exactly_the_two_exempted_ports_rules(self, library):
        raw = replace(library.get("S00016"), lint_allow=())
        assert {f.rule for f in lint(raw) if f.rule in PORT_RULES} == {
            "port-on-body-edge",
            "port-lane-clear",
        }

    @pytest.mark.parametrize(
        "rule_id",
        [
            "port-off-geometry",
            "port-spacing",
            "port-position-shared",
            "port-duplicate-id",
            "port-off-wiring-grid",
        ],
    )
    def test_the_other_ports_rules_pass_on_it(self, library, rule_id):
        assert CHECKS[rule_id](library.get("S00016")) == ()

    def test_with_its_exemptions_no_ports_rule_fires(self, library):
        assert [f for f in lint(library.get("S00016")) if f.rule in PORT_RULES] == []

    def test_both_exempted_rules_fire_on_every_port_it_lists(self, library):
        symbol = library.get("S00016")
        assert len(port_lane_clear(symbol)) == 4
        assert len(port_on_body_edge(symbol)) == 4


class TestSlotsAndElementsInTheLane:
    def test_an_element_in_the_lane_also_pushes_the_body_box_past_the_port(self):
        # the lane is beyond the port, so a body box that contains the element reaches past it:
        # that is why the fixture of port-lane-clear uses a slot box, which the body box ignores
        symbol = plain_symbol(
            ports=(port("in", 0, -2, N),),
            elements=(Line(P(0, -2), P(0, -1)), Line(P(0, -3), P(0, -2.5))),
        )
        assert where(port_lane_clear(symbol)) == [("port-lane-clear", "ports[0]")]
        assert where(port_on_body_edge(symbol)) == [("port-on-body-edge", "ports[0]")]

    def test_a_slot_box_in_the_lane_leaves_the_body_edge_alone(self):
        symbol = plain_symbol(
            ports=(port("in", 0, -2, N),),
            elements=(Line(P(0, -2), P(0, -1)),),
            slots=(slot("marking.in", -0.5, -3, E, (1.5, 1)),),
        )
        assert where(port_lane_clear(symbol)) == [("port-lane-clear", "ports[0]")]
        assert port_on_body_edge(symbol) == ()

    def test_the_message_names_three_offenders_and_counts_the_rest(self):
        symbol = plain_symbol(
            ports=(port("in", 0, -2, N),),
            elements=tuple(Line(P(-1, -3 - i), P(1, -3 - i)) for i in range(5)),
        )
        (found,) = port_lane_clear(symbol)
        assert "elements[0], elements[1], elements[2] and 2 more" in found.message


def grid(low, high):
    return st.integers(low * 2, high * 2).map(lambda n: n / 2)


grid_points = st.builds(Point, grid(-3, 3), grid(-3, 3))
grid_elements = st.one_of(
    st.builds(Line, grid_points, grid_points),
    st.builds(
        Polyline,
        st.lists(grid_points, min_size=1, max_size=5).map(tuple),
        st.booleans(),
        st.sampled_from(list(Fill)),
    ),
    st.builds(Circle, grid_points, grid(1, 2), st.sampled_from(list(Fill))),
    st.builds(
        Arc,
        grid_points,
        grid(1, 2),
        st.sampled_from([0, 90, 180, 270]),
        st.sampled_from([0, 90, 180, 270]),
    ),
    st.builds(Text, st.sampled_from(["", "M", "ABC"]), grid_points, st.sampled_from([0.5, 1])),
)
grid_symbols = st.builds(
    plain_symbol,
    elements=st.lists(grid_elements, max_size=4).map(tuple),
    ports=st.lists(
        st.builds(
            Port, st.sampled_from(["a", "b", "c"]), grid_points, st.sampled_from(list(Direction))
        ),
        max_size=4,
    ).map(tuple),
    nodes=st.sampled_from([(), (Node(("a", "b")),), (Node(("a", "c")), Node(("b",)))]),
)
INVARIANT = (
    "port-duplicate-id",
    "port-off-wiring-grid",
    "port-off-geometry",
    "port-spacing",
    "port-position-shared",
)


class TestOrientationInvariance:
    """The five rules that run once must not change when the whole symbol is oriented."""

    @given(grid_symbols, st.sampled_from(list(Orientation)))
    @settings(max_examples=400, deadline=None)
    def test_the_findings_of_the_invariant_rules_are_the_same_in_every_orientation(
        self, symbol, orientation
    ):
        turned = orient(symbol, orientation)
        for rule_id in INVARIANT:
            check = CHECKS[rule_id]
            assert where(check(turned)) == where(check(symbol)), rule_id

    def test_the_comparison_can_fail_for_a_rule_that_does_depend_on_the_orientation(self):
        symbol = plain_symbol(
            ports=(port("p", 0, -2, N),),
            elements=(Line(P(0, -2), P(0, 0)), Text("ABCDEFGH", P(1, -1), 1)),
        )
        turned = orient(symbol, Orientation.R90)
        assert where(port_on_body_edge(turned)) != where(port_on_body_edge(symbol))


class TestTotalityOfAllRules:
    @given(symbols, st.sampled_from(list(Orientation)))
    @settings(max_examples=400, deadline=None)
    def test_no_ports_rule_raises_for_any_floats(self, symbol, orientation):
        turned = orient(symbol, orientation)
        for rule_id in PORT_RULES:
            found = CHECKS[rule_id](turned)
            assert all(f.rule == rule_id for f in found)

    @given(symbols)
    @settings(max_examples=200, deadline=None)
    def test_lint_never_raises_for_any_floats_and_ports(self, symbol):
        lint(symbol)
