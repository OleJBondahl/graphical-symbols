import dataclasses

import pytest

from symdef.geometry import (
    Arc,
    Box,
    Circle,
    Direction,
    Fill,
    Line,
    Orientation,
    Point,
    Polyline,
    Style,
    Text,
    Weight,
    arc_point,
    arc_sweep,
)


def test_direction_vectors():
    assert [(d.dx, d.dy) for d in Direction] == [(0, -1), (1, 0), (0, 1), (-1, 0)]


def test_direction_opposite():
    assert Direction.N.opposite is Direction.S
    assert Direction.E.opposite is Direction.W
    assert Direction.S.opposite is Direction.N
    assert Direction.W.opposite is Direction.E


def test_weight_values():
    assert Weight.NORMAL.value == 0.1
    assert Weight.THICK.value == 0.2


def test_style_and_fill_members():
    assert [s.value for s in Style] == ["solid", "dashed"]
    assert [f.value for f in Fill] == ["none", "solid"]


def test_orientation_value_is_its_name():
    assert [o.value for o in Orientation] == [
        "R0",
        "R90",
        "R180",
        "R270",
        "MR0",
        "MR90",
        "MR180",
        "MR270",
    ]
    assert all(o.value == o.name for o in Orientation)


def test_point_is_immutable():
    p = Point(1, 2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.x = 3  # ty: ignore[invalid-assignment]


def test_line_is_immutable():
    line = Line(Point(0, 0), Point(1, 0))
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.weight = Weight.THICK  # ty: ignore[invalid-assignment]


def test_point_equality_and_hash():
    assert Point(1, 2) == Point(1, 2)
    assert Point(1, 2) != Point(2, 1)
    assert hash(Point(1, 2)) == hash(Point(1, 2))
    assert len({Point(1, 2), Point(1, 2), Point(0, 0)}) == 2


def test_box_properties():
    b = Box(Point(0, 0), Point(4, 2))
    assert (b.width, b.height, b.center) == (4, 2, Point(2, 1))


def test_element_defaults():
    assert Line(Point(0, 0), Point(1, 0)).style is Style.SOLID
    assert Line(Point(0, 0), Point(1, 0)).port is None
    poly = Polyline((Point(0, 0), Point(1, 0)))
    assert (poly.closed, poly.fill, poly.weight, poly.style) == (
        False,
        Fill.NONE,
        Weight.NORMAL,
        Style.SOLID,
    )
    assert Circle(Point(0, 0), 1).fill is Fill.NONE
    assert Arc(Point(0, 0), 1, 0, 90).style is Style.SOLID
    text = Text("M", Point(0, 0))
    assert (text.height, text.weight) == (1.0, Weight.NORMAL)


def test_text_has_no_anchor_field():
    assert "anchor" not in {f.name for f in dataclasses.fields(Text)}


def test_arc_point_is_exact_at_right_angles():
    arc = Arc(Point(1, 1), 2, 0, 90)
    assert arc_point(arc, 0) == Point(3, 1)
    assert arc_point(arc, 90) == Point(1, 3)
    assert arc_point(arc, 180) == Point(-1, 1)
    assert arc_point(arc, 270) == Point(1, -1)
    assert arc_point(arc, 360) == Point(3, 1)


def test_arc_point_rounds_intermediate_angles():
    p = arc_point(Arc(Point(0, 0), 1, 0, 90), 45)
    assert p == Point(0.707106781187, 0.707106781187)


@pytest.mark.parametrize("angle", [float("nan"), float("inf"), float("-inf")])
def test_arc_point_of_a_non_finite_angle_is_the_centre(angle):
    assert arc_point(Arc(Point(1, 2), 3, 0, 90), angle) == Point(1, 2)


@pytest.mark.parametrize("angle", [1e300, -1e300, 720.0, -450.0])
def test_arc_point_of_a_huge_or_unreduced_angle_is_on_the_circle(angle):
    p = arc_point(Arc(Point(1, 2), 3, 0, 90), angle)
    assert (p.x - 1) ** 2 + (p.y - 2) ** 2 == pytest.approx(9)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [(0, 90, 90), (0, 270, 270), (270, 90, 180), (0, 360, 360), (45, 45, 360), (-90, 90, 180)],
)
def test_arc_sweep_is_clockwise_and_equal_angles_are_a_full_circle(start, end, expected):
    assert arc_sweep(Arc(Point(0, 0), 1, start, end)) == expected
