"""Geometry-group rules and the shared point-on-geometry helper."""

import math

import pytest
from build_symbol import plain_symbol

from symdef.geometry import (
    Arc,
    Circle,
    Direction,
    Fill,
    Line,
    Point,
    Polyline,
    Style,
    Text,
)
from symdef.lint.geometry import (
    degenerate,
    off_drawing_grid,
    point_on_geometry,
    text_too_large,
)
from symdef.model import Anchor, Port, Severity, Slot

P = Point


def where(findings):
    return [(f.rule, f.location) for f in findings]


class TestOffDrawingGrid:
    def test_clean_symbol_with_every_kind_of_element(self):
        symbol = plain_symbol(
            elements=(
                Line(P(0, 0), P(-0.375, 1.25)),
                Polyline((P(0, 0), P(0.125, 0.25), P(1e6, -1e6))),
                Circle(P(0.5, 0.5), 0.25),
                Arc(P(0, 0), 1, 10.3, 200.7),
                Text("M", P(0.125, 0.5), 0.75),
            ),
            anchors=(Anchor("a", P(0.125, -0.5), Direction.N),),
            slots=(Slot("tag", P(-1.5, 0), Direction.W, (6, 1)),),
        )
        assert off_drawing_grid(symbol) == ()

    @pytest.mark.parametrize(
        "element",
        [
            Line(P(0, 0), P(0.1, 1)),
            Line(P(0, 0.3), P(1, 1)),
            Line(P(0, 0), P(1, 1.06)),
            Line(P(0.07, 0), P(1, 1)),
            Polyline((P(0, 0), P(1, 1), P(1.1, 2))),
            Polyline((P(0, 0), P(0.2, 1)), closed=True),
            Circle(P(0.1, 0), 1),
            Circle(P(0, 0.1), 1),
            Circle(P(0, 0), 0.3),
            Arc(P(0.1, 0), 1, 0, 90),
            Arc(P(0, 0.1), 1, 0, 90),
            Arc(P(0, 0), 0.3, 0, 90),
            Text("x", P(0.1, 0), 1),
            Text("x", P(0, 0.1), 1),
            Text("x", P(0, 0), 0.3),
        ],
        ids=lambda e: f"{type(e).__name__}-{e!r}"[:60],
    )
    def test_an_element_value_off_the_grid_fires_once_at_the_element(self, element):
        symbol = plain_symbol(elements=(Line(P(0, 0), P(0, 1)), element))
        (found,) = off_drawing_grid(symbol)
        assert (found.rule, found.severity, found.location) == (
            "off-drawing-grid",
            Severity.ERROR,
            "elements[1]",
        )
        assert found.orientation is None

    def test_an_arc_angle_is_not_a_coordinate(self):
        symbol = plain_symbol(elements=(Arc(P(0, 0), 1, 0.1, 33.3),))
        assert off_drawing_grid(symbol) == ()

    def test_one_finding_per_element_names_every_bad_value(self):
        symbol = plain_symbol(elements=(Line(P(0.1, 0), P(1, 0.3)),))
        (found,) = off_drawing_grid(symbol)
        assert "start.x 0.1" in found.message
        assert "end.y 0.3" in found.message
        assert "0.125" in found.message

    def test_locations_are_the_element_positions(self):
        symbol = plain_symbol(
            elements=(Circle(P(0, 0), 0.3), Line(P(0, 0), P(0, 1)), Circle(P(0, 0), 0.7))
        )
        assert where(off_drawing_grid(symbol)) == [
            ("off-drawing-grid", "elements[0]"),
            ("off-drawing-grid", "elements[2]"),
        ]

    def test_an_anchor_off_the_grid_fires_at_the_anchor(self):
        symbol = plain_symbol(
            anchors=(Anchor("a", P(0, 0), Direction.N), Anchor("b", P(0.1, 0), Direction.N))
        )
        assert where(off_drawing_grid(symbol)) == [("off-drawing-grid", "anchors[1]")]

    @pytest.mark.parametrize(
        "slot",
        [
            Slot("tag", P(0.1, 0), Direction.W, (6, 1)),
            Slot("tag", P(0, 0.1), Direction.W, (6, 1)),
            Slot("tag", P(0, 0), Direction.W, (6.1, 1)),
            Slot("tag", P(0, 0), Direction.W, (6, 1.1)),
        ],
    )
    def test_a_slot_point_or_box_size_off_the_grid_fires_at_the_slot(self, slot):
        assert where(off_drawing_grid(plain_symbol(slots=(slot,)))) == [
            ("off-drawing-grid", "slots.tag")
        ]

    def test_a_port_position_is_not_this_rules_business(self):
        symbol = plain_symbol(ports=(Port("in", P(0.3, 0.7), Direction.N),))
        assert off_drawing_grid(symbol) == ()

    def test_the_check_is_exact_not_approximate(self):
        symbol = plain_symbol(elements=(Line(P(0, 0), P(0.125 + 1e-12, 1)),))
        assert len(off_drawing_grid(symbol)) == 1

    @pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 0.1 + 0.2])
    def test_odd_floats_are_off_the_grid_and_never_raise(self, value):
        symbol = plain_symbol(elements=(Circle(P(value, 0), 1),))
        assert len(off_drawing_grid(symbol)) == 1


class TestDegenerate:
    def test_clean_symbol(self):
        symbol = plain_symbol(
            elements=(
                Line(P(0, 0), P(0, 1)),
                Polyline((P(0, 0), P(1, 0))),
                Polyline((P(0, 0), P(1, 0), P(1, 1)), closed=True),
                Circle(P(0, 0), 0.125),
                Arc(P(0, 0), 1, 0, 90),
            ),
            slots=(Slot("tag", P(0, 0), Direction.W, (6, 1)),),
        )
        assert degenerate(symbol) == ()

    @pytest.mark.parametrize(
        "element",
        [
            Line(P(1, 1), P(1, 1)),
            Circle(P(0, 0), 0),
            Circle(P(0, 0), -1),
            Arc(P(0, 0), 0, 0, 90),
            Arc(P(0, 0), -1, 0, 90),
            Polyline(()),
            Polyline((P(0, 0),)),
            Polyline((P(0, 0), P(1, 0)), closed=True),
            Polyline((P(0, 0),), closed=True),
            Arc(P(0, 0), 1, 90, 90),
            Arc(P(0, 0), 1, 0, 360),
            Arc(P(0, 0), 1, -90, 270),
            Arc(P(0, 0), 1, 725, 5),
        ],
        ids=lambda e: f"{type(e).__name__}-{e!r}"[:70],
    )
    def test_each_degenerate_element_fires_at_the_element(self, element):
        symbol = plain_symbol(elements=(Line(P(0, 0), P(0, 1)), element))
        (found,) = degenerate(symbol)
        assert (found.rule, found.severity, found.location) == (
            "degenerate",
            Severity.ERROR,
            "elements[1]",
        )

    def test_an_exact_duplicate_fires_at_the_later_copy(self):
        symbol = plain_symbol(
            elements=(Line(P(0, 0), P(0, 1)), Circle(P(0, 0), 1), Line(P(0, 0), P(0, 1)))
        )
        (found,) = degenerate(symbol)
        assert found.location == "elements[2]"
        assert "elements[0]" in found.message

    def test_three_copies_give_two_findings_against_the_first(self):
        line = Line(P(0, 0), P(0, 1))
        found = degenerate(plain_symbol(elements=(line, line, line)))
        assert [f.location for f in found] == ["elements[1]", "elements[2]"]
        assert all("elements[0]" in f.message for f in found)

    def test_reversed_or_restyled_lines_are_not_duplicates(self):
        symbol = plain_symbol(
            elements=(
                Line(P(0, 0), P(0, 1)),
                Line(P(0, 1), P(0, 0)),
                Line(P(0, 0), P(0, 1), style=Style.DASHED),
            )
        )
        assert degenerate(symbol) == ()

    def test_a_degenerate_duplicate_is_reported_for_both_reasons(self):
        zero = Line(P(1, 1), P(1, 1))
        found = degenerate(plain_symbol(elements=(zero, zero)))
        assert [f.location for f in found] == ["elements[0]", "elements[1]", "elements[1]"]

    @pytest.mark.parametrize("box", [(0, 1), (1, 0), (-1, 1), (1, -2), (0, 0)])
    def test_a_slot_box_with_a_non_positive_side_fires_at_the_slot(self, box):
        symbol = plain_symbol(slots=(Slot("tag", P(0, 0), Direction.W, box),))
        (found,) = degenerate(symbol)
        assert (found.rule, found.location) == ("degenerate", "slots.tag")

    def test_text_is_never_degenerate(self):
        assert degenerate(plain_symbol(elements=(Text("", P(0, 0), 0),))) == ()

    @pytest.mark.parametrize("angle", [math.nan, math.inf, -math.inf])
    def test_odd_arc_angles_never_raise(self, angle):
        degenerate(plain_symbol(elements=(Arc(P(0, 0), 1, angle, 90),)))


class TestTextTooLarge:
    def test_one_module_is_the_limit(self):
        symbol = plain_symbol(elements=(Text("M", P(0, 0), 1), Text("M", P(0, 0), 0.5)))
        assert text_too_large(symbol) == ()

    def test_taller_than_one_fires_at_the_text(self):
        symbol = plain_symbol(elements=(Line(P(0, 0), P(0, 1)), Text("M", P(0, 0), 1.125)))
        (found,) = text_too_large(symbol)
        assert (found.rule, found.severity, found.location) == (
            "text-too-large",
            Severity.ERROR,
            "elements[1]",
        )
        assert "1.125" in found.message

    def test_other_elements_are_ignored(self):
        symbol = plain_symbol(elements=(Circle(P(0, 0), 50), Line(P(0, 0), P(0, 99))))
        assert text_too_large(symbol) == ()


def on(point, *elements, **options):
    return point_on_geometry(point, elements, **options)


class TestPointOnGeometry:
    def test_no_elements(self):
        assert not on(P(0, 0))

    def test_a_line_segment_including_its_ends(self):
        line = Line(P(0, 0), P(2, 0))
        assert on(P(0, 0), line)
        assert on(P(1, 0), line)
        assert on(P(2, 0), line)
        assert not on(P(3, 0), line)
        assert not on(P(-1e-6, 0), line)
        assert not on(P(1, 0.001), line)

    def test_the_tolerance_is_1e_9(self):
        line = Line(P(0, 0), P(2, 0))
        assert on(P(1, 5e-10), line)
        assert not on(P(1, 2e-9), line)

    def test_a_zero_length_line_is_its_point(self):
        line = Line(P(1, 1), P(1, 1))
        assert on(P(1, 1), line)
        assert not on(P(1, 2), line)

    def test_polyline_segments_and_the_closing_segment(self):
        chain = Polyline((P(0, 0), P(2, 0), P(2, 2)))
        assert on(P(1, 0), chain)
        assert on(P(2, 1), chain)
        assert not on(P(1, 1), chain)
        closed = Polyline((P(0, 0), P(2, 0), P(2, 2)), closed=True)
        assert on(P(1, 1), closed)
        assert not on(P(0.5, 1.5), closed)
        assert not on(P(1, 0.5), closed)

    def test_a_filled_closed_polyline_is_its_area(self):
        square = Polyline((P(0, 0), P(2, 0), P(2, 2), P(0, 2)), closed=True, fill=Fill.SOLID)
        assert on(P(1, 1), square)
        assert on(P(0.1, 1.9), square)
        assert on(P(0, 1), square)
        assert not on(P(3, 1), square)
        assert not on(P(1, -0.5), square)

    def test_a_filled_open_polyline_is_only_its_line(self):
        chain = Polyline((P(0, 0), P(2, 0), P(2, 2), P(0, 2)), fill=Fill.SOLID)
        assert not on(P(1, 1), chain)
        assert on(P(1, 0), chain)

    def test_a_single_point_polyline_is_its_point(self):
        assert on(P(1, 1), Polyline((P(1, 1),)))
        assert not on(P(1, 1), Polyline(()))

    def test_a_circle_is_its_circumference_and_a_filled_one_its_disk(self):
        ring = Circle(P(0, 0), 2)
        assert on(P(2, 0), ring)
        assert on(P(0, -2), ring)
        assert on(P(math.sqrt(2), math.sqrt(2)), ring)
        assert not on(P(0, 0), ring)
        assert not on(P(1, 0), ring)
        disk = Circle(P(0, 0), 2, fill=Fill.SOLID)
        assert on(P(0, 0), disk)
        assert on(P(1, 1), disk)
        assert on(P(2, 0), disk)
        assert not on(P(2.1, 0), disk)

    def test_an_arc_is_only_its_swept_curve(self):
        arc = Arc(P(0, 0), 2, 0, 90)
        assert on(P(2, 0), arc)
        assert on(P(0, 2), arc)
        assert on(P(math.sqrt(2), math.sqrt(2)), arc)
        assert not on(P(0, -2), arc)
        assert not on(P(-2, 0), arc)
        assert not on(P(1, 0), arc)

    def test_an_arc_that_wraps_through_zero(self):
        arc = Arc(P(0, 0), 1, 270, 90)
        assert on(P(1, 0), arc)
        assert on(P(0, -1), arc)
        assert on(P(0, 1), arc)
        assert not on(P(-1, 0), arc)

    def test_an_arc_end_at_a_non_axis_angle_counts(self):
        arc = Arc(P(1, 1), 2, 30, 100)
        for angle in (30, 100):
            r = math.radians(angle)
            assert on(P(1 + 2 * math.cos(r), 1 + 2 * math.sin(r)), arc)

    def test_just_outside_an_arc_end_is_off(self):
        arc = Arc(P(0, 0), 2, 0, 90)
        r = math.radians(-1)
        assert not on(P(2 * math.cos(r), 2 * math.sin(r)), arc)

    def test_a_full_circle_arc(self):
        assert on(P(-1, 0), Arc(P(0, 0), 1, 5, 5))

    def test_text_is_not_geometry(self):
        assert not on(P(0, 0), Text("M", P(0, 0), 1))

    def test_any_element_will_do(self):
        assert on(P(5, 5), Line(P(0, 0), P(1, 1)), Circle(P(5, 5), 1, fill=Fill.SOLID))

    def test_endpoints_only_takes_the_ends_of_lines_and_open_polylines(self):
        line = Line(P(0, 0), P(2, 0))
        assert on(P(0, 0), line, endpoints_only=True)
        assert on(P(2, 0), line, endpoints_only=True)
        assert not on(P(1, 0), line, endpoints_only=True)
        chain = Polyline((P(0, 0), P(2, 0), P(2, 2)))
        assert on(P(0, 0), chain, endpoints_only=True)
        assert on(P(2, 2), chain, endpoints_only=True)
        assert not on(P(2, 0), chain, endpoints_only=True)
        assert not on(P(1, 0), chain, endpoints_only=True)
        assert not on(P(1, 1), Polyline(()), endpoints_only=True)

    def test_endpoints_only_leaves_circles_arcs_and_closed_outlines_whole(self):
        assert on(P(2, 0), Circle(P(0, 0), 2), endpoints_only=True)
        assert on(P(0, 0), Circle(P(0, 0), 2, fill=Fill.SOLID), endpoints_only=True)
        assert on(P(0, 2), Arc(P(0, 0), 2, 0, 90), endpoints_only=True)
        closed = Polyline((P(0, 0), P(2, 0), P(2, 2)), closed=True)
        assert on(P(1, 1), closed, endpoints_only=True)
        assert on(P(1, 0), closed, endpoints_only=True)

    @pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 1e300])
    def test_odd_floats_never_raise(self, value):
        elements = (
            Line(P(0, 0), P(value, 1)),
            Polyline((P(0, 0), P(value, 1), P(1, value)), closed=True, fill=Fill.SOLID),
            Circle(P(value, 0), value, fill=Fill.SOLID),
            Arc(P(0, 0), value, value, 90),
            Arc(P(0, 0), 1, 0, value),
        )
        point_on_geometry(P(value, 0), elements)
        point_on_geometry(P(0, 0), elements, endpoints_only=True)
