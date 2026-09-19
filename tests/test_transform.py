import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from graphical_symbols.geometry import (
    Anchor,
    Arc,
    Circle,
    Direction,
    Fill,
    Line,
    Point,
    Polyline,
    Text,
    Weight,
)
from graphical_symbols.symbol import Port, Reference, Status, Symbol, bbox
from graphical_symbols.transform import mirror, rotate, translate


def sym(*elements, ports=()):
    return Symbol("t", Reference("X", "1"), tuple(elements), tuple(ports))


def test_rotate_90_moves_port_and_direction():
    s = Symbol(
        "t",
        Reference("X", "1"),
        (Line(Point(0, 0), Point(0, -2)),),
        (Port("1", Point(0, -2), Direction.N),),
    )
    r = rotate(s, 90)
    assert r.ports[0].position == Point(2, 0)
    assert r.ports[0].direction is Direction.E
    assert r.elements[0] == Line(Point(0, 0), Point(2, 0))


def test_rotate_directions_cycle_clockwise():
    s = sym(Line(Point(0, 0), Point(1, 0)), ports=[Port("1", Point(0, 0), Direction.N)])
    turns = [rotate(s, d).ports[0].direction for d in (0, 90, 180, 270)]
    assert turns == [Direction.N, Direction.E, Direction.S, Direction.W]


def test_rotate_arc_adds_angle_and_normalises():
    s = sym(Arc(Point(0, 0), 2, 300, 350))
    assert rotate(s, 90).elements[0] == Arc(Point(0, 0), 2, 30, 80)
    assert rotate(s, 0).elements[0] == Arc(Point(0, 0), 2, 300, 350)


def test_mirror_x_flips_arc():
    s = Symbol("t", Reference("X", "1"), (Arc(Point(0, 0), 2, 0, 90),))
    m = mirror(s, "x")
    assert m.elements[0] == Arc(Point(0, 0), 2, 90, 180)


def test_mirror_y_flips_arc():
    m = mirror(sym(Arc(Point(1, 1), 2, 0, 90)), "y")
    assert m.elements[0] == Arc(Point(1, -1), 2, 270, 0)


def test_mirror_x_swaps_east_west_only():
    ports = [Port(str(i), Point(1, 1), d) for i, d in enumerate(Direction)]
    m = mirror(sym(Line(Point(0, 0), Point(1, 0)), ports=ports), "x")
    assert [p.direction for p in m.ports] == [Direction.N, Direction.W, Direction.S, Direction.E]
    assert m.ports[0].position == Point(-1, 1)


def test_mirror_y_swaps_north_south_only():
    ports = [Port(str(i), Point(1, 1), d) for i, d in enumerate(Direction)]
    m = mirror(sym(Line(Point(0, 0), Point(1, 0)), ports=ports), "y")
    assert [p.direction for p in m.ports] == [Direction.S, Direction.E, Direction.N, Direction.W]
    assert m.ports[0].position == Point(1, -1)


def test_translate_shifts_everything():
    s = sym(
        Line(Point(0, 0), Point(1, 2)),
        Polyline((Point(0, 0), Point(1, 0), Point(1, 1)), closed=True, fill=Fill.SOLID),
        Circle(Point(3, 3), 2),
        Arc(Point(1, 1), 1, 0, 90),
        Text("A", Point(2, 2), height=2.0, anchor=Anchor.START),
        ports=[Port("1", Point(1, 2), Direction.S, "out")],
    )
    t = translate(s, 5, -1)
    assert t.elements == (
        Line(Point(5, -1), Point(6, 1)),
        Polyline((Point(5, -1), Point(6, -1), Point(6, 0)), closed=True, fill=Fill.SOLID),
        Circle(Point(8, 2), 2),
        Arc(Point(6, 0), 1, 0, 90),
        Text("A", Point(7, 1), height=2.0, anchor=Anchor.START),
    )
    assert t.ports == (Port("1", Point(6, 1), Direction.S, "out"),)


def test_transforms_keep_style_and_metadata():
    s = Symbol(
        "keep",
        Reference("X", "1", "2020", "form"),
        (
            Line(Point(0, 0), Point(1, 0), Weight.THICK),
            Circle(Point(0, 0), 1, Fill.SOLID, Weight.THICK),
            Text("hello", Point(1, 1), 2.0, Anchor.END),
        ),
        (Port("p", Point(0, 0), Direction.E, "desc"),),
        Status.VERIFIED,
    )
    for t in (rotate(s, 90), mirror(s, "x"), mirror(s, "y"), translate(s, 1, 1)):
        assert (t.name, t.reference, t.status) == (s.name, s.reference, s.status)
        line, circle, text = t.elements
        assert isinstance(line, Line)
        assert isinstance(circle, Circle)
        assert isinstance(text, Text)
        assert line.weight is Weight.THICK
        assert (circle.fill, circle.weight) == (Fill.SOLID, Weight.THICK)
        assert (text.content, text.height, text.anchor) == ("hello", 2.0, Anchor.END)
        assert (t.ports[0].id, t.ports[0].description) == ("p", "desc")


def test_no_negative_zero():
    s = sym(Line(Point(0, 0), Point(0, 2)), Arc(Point(0, 0), 1, 0, 180), Text("A", Point(0, 0)))
    for t in (rotate(s, 90), rotate(s, 180), rotate(s, 270), mirror(s, "x"), mirror(s, "y")):
        for v in _coordinates(t):
            assert math.copysign(1.0, v) == 1.0 or v != 0


# -- property tests over grid-aligned symbols

_grid = st.integers(-64, 64).map(lambda n: n / 8)
_points = st.builds(Point, _grid, _grid)
_radii = st.integers(1, 32).map(lambda n: n / 8)
_angles = st.integers(0, 71).map(lambda n: n * 5.0)
_elements = st.one_of(
    st.builds(Line, _points, _points),
    st.builds(Circle, _points, _radii),
    st.builds(Arc, _points, _radii, _angles, _angles),
    st.builds(Text, st.text(max_size=3), _points),
)
_ports = st.builds(Port, st.text(max_size=3), _points, st.sampled_from(Direction))
_symbols = st.builds(
    Symbol,
    st.just("t"),
    st.just(Reference("X", "1")),
    st.lists(_elements, min_size=1, max_size=5).map(tuple),
    st.lists(_ports, max_size=3).map(tuple),
)


def _coordinates(symbol):
    values = []
    for e in symbol.elements:
        match e:
            case Line(start=a, end=b):
                values += [a.x, a.y, b.x, b.y]
            case Circle(center=c) | Text(position=c):
                values += [c.x, c.y]
            case Arc(center=c, start_deg=a, end_deg=b):
                values += [c.x, c.y, a, b]
    for p in symbol.ports:
        values += [p.position.x, p.position.y]
    return values


@given(_symbols)
def test_rotate_four_quarter_turns_is_identity(s):
    assert rotate(rotate(rotate(rotate(s, 90), 90), 90), 90) == s


@given(_symbols)
def test_rotate_composes(s):
    assert rotate(rotate(s, 90), 180) == rotate(s, 270)


@given(_symbols)
def test_mirror_x_twice_is_identity(s):
    assert mirror(mirror(s, "x"), "x") == s


@given(_symbols)
def test_mirror_y_twice_is_identity(s):
    assert mirror(mirror(s, "y"), "y") == s


@given(_symbols)
def test_rotate_90_swaps_bbox_extents(s):
    before, after = bbox(s), bbox(rotate(s, 90))
    assert after.width == pytest.approx(before.height, abs=1e-9)
    assert after.height == pytest.approx(before.width, abs=1e-9)


@given(_symbols, _grid, _grid)
def test_translate_then_back_is_identity(s, dx, dy):
    assert translate(translate(s, dx, dy), -dx, -dy) == s


@given(_symbols, st.sampled_from([0, 90, 180, 270]))
def test_rotate_never_yields_negative_zero(s, degrees):
    for v in _coordinates(rotate(s, degrees)):
        assert v != 0 or math.copysign(1.0, v) == 1.0
