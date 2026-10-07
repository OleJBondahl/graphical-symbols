"""Orient and translate symbols, in SVG axes (x right, y down)."""

from collections.abc import Callable
from dataclasses import replace

from symdef.geometry import (
    Arc,
    Circle,
    Direction,
    Element,
    Line,
    Orientation,
    Point,
    Polyline,
    Text,
)
from symdef.model import Symbol

_QUARTER = 90
_FULL_TURN = 360
_HALF_TURN = 180

# Each orientation as (mirror x first?, clockwise quarter turns after it).
_PARTS: dict[Orientation, tuple[bool, int]] = {
    Orientation.R0: (False, 0),
    Orientation.R90: (False, 1),
    Orientation.R180: (False, 2),
    Orientation.R270: (False, 3),
    Orientation.MR0: (True, 0),
    Orientation.MR90: (True, 1),
    Orientation.MR180: (True, 2),
    Orientation.MR270: (True, 3),
}

_Move = Callable[[Point], Point]
_Turn = Callable[[Direction], Direction]
_Angles = Callable[[float, float], tuple[float, float]]


def _map_element(element: Element, move: _Move, angles: _Angles) -> Element:
    """Move an element's positions with `move` and an arc's angles with `angles`."""
    match element:
        case Line(start=start, end=end):
            return replace(element, start=move(start), end=move(end))
        case Polyline(points=points):
            return replace(element, points=tuple(move(p) for p in points))
        case Circle(center=center):
            return replace(element, center=move(center))
        case Arc(center=center, start_deg=start, end_deg=end):
            new_start, new_end = angles(start, end)
            return replace(element, center=move(center), start_deg=new_start, end_deg=new_end)
        case Text(position=position):
            return replace(element, position=move(position))


def _map_symbol(symbol: Symbol, move: _Move, turn: _Turn, angles: _Angles) -> Symbol:
    """Carry every geometric part of a symbol along: points with `move`, directions with `turn`.

    Slot boxes keep their size, and nodes, paths and every non-geometric field are untouched.
    """
    return replace(
        symbol,
        elements=tuple(_map_element(e, move, angles) for e in symbol.elements),
        ports=tuple(
            replace(p, position=move(p.position), direction=turn(p.direction)) for p in symbol.ports
        ),
        anchors=tuple(
            replace(a, position=move(a.position), direction=turn(a.direction))
            for a in symbol.anchors
        ),
        slots=tuple(replace(s, position=move(s.position), side=turn(s.side)) for s in symbol.slots),
    )


def orient_point(point: Point, orientation: Orientation) -> Point:
    """Return a point mirrored (if the orientation is an MR) and then turned clockwise.

    Adding 0.0 turns -0.0 into 0.0, so the result never contains a negative zero.
    """
    mirrored, turns = _PARTS[orientation]
    x, y = (-point.x if mirrored else point.x), point.y
    for _ in range(turns):
        x, y = -y, x
    return Point(x + 0.0, y + 0.0)


def orient_direction(direction: Direction, orientation: Orientation) -> Direction:
    """Return a direction (or slot side) transformed as a vector by an orientation."""
    mirrored, turns = _PARTS[orientation]
    x, y = (-direction.dx if mirrored else direction.dx), direction.dy
    for _ in range(turns):
        x, y = -y, x
    return Direction((x, y))


def orient(symbol: Symbol, orientation: Orientation) -> Symbol:
    """Return the symbol mirrored first if the orientation is an MR, then turned clockwise.

    Ports, anchors and slots move as points and turn as directions; circle and arc centres move
    as points and radii stay. Arc angles are normalised into [0, 360): a turn adds its degrees,
    and a mirror maps t to 180 - t and swaps start with end, so the arc is still swept clockwise.
    Text elements and slot boxes stay upright and unchanged; only their position moves.

    Args:
        symbol: The symbol in its own orientation.
        orientation: One of the 8 orientations.

    Returns:
        A new symbol; nodes, paths and all non-geometric fields are unchanged.
    """
    mirrored, turns = _PARTS[orientation]
    add = turns * _QUARTER

    def angles(start: float, end: float) -> tuple[float, float]:
        if mirrored:
            start, end = _HALF_TURN - end, _HALF_TURN - start
        return (start + add) % _FULL_TURN + 0.0, (end + add) % _FULL_TURN + 0.0

    return _map_symbol(
        symbol,
        lambda p: orient_point(p, orientation),
        lambda d: orient_direction(d, orientation),
        angles,
    )


def translate(symbol: Symbol, dx: float, dy: float) -> Symbol:
    """Return the symbol shifted by (dx, dy).

    Args:
        symbol: The symbol to shift.
        dx: Horizontal shift, positive to the right.
        dy: Vertical shift, positive downwards.

    Returns:
        A new symbol; arc angles, directions and slot boxes are unchanged.
    """
    return _map_symbol(
        symbol,
        lambda p: Point(p.x + dx, p.y + dy),
        lambda d: d,
        lambda start, end: (start, end),
    )
