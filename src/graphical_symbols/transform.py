"""Translate, rotate and mirror symbols, in SVG axes (x right, y down)."""

from collections.abc import Callable
from dataclasses import replace
from typing import Literal

import deal

from graphical_symbols.geometry import Arc, Circle, Direction, Element, Line, Point, Polyline, Text
from graphical_symbols.symbol import Symbol

# An affine map (x, y) -> (a*x + b*y + e, c*x + d*y + f), stored as (a, b, c, d, e, f).
_Affine = tuple[int, int, int, int, float, float]
_AngleMap = Callable[[float, float], tuple[float, float]]

_ROTATIONS: dict[int, _Affine] = {
    0: (1, 0, 0, 1, 0, 0),
    90: (0, -1, 1, 0, 0, 0),
    180: (-1, 0, 0, -1, 0, 0),
    270: (0, 1, -1, 0, 0, 0),
}
_MIRROR_X: _Affine = (-1, 0, 0, 1, 0, 0)
_MIRROR_Y: _Affine = (1, 0, 0, -1, 0, 0)


@deal.pure
def _map_point(p: Point, m: _Affine) -> Point:
    """Apply an affine map to a point; adding 0.0 turns -0.0 into 0.0."""
    a, b, c, d, e, f = m
    return Point(a * p.x + b * p.y + e + 0.0, c * p.x + d * p.y + f + 0.0)


@deal.pure
def _map_direction(direction: Direction, m: _Affine) -> Direction:
    """Apply the linear part of an affine map to a unit vector."""
    a, b, c, d, _, _ = m
    return Direction((a * direction.dx + b * direction.dy, c * direction.dx + d * direction.dy))


@deal.pure
def _map_element(element: Element, m: _Affine, angle_map: _AngleMap) -> Element:
    """Apply an affine map to an element's positions, and angle_map to an arc's angles."""
    match element:
        case Line(start=start, end=end):
            return replace(element, start=_map_point(start, m), end=_map_point(end, m))
        case Polyline(points=points):
            return replace(element, points=tuple(_map_point(p, m) for p in points))
        case Circle(center=center):
            return replace(element, center=_map_point(center, m))
        case Arc(center=center, start_deg=start, end_deg=end):
            new_start, new_end = angle_map(start, end)
            return replace(
                element, center=_map_point(center, m), start_deg=new_start, end_deg=new_end
            )
        case Text(position=position):
            return replace(element, position=_map_point(position, m))


@deal.pure
def _map_symbol(symbol: Symbol, m: _Affine, angle_map: _AngleMap) -> Symbol:
    """Apply an affine map to every element and port; port directions follow the geometry."""
    ports = tuple(
        replace(
            port,
            position=_map_point(port.position, m),
            direction=_map_direction(port.direction, m),
        )
        for port in symbol.ports
    )
    elements = tuple(_map_element(e, m, angle_map) for e in symbol.elements)
    return replace(symbol, elements=elements, ports=ports)


@deal.pure
def translate(symbol: Symbol, dx: float, dy: float) -> Symbol:
    """Return the symbol shifted by (dx, dy).

    Args:
        symbol: The symbol to shift.
        dx: Horizontal shift, positive to the right.
        dy: Vertical shift, positive downwards.

    Returns:
        A new symbol; arc angles and port directions are unchanged.
    """
    return _map_symbol(symbol, (1, 0, 0, 1, dx, dy), lambda start, end: (start, end))


@deal.pure
def rotate(symbol: Symbol, degrees: Literal[0, 90, 180, 270]) -> Symbol:
    """Return the symbol rotated clockwise on screen about the origin.

    Args:
        symbol: The symbol to rotate.
        degrees: A quarter turn count in degrees; other values are rejected by the type
            checker, not at runtime.

    Returns:
        A new symbol with arc angles normalised into [0, 360) and port directions turned
        the same way (N to E to S to W).
    """
    return _map_symbol(
        symbol,
        _ROTATIONS[degrees],
        lambda start, end: ((start + degrees) % 360 + 0.0, (end + degrees) % 360 + 0.0),
    )


@deal.pure
def mirror(symbol: Symbol, axis: Literal["x", "y"]) -> Symbol:
    """Return the symbol mirrored about the origin.

    Args:
        symbol: The symbol to mirror.
        axis: "x" flips left-right (x becomes -x); "y" flips top-bottom (y becomes -y).
            Other values are rejected by the type checker, not at runtime.

    Returns:
        A new symbol. Arcs keep their clockwise sweep, so start and end swap places, and both
        angles are normalised into [0, 360). Port directions flip with the geometry.
    """
    if axis == "x":
        return _map_symbol(
            symbol,
            _MIRROR_X,
            lambda start, end: ((180 - end) % 360 + 0.0, (180 - start) % 360 + 0.0),
        )
    return _map_symbol(symbol, _MIRROR_Y, lambda start, end: (-end % 360 + 0.0, -start % 360 + 0.0))
