import pytest

from graphical_symbols.errors import (
    DuplicateSymbolError,
    GraphicalSymbolsError,
    InvalidSymbolError,
    UnknownSymbolError,
)
from graphical_symbols.geometry import Arc, Circle, Direction, Line, Point, Polyline, Text
from graphical_symbols.symbol import Box, Port, Reference, Status, Symbol, bbox


def sym(*elements):
    return Symbol("t", Reference("X", "1"), tuple(elements))


def test_error_hierarchy():
    for error in (InvalidSymbolError, DuplicateSymbolError, UnknownSymbolError):
        assert issubclass(error, GraphicalSymbolsError)


def test_symbol_defaults():
    s = sym(Line(Point(0, 0), Point(1, 0)))
    assert s.ports == ()
    assert s.status is Status.UNVERIFIED
    assert Reference("X", "1").edition is None
    assert Port("1", Point(0, 0), Direction.W).description == ""


def test_symbol_with_no_elements_raises():
    with pytest.raises(InvalidSymbolError):
        sym()


def test_bbox_lines():
    b = bbox(sym(Line(Point(0, 0), Point(2, 0)), Line(Point(0, 0), Point(0, -1))))
    assert (b.min, b.max) == (Point(0, -1), Point(2, 0))


def test_bbox_polyline():
    b = bbox(sym(Polyline((Point(-1, 0), Point(0, 3), Point(2, 1)), closed=True)))
    assert (b.min, b.max) == (Point(-1, 0), Point(2, 3))


def test_bbox_circle():
    b = bbox(sym(Circle(Point(1, 1), 2)))
    assert (b.min, b.max) == (Point(-1, -1), Point(3, 3))


def test_bbox_arc_includes_axis_extremes():
    # quarter arc from 0 to 90 degrees clockwise: from (r,0) down to (0,r)
    b = bbox(sym(Arc(Point(0, 0), 2, 0, 90)))
    assert (b.min, b.max) == (Point(0, 0), Point(2, 2))
    # half arc from 270 to 90 clockwise passes through 0: reaches x = +r
    b = bbox(sym(Arc(Point(0, 0), 2, 270, 90)))
    assert b.max.x == 2
    assert b.min.x == 0


def test_bbox_arc_wraps_when_end_not_after_start():
    # 350 to 10 sweeps 20 degrees through angle 0 (x = +r), not 340 degrees
    b = bbox(sym(Arc(Point(0, 0), 1, 350, 10)))
    assert b.max.x == 1
    assert b.min.x > 0.98


def test_bbox_text_is_its_position_only():
    b = bbox(sym(Line(Point(0, 0), Point(1, 0)), Text("A", Point(5, 5))))
    assert (b.min, b.max) == (Point(0, 0), Point(5, 5))


def test_box_properties():
    b = Box(Point(0, 0), Point(4, 2))
    assert (b.width, b.height, b.center) == (4, 2, Point(2, 1))
