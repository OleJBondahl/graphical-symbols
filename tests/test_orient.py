import math

import pytest
from hypothesis import given
from hypothesis import strategies as st
from orientations import inverse

from graphical_symbols.geometry import (
    Arc,
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
)
from graphical_symbols.model import (
    Allow,
    Anchor,
    Node,
    Path,
    PathKind,
    Port,
    Potential,
    Reference,
    Slot,
    Status,
    Symbol,
    SymbolKind,
)
from graphical_symbols.orient import (
    orient,
    orient_direction,
    orient_point,
    translate,
)

N, E, S, W = Direction.N, Direction.E, Direction.S, Direction.W
Ori = Orientation


def sym(*elements, **fields):
    return Symbol(
        name="t",
        kind=SymbolKind.SYMBOL,
        status=Status.UNVERIFIED,
        reference=Reference("X", "1"),
        elements=tuple(elements),
        **fields,
    )


def only_arc(symbol):
    (arc,) = symbol.elements
    assert isinstance(arc, Arc)
    return arc


# -- hand-checked cases

_POINT_TABLE = {
    Ori.R0: Point(1, 2),
    Ori.R90: Point(-2, 1),
    Ori.R180: Point(-1, -2),
    Ori.R270: Point(2, -1),
    Ori.MR0: Point(-1, 2),
    Ori.MR90: Point(-2, -1),
    Ori.MR180: Point(1, -2),
    Ori.MR270: Point(2, 1),
}


@pytest.mark.parametrize("orientation", list(Ori))
def test_orient_point_table(orientation):
    assert orient_point(Point(1, 2), orientation) == _POINT_TABLE[orientation]


def test_r90_maps_x_y_to_minus_y_x():
    assert orient_point(Point(2, 3), Ori.R90) == Point(-3, 2)


_DIRECTION_TABLE = {
    Ori.R0: (N, E, S, W),
    Ori.R90: (E, S, W, N),
    Ori.R180: (S, W, N, E),
    Ori.R270: (W, N, E, S),
    Ori.MR0: (N, W, S, E),
    Ori.MR90: (E, N, W, S),
    Ori.MR180: (S, E, N, W),
    Ori.MR270: (W, S, E, N),
}


@pytest.mark.parametrize("orientation", list(Ori))
def test_orient_direction_table(orientation):
    assert (
        tuple(orient_direction(d, orientation) for d in (N, E, S, W))
        == (_DIRECTION_TABLE[orientation])
    )


def test_north_port_under_r90_is_east():
    s = sym(ports=(Port("in", Point(0, -2), N),))
    (p,) = orient(s, Ori.R90).ports
    assert p.direction is E
    assert p.position == Point(2, 0)


def test_mr180_flips_top_to_bottom():
    s = sym(
        Line(Point(0, -2), Point(1, 0)),
        ports=(Port("in", Point(0, -2), N), Port("out", Point(3, 2), S)),
    )
    flipped = orient(s, Ori.MR180)
    assert flipped.elements == (Line(Point(0, 2), Point(1, 0)),)
    assert [(p.position, p.direction) for p in flipped.ports] == [
        (Point(0, 2), S),
        (Point(3, -2), N),
    ]


@pytest.mark.parametrize(
    ("orientation", "start", "end"),
    [
        (Ori.R0, 180, 0),
        (Ori.MR0, 180, 0),
        (Ori.R90, 270, 90),
        (Ori.R180, 0, 180),
        (Ori.R270, 90, 270),
        (Ori.MR90, 270, 90),
        (Ori.MR180, 0, 180),
        (Ori.MR270, 90, 270),
    ],
)
def test_arc_180_to_0_under_every_orientation(orientation, start, end):
    arc = only_arc(orient(sym(Arc(Point(0, 0), 2, 180, 0)), orientation))
    assert (arc.start_deg, arc.end_deg) == (start, end)


def test_arc_mirror_maps_t_to_180_minus_t_and_swaps():
    arc = only_arc(orient(sym(Arc(Point(0, 0), 2, 10, 50)), Ori.MR0))
    assert (arc.start_deg, arc.end_deg) == (130, 170)
    arc = only_arc(orient(sym(Arc(Point(0, 0), 2, 10, 50)), Ori.MR90))
    assert (arc.start_deg, arc.end_deg) == (220, 260)


def test_arc_rotation_adds_the_angle_and_normalises():
    arc = only_arc(orient(sym(Arc(Point(1, 2), 2, 300, 350)), Ori.R90))
    assert arc == Arc(Point(-2, 1), 2, 30, 80)
    arc = only_arc(orient(sym(Arc(Point(0, 0), 2, 300, 350)), Ori.R0))
    assert (arc.start_deg, arc.end_deg) == (300, 350)


def test_circle_centre_moves_and_radius_stays():
    (circle,) = orient(sym(Circle(Point(1, 2), 0.5, Fill.SOLID, Weight.THICK)), Ori.R90).elements
    assert circle == Circle(Point(-2, 1), 0.5, Fill.SOLID, Weight.THICK)


def test_text_only_moves():
    text = Text("Mx", Point(1, 2), 0.5, Weight.THICK)
    for o in Ori:
        (moved,) = orient(sym(text), o).elements
        assert moved == Text("Mx", _POINT_TABLE[o], 0.5, Weight.THICK)


def test_slot_position_and_side_move_but_the_box_stays():
    s = sym(slots=(Slot("tag", Point(1, 2), E, (3.0, 1.0)),))
    (slot,) = orient(s, Ori.R90).slots
    assert slot == Slot("tag", Point(-2, 1), S, (3.0, 1.0))
    (slot,) = orient(s, Ori.MR0).slots
    assert slot == Slot("tag", Point(-1, 2), W, (3.0, 1.0))


def test_anchors_are_carried_along():
    s = sym(anchors=(Anchor("link", Point(-0.5, 0), W),))
    (anchor,) = orient(s, Ori.R90).anchors
    assert anchor == Anchor("link", Point(0, -0.5), N)


def test_polyline_points_move_and_flags_stay():
    poly = Polyline(
        (Point(0, 0), Point(2, 0), Point(2, 1)), closed=True, fill=Fill.SOLID, weight=Weight.THICK
    )
    (moved,) = orient(sym(poly), Ori.R90).elements
    assert moved == Polyline(
        (Point(0, 0), Point(0, 2), Point(-1, 2)),
        closed=True,
        fill=Fill.SOLID,
        weight=Weight.THICK,
    )


def test_line_keeps_weight_and_style():
    line = Line(Point(0, 0), Point(1, 0), Weight.THICK, Style.DASHED)
    (moved,) = orient(sym(line), Ori.R90).elements
    assert moved == Line(Point(0, 0), Point(0, 1), Weight.THICK, Style.DASHED)


def test_everything_else_is_unchanged_by_orient_and_translate():
    s = sym(
        Line(Point(0, 0), Point(1, 0)),
        ports=(Port("a", Point(0, 0), N, "d"),),
        nodes=(Node(("a",), Potential.EARTH),),
        paths=(Path("a", "a", PathKind.DIODE, through=True),),
        pole_pitch=8,
        lint_allow=(Allow("port-off-geometry", "why"),),
    )
    for moved in (orient(s, Ori.MR270), translate(s, 3, 4)):
        assert (moved.name, moved.kind, moved.status, moved.reference) == (
            s.name,
            s.kind,
            s.status,
            s.reference,
        )
        assert (moved.nodes, moved.paths, moved.pole_pitch, moved.lint_allow) == (
            s.nodes,
            s.paths,
            8,
            s.lint_allow,
        )
        assert (moved.ports[0].id, moved.ports[0].description) == ("a", "d")


def test_translate_shifts_positions_only():
    s = sym(
        Line(Point(0, 0), Point(1, 2)),
        Polyline((Point(0, 0), Point(1, 0), Point(1, 1)), closed=True, fill=Fill.SOLID),
        Circle(Point(3, 3), 2),
        Arc(Point(1, 1), 1, 0, 90),
        Text("A", Point(2, 2), height=2.0),
        ports=(Port("1", Point(1, 2), S, "out"),),
        anchors=(Anchor("k", Point(0, 1), W),),
        slots=(Slot("tag", Point(0, 0), N, (2.0, 1.0)),),
    )
    t = translate(s, 5, -1)
    assert t.elements == (
        Line(Point(5, -1), Point(6, 1)),
        Polyline((Point(5, -1), Point(6, -1), Point(6, 0)), closed=True, fill=Fill.SOLID),
        Circle(Point(8, 2), 2),
        Arc(Point(6, 0), 1, 0, 90),
        Text("A", Point(7, 1), height=2.0),
    )
    assert t.ports == (Port("1", Point(6, 1), S, "out"),)
    assert t.anchors == (Anchor("k", Point(5, 0), W),)
    assert t.slots == (Slot("tag", Point(5, -1), N, (2.0, 1.0)),)


def test_inverse_pairs():
    assert {o: inverse(o) for o in Ori} == {
        Ori.R0: Ori.R0,
        Ori.R90: Ori.R270,
        Ori.R180: Ori.R180,
        Ori.R270: Ori.R90,
        Ori.MR0: Ori.MR0,
        Ori.MR90: Ori.MR90,
        Ori.MR180: Ori.MR180,
        Ori.MR270: Ori.MR270,
    }


# -- property tests over grid-aligned symbols

_grid = st.integers(-64, 64).map(lambda n: n / 8)
_points = st.builds(Point, _grid, _grid)
_radii = st.integers(1, 32).map(lambda n: n / 8)
_angles = st.integers(0, 71).map(lambda n: n * 5.0)
_weights = st.sampled_from(Weight)
_styles = st.sampled_from(Style)
_fills = st.sampled_from(Fill)
_directions = st.sampled_from(Direction)
_ids = st.text("abc", min_size=1, max_size=3)
_elements = st.one_of(
    st.builds(Line, _points, _points, _weights, _styles),
    st.builds(
        Polyline,
        st.lists(_points, max_size=4).map(tuple),
        st.booleans(),
        _fills,
        _weights,
        _styles,
    ),
    st.builds(Circle, _points, _radii, _fills, _weights),
    st.builds(Arc, _points, _radii, _angles, _angles, _weights, _styles),
    st.builds(Text, st.text(max_size=3), _points, _radii, _weights),
)
_symbols = st.builds(
    Symbol,
    name=st.just("t"),
    kind=st.sampled_from(SymbolKind),
    status=st.sampled_from(Status),
    reference=st.just(Reference("X", "1")),
    elements=st.lists(_elements, max_size=5).map(tuple),
    ports=st.lists(st.builds(Port, _ids, _points, _directions), max_size=3).map(tuple),
    nodes=st.lists(st.builds(Node, st.lists(_ids, max_size=2).map(tuple)), max_size=2).map(tuple),
    paths=st.lists(
        st.builds(Path, _ids, _ids, st.sampled_from(PathKind), st.booleans()), max_size=2
    ).map(tuple),
    anchors=st.lists(st.builds(Anchor, _ids, _points, _directions), max_size=2).map(tuple),
    slots=st.lists(
        st.builds(Slot, _ids, _points, _directions, st.tuples(_radii, _radii)), max_size=2
    ).map(tuple),
)


def round_trips(symbol, orientation, inverse_orientation):
    return orient(orient(symbol, orientation), inverse_orientation) == symbol


def _numbers(symbol):
    values = []
    for e in symbol.elements:
        match e:
            case Line(start=a, end=b):
                values += [a.x, a.y, b.x, b.y]
            case Polyline(points=points):
                values += [v for p in points for v in (p.x, p.y)]
            case Circle(center=c) | Text(position=c):
                values += [c.x, c.y]
            case Arc(center=c, start_deg=a, end_deg=b):
                values += [c.x, c.y, a, b]
    for p in (*symbol.ports, *symbol.anchors, *symbol.slots):
        values += [p.position.x, p.position.y]
    return values


@given(_symbols, st.sampled_from(Orientation))
def test_orient_then_inverse_returns_the_same_symbol(s, o):
    assert round_trips(s, o, inverse(o))


@given(_symbols)
def test_orient_r0_is_identity(s):
    assert orient(s, Ori.R0) == s


@given(_symbols, st.sampled_from(Orientation))
def test_orient_never_yields_negative_zero(s, o):
    for v in _numbers(orient(s, o)):
        assert v != 0 or math.copysign(1.0, v) == 1.0


@given(_symbols, _grid, _grid)
def test_translate_then_back_is_identity(s, dx, dy):
    assert translate(translate(s, dx, dy), -dx, -dy) == s


@given(_symbols, _grid, _grid, st.sampled_from(Orientation))
def test_orient_of_translate_is_translate_of_the_oriented_offset(s, dx, dy, o):
    moved = orient_point(Point(dx, dy), o)
    assert orient(translate(s, dx, dy), o) == translate(orient(s, o), moved.x, moved.y)


def test_round_trip_check_can_fail_with_a_wrong_inverse():
    s = sym(Line(Point(0, 0), Point(1, 2)), ports=(Port("in", Point(0, -2), N),))
    assert round_trips(s, Ori.R90, Ori.R270)
    assert not round_trips(s, Ori.R90, Ori.R90)
    assert not round_trips(s, Ori.R90, Ori.R0)
