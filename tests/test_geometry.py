import dataclasses

import pytest

from graphical_symbols.geometry import Arc, Direction, Line, Point, Weight, arc_point, arc_sweep


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


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [(0, 90, 90), (0, 270, 270), (270, 90, 180), (0, 360, 360), (45, 45, 360), (-90, 90, 180)],
)
def test_arc_sweep_is_clockwise_and_equal_angles_are_a_full_circle(start, end, expected):
    assert arc_sweep(Arc(Point(0, 0), 1, start, end)) == expected
