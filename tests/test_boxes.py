import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from symdef.boxes import body_box, element_box, keepout_box, slot_box
from symdef.geometry import (
    Arc,
    Box,
    Circle,
    Direction,
    Line,
    Orientation,
    Point,
    Polyline,
    Text,
)
from symdef.model import Reference, Slot, Status, Symbol, SymbolKind
from symdef.orient import orient


def sym(*elements, slots=()):
    return Symbol(
        name="t",
        kind=SymbolKind.SYMBOL,
        status=Status.UNVERIFIED,
        reference=Reference("X", "1"),
        elements=tuple(elements),
        slots=tuple(slots),
    )


def box(x0, y0, x1, y1):
    return Box(Point(x0, y0), Point(x1, y1))


def test_line_box_spans_its_points():
    assert element_box(Line(Point(2, 0), Point(0, -1))) == box(0, -1, 2, 0)


def test_polyline_box_spans_its_points():
    poly = Polyline((Point(-1, 0), Point(0, 3), Point(2, 1)), closed=True)
    assert element_box(poly) == box(-1, 0, 2, 3)


def test_circle_box_is_the_full_diameter():
    assert element_box(Circle(Point(1, 1), 2)) == box(-1, -1, 3, 3)


def test_arc_box_includes_axis_extremes():
    # quarter arc from 0 to 90 degrees clockwise: from (r, 0) down to (0, r)
    assert element_box(Arc(Point(0, 0), 2, 0, 90)) == box(0, 0, 2, 2)
    # half arc from 270 to 90 clockwise passes through 0: reaches x = +r
    assert element_box(Arc(Point(0, 0), 2, 270, 90)) == box(0, -2, 2, 2)


def test_arc_box_wraps_when_end_is_not_after_start():
    # 350 to 10 sweeps 20 degrees through angle 0 (x = +r), not 340 degrees
    b = element_box(Arc(Point(0, 0), 1, 350, 10))
    assert b.max.x == 1
    assert b.min.x > 0.98


def test_arc_with_equal_angles_is_a_full_circle():
    assert element_box(Arc(Point(0, 0), 1, 30, 30)) == box(-1, -1, 1, 1)


def test_text_box_is_centred_on_at_and_sized_by_height_and_length():
    b = element_box(Text("ABCD", Point(1, 2), 1.0))
    assert (b.min.x, b.min.y, b.max.x, b.max.y) == pytest.approx((-0.2, 1.5, 2.2, 2.5))
    assert (b.width, b.height) == (pytest.approx(2.4), 1.0)
    assert (b.center.x, b.center.y) == pytest.approx((1, 2))


def test_wide_text_widens_the_box():
    narrow = body_box(sym(Line(Point(0, 0), Point(1, 0)), Text("A", Point(0, 0), 1.0)))
    wide = body_box(sym(Line(Point(0, 0), Point(1, 0)), Text("AAAAAAAA", Point(0, 0), 1.0)))
    assert narrow.min.x == pytest.approx(-0.3)
    assert wide.min.x == pytest.approx(-2.4)
    assert wide.max.x == pytest.approx(2.4)
    assert wide.width > narrow.width


def test_text_width_scales_with_height():
    assert element_box(Text("AB", Point(0, 0), 0.5)).width == pytest.approx(0.6)
    assert element_box(Text("AB", Point(0, 0), 0.5)).height == 0.5


def test_empty_text_has_zero_width():
    assert element_box(Text("", Point(1, 1), 1.0)) == box(1, 0.5, 1, 1.5)


def test_element_without_points_has_the_origin_box():
    assert element_box(Polyline(())) == box(0, 0, 0, 0)


def test_body_box_is_the_union_of_element_boxes():
    s = sym(Line(Point(0, 0), Point(2, 0)), Line(Point(0, 0), Point(0, -1)), Circle(Point(5, 5), 1))
    assert body_box(s) == box(0, -1, 6, 6)


def test_body_box_of_a_symbol_without_elements_is_the_origin():
    assert body_box(sym()) == box(0, 0, 0, 0)


def test_body_box_ignores_an_element_with_no_points():
    assert body_box(sym(Polyline(()), Line(Point(1, 1), Point(2, 2)))) == box(1, 1, 2, 2)


@pytest.mark.parametrize(
    ("side", "expected"),
    [
        (Direction.E, box(1, 1.5, 4, 2.5)),
        (Direction.W, box(-2, 1.5, 1, 2.5)),
        (Direction.N, box(-0.5, 1, 2.5, 2)),
        (Direction.S, box(-0.5, 2, 2.5, 3)),
    ],
)
def test_slot_box_grows_from_at_by_side(side, expected):
    assert slot_box(Slot("tag", Point(1, 2), side, (3.0, 1.0))) == expected


def test_keepout_box_unites_body_and_every_slot_box():
    s = sym(
        Line(Point(0, -2), Point(0, 2)),
        slots=(
            Slot("tag", Point(-1.5, 0), Direction.W, (6.0, 1.0)),
            Slot("marking.in", Point(0.25, -1.5), Direction.E, (1.5, 1.0)),
        ),
    )
    assert body_box(s) == box(0, -2, 0, 2)
    assert keepout_box(s) == box(-7.5, -2, 1.75, 2)


def test_keepout_box_without_slots_is_the_body_box():
    s = sym(Line(Point(0, 0), Point(3, 1)))
    assert keepout_box(s) == body_box(s)


def test_slot_box_stays_upright_under_orient():
    slot = Slot("tag", Point(-1.5, 0), Direction.W, (6.0, 1.0))
    s = sym(Line(Point(0, -2), Point(0, 2)), slots=(slot,))
    (rotated,) = orient(s, Orientation.R90).slots
    assert rotated.side is Direction.N
    b = slot_box(rotated)
    assert (b.width, b.height) == (6.0, 1.0)
    assert b == box(-3, -2.5, 3, -1.5)


_grid = st.integers(-64, 64).map(lambda n: n / 8)
_points = st.builds(Point, _grid, _grid)


@given(st.lists(st.tuples(_points, _points), min_size=1, max_size=4), st.sampled_from(Orientation))
def test_body_box_of_lines_follows_orient_for_a_rigid_transform(pairs, o):
    s = sym(*(Line(a, b) for a, b in pairs))
    before, after = body_box(s), body_box(orient(s, o))
    assert sorted((after.width, after.height)) == sorted((before.width, before.height))


_ODD = [math.nan, math.inf, -math.inf, 1e300, -1e300, 720.0, -450.0]


@pytest.mark.parametrize("angle", _ODD)
@pytest.mark.parametrize("field", ["start_deg", "end_deg"])
def test_an_arc_with_an_odd_angle_has_a_box_and_never_raises(angle, field):
    angles = {"start_deg": 10.0, "end_deg": 100.0, field: angle}
    arc = Arc(Point(1, 1), 2, angles["start_deg"], angles["end_deg"])
    element_box(arc)
    body_box(sym(arc))


@pytest.mark.parametrize("angle", [math.nan, math.inf, -math.inf])
def test_an_arc_with_a_non_finite_angle_counts_as_its_centre(angle):
    assert element_box(Arc(Point(1, 2), 3, angle, 90)) == box(1, 2, 1, 2)
    assert element_box(Arc(Point(1, 2), 3, 0, angle)) == box(1, 2, 1, 2)


def test_arc_angles_beyond_a_turn_give_the_box_of_their_normalised_angles():
    assert element_box(Arc(Point(0, 0), 2, 720, 810)) == element_box(Arc(Point(0, 0), 2, 0, 90))
    assert element_box(Arc(Point(0, 0), 2, -90, 90)) == element_box(Arc(Point(0, 0), 2, 270, 90))


_any = st.sampled_from([*_ODD, 0.0, 0.5, 90.0, -3.0, 1e6, 1e-300])


@given(_any, _any, _any, _any, _any)
def test_element_box_of_an_arc_is_total_for_any_floats(x, y, r, start, end):
    element_box(Arc(Point(x, y), r, start, end))
