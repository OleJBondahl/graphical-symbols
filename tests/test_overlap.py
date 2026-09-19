"""Overlap of a shape or a box with an open rectangle: touching is not overlap."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from graphical_symbols.geometry import (
    Arc,
    Box,
    Circle,
    Direction,
    Fill,
    Line,
    Point,
    Polyline,
    Text,
    arc_point,
)
from graphical_symbols.lint.overlap import boxes_overlap, overlaps_rect, wire_lane

P = Point
SOLID = Fill.SOLID


def rect(x0, y0, x1, y1):
    return Box(P(x0, y0), P(x1, y1))


def square(x0, y0, x1, y1, *, fill=Fill.NONE):
    """A closed rectangle outline, optionally filled."""
    return Polyline((P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)), closed=True, fill=fill)


R = rect(0, 0, 1, 1)


class TestBoxesOverlap:
    def test_crossing_boxes_overlap(self):
        assert boxes_overlap(rect(0, 0, 2, 2), rect(1, 1, 3, 3))

    def test_a_box_inside_another_overlaps_it(self):
        assert boxes_overlap(rect(0, 0, 4, 4), rect(1, 1, 2, 2))
        assert boxes_overlap(rect(1, 1, 2, 2), rect(0, 0, 4, 4))

    def test_a_cross_shape_overlaps_with_no_corner_inside_the_other(self):
        assert boxes_overlap(rect(0, 1, 3, 2), rect(1, 0, 2, 3))

    @pytest.mark.parametrize(
        "other",
        [
            rect(1, 0, 2, 1),
            rect(-1, 0, 0, 1),
            rect(0, 1, 1, 2),
            rect(0, -1, 1, 0),
            rect(1, 1, 2, 2),
            rect(-1, -1, 0, 0),
            rect(1, 0.25, 2, 0.75),
        ],
    )
    def test_touching_along_an_edge_or_at_a_corner_is_not_overlap(self, other):
        assert not boxes_overlap(R, other)
        assert not boxes_overlap(other, R)

    def test_moving_a_touching_box_inward_by_one_grid_step_makes_it_overlap(self):
        assert not boxes_overlap(R, rect(1, 0, 2, 1))
        assert boxes_overlap(R, rect(0.875, 0, 2, 1))

    def test_disjoint_boxes_do_not_overlap(self):
        assert not boxes_overlap(R, rect(2, 2, 3, 3))

    def test_a_box_with_no_area_overlaps_nothing(self):
        assert not boxes_overlap(rect(0.5, 0, 0.5, 1), R)
        assert not boxes_overlap(R, rect(0.5, 0.5, 0.5, 0.5))


class TestOpenRectangle:
    """An open rectangle with no area (zero, negative or NaN width or height) is empty."""

    @pytest.mark.parametrize(
        "empty",
        [rect(0, 0, 0, 1), rect(0, 0, 1, 0), rect(1, 1, 0, 0), rect(0, 0, math.nan, 1)],
    )
    def test_nothing_overlaps_an_empty_rectangle(self, empty):
        assert not overlaps_rect(Line(P(-1, 0.5), P(2, 0.5)), empty)
        assert not overlaps_rect(Circle(P(0.5, 0.5), 5, SOLID), empty)
        assert not overlaps_rect(square(-1, -1, 2, 2, fill=SOLID), empty)
        assert not overlaps_rect(Text("ABC", P(0.5, 0.5), 3), empty)


class TestLine:
    def test_a_line_through_the_rectangle_overlaps(self):
        assert overlaps_rect(Line(P(-1, 0.5), P(2, 0.5)), R)
        assert overlaps_rect(Line(P(0.5, -1), P(0.5, 2)), R)

    def test_a_line_that_ends_inside_overlaps(self):
        assert overlaps_rect(Line(P(0.5, 0.5), P(5, 5)), R)
        assert overlaps_rect(Line(P(5, 5), P(0.5, 0.5)), R)

    def test_a_line_inside_overlaps(self):
        assert overlaps_rect(Line(P(0.25, 0.25), P(0.75, 0.5)), R)

    def test_a_diagonal_through_two_corners_overlaps(self):
        assert overlaps_rect(Line(P(-1, -1), P(2, 2)), R)

    def test_a_line_that_cuts_a_corner_overlaps(self):
        assert overlaps_rect(Line(P(-1, 0.5), P(0.5, -1)), rect(-1, -1, 0, 0))
        assert overlaps_rect(Line(P(-1, 1.125), P(2, -1.875)), R)

    @pytest.mark.parametrize(
        "line",
        [
            Line(P(1, 0.5), P(2, 0.5)),
            Line(P(-1, 0.5), P(0, 0.5)),
            Line(P(0.5, 1), P(0.5, 2)),
            Line(P(0.5, -1), P(0.5, 0)),
            Line(P(1, 1), P(2, 2)),
            Line(P(-1, -1), P(0, 0)),
            Line(P(0, -1), P(0, 2)),
            Line(P(1, -1), P(1, 2)),
            Line(P(-1, 0), P(2, 0)),
            Line(P(-1, 1), P(2, 1)),
            Line(P(0, 0), P(0, 1)),
            Line(P(0, 0), P(1, 0)),
            Line(P(1, 0), P(1, 1)),
            Line(P(-1, 1), P(2, -2)),
            Line(P(2, 1), P(-1, -2)),
            Line(P(-2, 1), P(1, 4)),
        ],
        ids=lambda line: f"{line.start.x},{line.start.y}->{line.end.x},{line.end.y}",
    )
    def test_touching_the_boundary_is_not_overlap(self, line):
        assert not overlaps_rect(line, R)

    def test_a_line_along_an_edge_or_touching_a_corner_is_not_overlap_but_nudged_it_is(self):
        touching = Line(P(-1, 1), P(2, -2))  # meets the rectangle only at the corner (0, 0)
        assert not overlaps_rect(touching, R)
        assert overlaps_rect(Line(P(-1, 1.125), P(2, -1.875)), R)
        assert not overlaps_rect(Line(P(-1, 0), P(2, 0)), R)
        assert overlaps_rect(Line(P(-1, 0.125), P(2, 0.125)), R)

    def test_a_line_that_stops_short_or_starts_past_does_not_overlap(self):
        assert not overlaps_rect(Line(P(-2, 0.5), P(-0.5, 0.5)), R)
        assert not overlaps_rect(Line(P(1.5, 0.5), P(3, 0.5)), R)
        assert not overlaps_rect(Line(P(-2, -2), P(-0.5, -0.5)), R)

    def test_a_line_that_stops_exactly_on_the_edge_from_outside_is_not_overlap(self):
        assert not overlaps_rect(Line(P(-2, 0.5), P(0, 0.5)), R)
        assert overlaps_rect(Line(P(-2, 0.5), P(0.125, 0.5)), R)

    def test_a_line_that_starts_on_an_edge_and_leaves_is_not_overlap(self):
        assert not overlaps_rect(Line(P(1, 0.5), P(3, 0.5)), R)
        assert overlaps_rect(Line(P(0.875, 0.5), P(3, 0.5)), R)

    def test_a_line_with_no_length_overlaps_only_when_its_point_is_inside(self):
        assert overlaps_rect(Line(P(0.5, 0.5), P(0.5, 0.5)), R)
        assert not overlaps_rect(Line(P(0, 0.5), P(0, 0.5)), R)
        assert not overlaps_rect(Line(P(2, 2), P(2, 2)), R)

    def test_an_inexact_slope_is_still_exact_at_the_boundary(self):
        # the crossing parameters are thirds, which are not binary fractions
        diagonal = Line(P(-1, 1), P(2, -2))  # through the corner (0, 0) at t = 1/3
        assert not overlaps_rect(diagonal, rect(0, 0, 3, 3))
        assert not overlaps_rect(diagonal, R)
        assert overlaps_rect(diagonal, rect(0, -1, 3, 3))
        seventh = Line(P(-1, 5), P(6, -2))  # meets the corner (2, 2) at t = 3/7
        assert not overlaps_rect(seventh, rect(0, 0, 2, 2))
        assert overlaps_rect(seventh, rect(0, 0, 2.125, 2))


class TestPolyline:
    def test_an_open_polyline_is_its_segments(self):
        chain = Polyline((P(-1, -1), P(-1, 0.5), P(2, 0.5)))
        assert overlaps_rect(chain, R)

    def test_an_open_polyline_does_not_close_itself(self):
        chain = (P(0, 0), P(2, 0), P(2, 2))
        middle = rect(0.75, 0.75, 1.25, 1.25)  # the closing diagonal runs through it
        assert not overlaps_rect(Polyline(chain), middle)
        assert overlaps_rect(Polyline(chain, closed=True), middle)

    def test_an_open_polyline_that_wraps_the_rectangle_without_touching_does_not_overlap(self):
        wrap = Polyline((P(-1, 2), P(-1, -1), P(2, -1), P(2, 2)))
        assert not overlaps_rect(wrap, R)

    def test_the_fill_of_an_open_polyline_is_ignored(self):
        open_u = Polyline((P(0, 0), P(4, 0), P(4, 4), P(0, 4)), fill=SOLID)
        assert not overlaps_rect(open_u, rect(1, 1, 3, 3))
        assert overlaps_rect(open_u, rect(3, 1, 5, 3))

    def test_a_closed_unfilled_outline_is_only_its_outline(self):
        outline = square(0, 0, 4, 4)
        assert not overlaps_rect(outline, rect(1, 1, 3, 3))
        assert overlaps_rect(outline, rect(3, 1, 5, 3))
        assert overlaps_rect(outline, rect(-1, 1, 1, 3))
        assert overlaps_rect(outline, rect(1, -1, 3, 1))
        assert overlaps_rect(outline, rect(1, 3, 3, 5))

    def test_a_slot_inside_an_empty_body_rectangle_does_not_overlap_it(self):
        assert not overlaps_rect(square(-2, -1, 2, 1), rect(-1.5, -0.5, 0, 0.5))

    def test_a_slot_that_only_touches_the_inside_of_the_outline_is_not_overlap(self):
        assert not overlaps_rect(square(-2, -1, 2, 1), rect(-1.5, -1, 0, 0))

    def test_a_closed_filled_outline_is_its_area(self):
        assert overlaps_rect(square(0, 0, 4, 4, fill=SOLID), rect(1, 1, 3, 3))
        assert overlaps_rect(square(0, 0, 4, 4, fill=SOLID), rect(3, 1, 5, 3))
        assert overlaps_rect(square(0, 0, 4, 4, fill=SOLID), rect(-5, -5, 9, 9))

    def test_a_closed_filled_outline_does_not_overlap_a_box_outside_or_touching(self):
        filled = square(0, 0, 4, 4, fill=SOLID)
        assert not overlaps_rect(filled, rect(5, 0, 6, 4))
        assert not overlaps_rect(filled, rect(4, 0, 6, 4))
        assert not overlaps_rect(filled, rect(4, 4, 6, 6))
        assert overlaps_rect(filled, rect(3.875, 0, 6, 4))

    def test_a_concave_polygon_does_not_fill_its_notch(self):
        ell = Polyline(
            (P(0, 0), P(4, 0), P(4, 1), P(1, 1), P(1, 4), P(0, 4)), closed=True, fill=SOLID
        )
        assert not overlaps_rect(ell, rect(2, 2, 3, 3))
        assert overlaps_rect(ell, rect(2, 0.25, 3, 0.75))
        assert overlaps_rect(ell, rect(0.25, 2, 0.75, 3))
        assert overlaps_rect(ell, rect(0.25, 0.25, 0.75, 0.75))
        assert overlaps_rect(ell, rect(0.5, 0.5, 2, 2))
        assert not overlaps_rect(ell, rect(1, 1, 4, 4))
        assert overlaps_rect(ell, rect(0.875, 1, 4, 4))

    def test_a_box_beside_a_filled_u_shape_is_not_inside_it(self):
        # a ray from the box crosses four edges of the U, an even number, so it is outside
        u_shape = Polyline(
            (P(0, 0), P(1, 0), P(1, 3), P(3, 3), P(3, 0), P(4, 0), P(4, 4), P(0, 4)),
            closed=True,
            fill=SOLID,
        )
        assert not overlaps_rect(u_shape, rect(-3, 1, -1, 2))
        assert not overlaps_rect(u_shape, rect(1.25, 0.25, 2.75, 2.75))
        assert overlaps_rect(u_shape, rect(1.25, 3.25, 2.75, 3.75))

    def test_a_filled_triangle_covers_by_area_and_not_by_bounding_box(self):
        triangle = Polyline((P(0, 0), P(4, 0), P(0, 4)), closed=True, fill=SOLID)
        assert overlaps_rect(triangle, rect(0.5, 0.5, 1, 1))
        assert not overlaps_rect(triangle, rect(3, 3, 4, 4))
        assert not overlaps_rect(triangle, rect(2, 2, 3, 3))
        assert overlaps_rect(triangle, rect(1.5, 1.5, 3, 3))

    def test_a_filled_outline_with_fewer_than_three_points_has_no_area(self):
        segment = Polyline((P(0, 0), P(4, 0)), closed=True, fill=SOLID)
        assert not overlaps_rect(segment, rect(1, 1, 3, 3))
        assert overlaps_rect(segment, rect(1, -1, 3, 1))

    def test_a_polyline_of_one_point_is_a_dot_and_of_none_is_nothing(self):
        assert overlaps_rect(Polyline((P(0.5, 0.5),)), R)
        assert not overlaps_rect(Polyline((P(1, 0.5),)), R)
        assert not overlaps_rect(Polyline(()), R)
        assert not overlaps_rect(Polyline((), closed=True, fill=SOLID), R)


class TestCircle:
    def test_an_outline_crossing_the_rectangle_overlaps(self):
        assert overlaps_rect(Circle(P(0, 0), 1), rect(0.5, -0.25, 2, 0.25))

    def test_an_outline_around_the_rectangle_does_not_overlap_it(self):
        assert not overlaps_rect(Circle(P(0, 0), 5), rect(-1, -1, 1, 1))

    def test_a_rectangle_around_the_circle_overlaps_its_outline(self):
        assert overlaps_rect(Circle(P(0, 0), 1), rect(-2, -2, 2, 2))

    def test_a_filled_circle_is_its_disk(self):
        assert overlaps_rect(Circle(P(0, 0), 5, SOLID), rect(-1, -1, 1, 1))
        assert overlaps_rect(Circle(P(0, 0), 1, SOLID), rect(-2, -2, 2, 2))
        assert overlaps_rect(Circle(P(0, 0), 1, SOLID), rect(0.5, -0.25, 2, 0.25))
        assert not overlaps_rect(Circle(P(0, 0), 1, SOLID), rect(2, 2, 3, 3))

    def test_an_outline_far_from_the_rectangle_does_not_overlap(self):
        assert not overlaps_rect(Circle(P(0, 0), 1), rect(2, 2, 3, 3))

    @pytest.mark.parametrize("fill", list(Fill))
    def test_a_circle_touching_an_edge_from_outside_is_not_overlap(self, fill):
        assert not overlaps_rect(Circle(P(0, 0), 1, fill), rect(1, -1, 2, 1))
        assert not overlaps_rect(Circle(P(0, 0), 1, fill), rect(-2, -1, -1, 1))
        assert not overlaps_rect(Circle(P(0, 0), 1, fill), rect(-1, 1, 1, 2))
        assert not overlaps_rect(Circle(P(0, 0), 1, fill), rect(-1, -2, 1, -1))

    @pytest.mark.parametrize("fill", list(Fill))
    def test_a_circle_touching_a_corner_from_outside_is_not_overlap(self, fill):
        # the corner (3, 4) is at distance 5
        assert not overlaps_rect(Circle(P(0, 0), 5, fill), rect(3, 4, 6, 8))

    def test_a_circle_touching_a_corner_from_inside_is_not_an_outline_overlap(self):
        assert not overlaps_rect(Circle(P(0, 0), 5), rect(0, 0, 3, 4))
        assert overlaps_rect(Circle(P(0, 0), 5, SOLID), rect(0, 0, 3, 4))
        assert overlaps_rect(Circle(P(0, 0), 5), rect(0, 0, 3.125, 4))

    def test_moving_a_touching_rectangle_inward_by_one_grid_step_makes_it_overlap(self):
        assert not overlaps_rect(Circle(P(0, 0), 1), rect(1, -1, 2, 1))
        assert overlaps_rect(Circle(P(0, 0), 1), rect(0.875, -1, 2, 1))
        assert not overlaps_rect(Circle(P(0, 0), 1, SOLID), rect(1, -1, 2, 1))
        assert overlaps_rect(Circle(P(0, 0), 1, SOLID), rect(0.875, -1, 2, 1))

    def test_a_small_circle_inside_the_rectangle_overlaps_whether_filled_or_not(self):
        assert overlaps_rect(Circle(P(0.5, 0.5), 0.125, SOLID), R)
        assert overlaps_rect(Circle(P(0.5, 0.5), 0.125), R)

    def test_a_rectangle_inside_an_empty_circle_does_not_overlap_it_but_does_a_filled_one(self):
        assert not overlaps_rect(Circle(P(0.5, 0.5), 5), R)
        assert overlaps_rect(Circle(P(0.5, 0.5), 5, SOLID), R)

    @pytest.mark.parametrize("radius", [0, -1, math.nan])
    def test_a_circle_without_a_positive_radius_draws_nothing(self, radius):
        assert not overlaps_rect(Circle(P(0.5, 0.5), radius, SOLID), R)
        assert not overlaps_rect(Circle(P(0.5, 0.5), radius), R)


class TestArc:
    def test_an_arc_through_the_rectangle_overlaps(self):
        # the point at 30 degrees on the circle of radius 2 is (1.732, 1)
        assert overlaps_rect(Arc(P(0, 0), 2, 0, 90), rect(1.5, 0.5, 2.5, 1.5))

    def test_the_extent_box_can_overlap_where_the_curve_does_not(self):
        arc = Arc(P(0, 0), 2, 0, 90)  # its extent box is (0, 0) to (2, 2)
        assert not overlaps_rect(arc, rect(0.25, 0.25, 1, 1))
        assert not overlaps_rect(arc, rect(1.5, 1.5, 2, 2))

    def test_the_swept_range_is_respected(self):
        upper_left = Arc(P(0, 0), 2, 180, 270)
        assert not overlaps_rect(upper_left, rect(1.5, -0.5, 2.5, 0.5))
        assert not overlaps_rect(upper_left, rect(-2.5, 0, -1.5, 1))
        assert overlaps_rect(upper_left, rect(-2.5, -1.5, -1.5, -0.5))

    def test_the_arc_runs_clockwise_on_screen_from_start_to_end(self):
        # from 0 to 90 the point moves from (2, 0) down (y grows) to (0, 2)
        assert overlaps_rect(Arc(P(0, 0), 2, 0, 90), rect(1, 1, 2, 2))
        assert not overlaps_rect(Arc(P(0, 0), 2, 0, 90), rect(1, -2, 2, -1))
        assert overlaps_rect(Arc(P(0, 0), 2, 270, 90), rect(1, -2, 2, -1))

    def test_an_arc_that_crosses_angle_zero(self):
        assert overlaps_rect(Arc(P(0, 0), 2, 350, 10), rect(1.5, -0.25, 2.5, 0.25))
        assert not overlaps_rect(Arc(P(0, 0), 2, 350, 10), rect(-2.5, -0.25, -1.5, 0.25))
        assert overlaps_rect(Arc(P(0, 0), 2, 10, 350), rect(-2.5, -0.25, -1.5, 0.25))
        assert not overlaps_rect(Arc(P(0, 0), 2, 10, 350), rect(1.5, -0.25, 2.5, 0.25))

    def test_an_arc_that_only_touches_the_rectangle_at_its_end_is_not_overlap(self):
        arc = Arc(P(0, 0), 2, 0, 90)
        assert not overlaps_rect(arc, rect(2, -1, 3, 1))
        assert not overlaps_rect(arc, rect(1, -1, 3, 0))
        assert not overlaps_rect(arc, rect(-1, 2, 1, 3))
        assert not overlaps_rect(arc, rect(0, 2, 1, 3))

    def test_moving_a_touching_rectangle_inward_makes_the_arc_overlap(self):
        arc = Arc(P(0, 0), 2, 0, 90)
        assert not overlaps_rect(arc, rect(2, -1, 3, 1))
        assert overlaps_rect(arc, rect(1.875, -1, 3, 1))
        assert not overlaps_rect(arc, rect(1, -1, 3, 0))
        assert overlaps_rect(arc, rect(1, -1, 3, 0.125))

    def test_an_arc_that_touches_a_rectangle_tangentially_is_not_overlap(self):
        right_half = Arc(P(0, 0), 2, 270, 90)
        assert not overlaps_rect(right_half, rect(2, -1, 3, 1))
        assert not overlaps_rect(right_half, rect(-1, 2, 1, 3))
        assert overlaps_rect(right_half, rect(1.875, -1, 3, 1))

    def test_an_arc_inside_the_rectangle_overlaps(self):
        assert overlaps_rect(Arc(P(0, 0), 1, 0, 90), rect(-3, -3, 3, 3))
        assert overlaps_rect(Arc(P(0, 0), 1, 30, 40), rect(-3, -3, 3, 3))

    def test_an_arc_that_touches_at_a_corner_is_not_overlap(self):
        # the circle of radius 5 passes through (3, 4) and (4, 3)
        assert not overlaps_rect(Arc(P(0, 0), 5, 0, 90), rect(3, 4, 6, 8))
        assert not overlaps_rect(Arc(P(0, 0), 5, 0, 90), rect(0, 0, 3, 4))
        assert overlaps_rect(Arc(P(0, 0), 5, 0, 90), rect(0, 0, 3.125, 4))

    def test_an_arc_that_grazes_an_edge_by_less_than_the_tolerance_is_touching(self):
        near = 1e-10
        assert not overlaps_rect(Arc(P(0, 0), 2, 270, 90), rect(2 - near, -1, 3, 1))
        assert not overlaps_rect(Arc(P(0, 0), 2, 90, 270), rect(-3, -1, -2 + near, 1))
        assert not overlaps_rect(Arc(P(0, 0), 2, 0, 180), rect(-1, 2 - near, 1, 3))
        assert overlaps_rect(Arc(P(0, 0), 2, 270, 90), rect(2 - 1e-6, -1, 3, 1))

    def test_equal_angles_are_a_full_circle(self):
        assert overlaps_rect(Arc(P(0, 0), 2, 30, 30), rect(-2.5, -0.25, -1.5, 0.25))

    def test_angles_beyond_a_turn_are_reduced(self):
        assert overlaps_rect(Arc(P(0, 0), 2, 720, 810), rect(1, 1, 2, 2))
        assert overlaps_rect(Arc(P(0, 0), 2, -90, 90), rect(1, -2, 2, -1))

    @pytest.mark.parametrize("radius", [0, -1, math.nan])
    def test_an_arc_without_a_positive_radius_draws_nothing(self, radius):
        assert not overlaps_rect(Arc(P(0.5, 0.5), radius, 0, 90), R)


class TestText:
    def test_text_counts_as_a_box_centred_on_its_position(self):
        assert overlaps_rect(Text("ABC", P(0, 0), 1), rect(0.5, -0.25, 2, 0.25))
        assert not overlaps_rect(Text("ABC", P(0, 0), 1), rect(1, -0.25, 2, 0.25))

    def test_text_that_only_touches_the_rectangle_is_not_overlap(self):
        # "ABCDE" at height 1 is 3 M wide, so its edges are at x = -1.5 and 1.5, y = -0.5 and 0.5
        assert not overlaps_rect(Text("ABCDE", P(0, 0), 1), rect(1.5, -1, 3, 1))
        assert not overlaps_rect(Text("ABCDE", P(0, 0), 1), rect(-1, 0.5, 1, 3))
        assert overlaps_rect(Text("ABCDE", P(0, 0), 1), rect(1.375, -1, 3, 1))
        assert overlaps_rect(Text("ABCDE", P(0, 0), 1), rect(-1, 0.375, 1, 3))

    def test_text_touching_by_the_inexact_width_is_still_only_touching(self):
        # three characters at height 1 are 1.8 M wide; 0.6 is not a binary fraction, so the
        # computed edge is 0.8999999999999999 and a rectangle starting at 0.9 must still touch
        assert not overlaps_rect(Text("ABC", P(0, 0), 1), rect(0.9, -1, 2, 1))
        assert overlaps_rect(Text("ABC", P(0, 0), 1), rect(0.899, -1, 2, 1))

    def test_text_whose_computed_edge_lands_a_rounding_step_beyond_the_true_one_only_touches(self):
        # three characters at height 0.875 are exactly 1.575 M wide; 0.6 * 0.875 * 3 / 2 is
        # 0.7875000000000001 in floating point, so without the tolerance this would overlap
        assert 0.6 * 0.875 * 3 / 2 > 0.7875
        assert not overlaps_rect(Text("ABC", P(0, 0), 0.875), rect(0.7875, -1, 2, 1))
        assert not overlaps_rect(Text("ABC", P(0, 0), 0.875), rect(-2, -1, -0.7875, 1))
        assert overlaps_rect(Text("ABC", P(0, 0), 0.875), rect(0.7874, -1, 2, 1))

    def test_empty_text_has_no_area(self):
        assert not overlaps_rect(Text("", P(0.5, 0.5), 1), R)


class TestWireLane:
    frame = rect(-10, -10, 10, 10)

    def test_a_north_lane_runs_from_the_port_to_the_frame_edge(self):
        assert wire_lane(P(1, -2), Direction.N, self.frame) == rect(0.75, -10, 1.25, -2)

    def test_a_south_lane(self):
        assert wire_lane(P(1, 2), Direction.S, self.frame) == rect(0.75, 2, 1.25, 10)

    def test_an_east_lane(self):
        assert wire_lane(P(2, 1), Direction.E, self.frame) == rect(2, 0.75, 10, 1.25)

    def test_a_west_lane(self):
        assert wire_lane(P(-2, 1), Direction.W, self.frame) == rect(-10, 0.75, -2, 1.25)

    def test_the_ports_own_lead_ends_at_the_lane_and_does_not_enter_it(self):
        lane = wire_lane(P(0, -2), Direction.N, self.frame)
        assert not overlaps_rect(Line(P(0, -2), P(0, -1)), lane)
        assert overlaps_rect(Line(P(0, -3), P(0, -1)), lane)

    def test_a_box_a_quarter_module_beside_the_wire_only_touches_the_lane(self):
        lane = wire_lane(P(0, -2), Direction.N, self.frame)
        assert not boxes_overlap(rect(0.25, -3, 1.75, -2.5), lane)
        assert boxes_overlap(rect(0.125, -3, 1.75, -2.5), lane)
        assert not boxes_overlap(rect(-1.75, -3, -0.25, -2.5), lane)


_odd = st.sampled_from(
    [math.nan, math.inf, -math.inf, 1e300, -1e300, 1e-300, 0.0, -0.0, 0.5, -1.0, 1e6, 720.0]
)
_num = st.one_of(st.floats(-8, 8), _odd)
_points = st.builds(Point, _num, _num)
_boxes = st.builds(Box, _points, _points)
_fills = st.sampled_from(list(Fill))
_elements = st.one_of(
    st.builds(Line, _points, _points),
    st.builds(Polyline, st.lists(_points, max_size=5).map(tuple), st.booleans(), _fills),
    st.builds(Circle, _points, _num, _fills),
    st.builds(Arc, _points, _num, _num, _num),
    st.builds(Text, st.text(max_size=4), _points, _num),
)


class TestTotality:
    @given(_elements, _boxes)
    @settings(max_examples=600, deadline=None)
    def test_overlaps_rect_never_raises(self, element, box):
        assert isinstance(overlaps_rect(element, box), bool)

    @given(_boxes, _boxes)
    def test_boxes_overlap_never_raises(self, a, b):
        assert isinstance(boxes_overlap(a, b), bool)

    @given(_points, st.sampled_from(list(Direction)), _boxes)
    def test_wire_lane_never_raises(self, point, direction, frame):
        assert isinstance(wire_lane(point, direction, frame), Box)


_g = st.integers(-8, 8).map(lambda n: n / 2)
_gr = st.integers(1, 6).map(lambda n: n / 2)
_grid_points = st.builds(Point, _g, _g)


@st.composite
def grid_rects(draw):
    x0, y0 = draw(_g), draw(_g)
    return Box(P(x0, y0), P(x0 + draw(_gr), y0 + draw(_gr)))


def strictly_inside(p, box):
    return box.min.x < p.x < box.max.x and box.min.y < p.y < box.max.y


def along_segment(a, b, steps):
    return [
        P(a.x + (b.x - a.x) * i / steps, a.y + (b.y - a.y) * i / steps) for i in range(steps + 1)
    ]


def along_arc(arc, steps):
    sweep = (arc.end_deg - arc.start_deg) % 360 or 360
    return [arc_point(arc, arc.start_deg + sweep * i / steps) for i in range(steps + 1)]


class TestAgainstSampling:
    """Cross-check the exact tests against dense sampling of the curve, on a coarse grid."""

    @given(_grid_points, _grid_points, grid_rects())
    @settings(max_examples=300, deadline=None)
    def test_a_line_agrees_with_its_samples(self, a, b, box):
        sampled = any(strictly_inside(p, box) for p in along_segment(a, b, 2000))
        assert overlaps_rect(Line(a, b), box) == sampled

    @given(_grid_points, _gr, _fills, grid_rects())
    @settings(max_examples=300, deadline=None)
    def test_a_circle_agrees_with_its_samples(self, centre, radius, fill, box):
        curve = any(strictly_inside(p, box) for p in along_arc(Arc(centre, radius, 0, 0), 1440))
        corners = (box.min, box.max, P(box.min.x, box.max.y), P(box.max.x, box.min.y))
        inside_disk = all(math.hypot(c.x - centre.x, c.y - centre.y) <= radius for c in corners)
        assert overlaps_rect(Circle(centre, radius, fill), box) == (
            curve or (fill is SOLID and inside_disk)
        )

    @given(
        _grid_points,
        _gr,
        st.sampled_from([0, 45, 90, 180, 270, 350]),
        st.sampled_from([10, 90, 135, 200, 270, 0]),
        grid_rects(),
    )
    @settings(max_examples=300, deadline=None)
    def test_an_arc_agrees_with_its_samples(self, centre, radius, start, end, box):
        arc = Arc(centre, radius, start, end)
        assert overlaps_rect(arc, box) == any(strictly_inside(p, box) for p in along_arc(arc, 1440))
