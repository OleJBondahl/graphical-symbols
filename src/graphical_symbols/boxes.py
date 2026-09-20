"""The body, slot and keep-out boxes of a symbol."""

import math

import deal

from graphical_symbols.geometry import (
    Arc,
    Box,
    Circle,
    Direction,
    Element,
    Line,
    Point,
    Polyline,
    Text,
    arc_point,
    arc_sweep,
)
from graphical_symbols.model import Slot, Symbol

_AXIS_ANGLES = (0, 90, 180, 270)
_FULL_TURN = 360
_TEXT_WIDTH_PER_HEIGHT = 0.6
_ORIGIN_BOX = Box(Point(0, 0), Point(0, 0))


@deal.pure
def _extent_points(element: Element) -> tuple[Point, ...]:
    """Return points whose bounding box is the element's extent, ignoring stroke width.

    An arc with a non-finite angle has no swept extent and counts as its centre.
    """
    match element:
        case Line(start=start, end=end):
            return (start, end)
        case Polyline(points=points):
            return points
        case Circle(center=c, radius=r):
            return (Point(c.x - r, c.y - r), Point(c.x + r, c.y + r))
        case Arc() as arc:
            if not (math.isfinite(arc.start_deg) and math.isfinite(arc.end_deg)):
                return (arc.center,)
            start, end = arc.start_deg % _FULL_TURN, arc.end_deg % _FULL_TURN
            sweep = arc_sweep(arc)
            extremes = tuple(a for a in _AXIS_ANGLES if (a - start) % _FULL_TURN <= sweep)
            return tuple(arc_point(arc, a) for a in (start, end, *extremes))
        case Text(content=content, position=at, height=height):
            half_w = _TEXT_WIDTH_PER_HEIGHT * height * len(content) / 2
            return (
                Point(at.x - half_w, at.y - height / 2),
                Point(at.x + half_w, at.y + height / 2),
            )


@deal.pure
def _bounding(points: tuple[Point, ...]) -> Box:
    """Return the smallest box holding every point; no points give the origin box."""
    if not points:
        return _ORIGIN_BOX
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return Box(Point(min(xs), min(ys)), Point(max(xs), max(ys)))


@deal.pure
def element_box(element: Element) -> Box:
    """Return the extent of one element.

    A line or polyline extends over its points, a circle over its full diameter, an arc over its
    true swept extent, and text is a box centred on its position, `height` tall and `0.6 * height`
    per character wide. Stroke width is ignored. A polyline without points has the origin box.
    """
    return _bounding(_extent_points(element))


@deal.pure
def body_box(symbol: Symbol) -> Box:
    """Return the union of the element boxes; a symbol without elements has the origin box."""
    return _bounding(tuple(p for e in symbol.elements for p in _extent_points(e)))


@deal.pure
def slot_box(slot: Slot) -> Box:
    """Return the box a slot reserves: it grows from the slot point towards its side.

    E and W grow horizontally and are vertically centred; N grows up and S grows down and both
    are horizontally centred. The box is never rotated; only the point and side are.
    """
    x, y = slot.position.x, slot.position.y
    w, h = slot.box
    match slot.side:
        case Direction.E:
            return Box(Point(x, y - h / 2), Point(x + w, y + h / 2))
        case Direction.W:
            return Box(Point(x - w, y - h / 2), Point(x, y + h / 2))
        case Direction.N:
            return Box(Point(x - w / 2, y - h), Point(x + w / 2, y))
        case Direction.S:
            return Box(Point(x - w / 2, y), Point(x + w / 2, y + h))


@deal.pure
def keepout_box(symbol: Symbol) -> Box:
    """Return the body box united with every slot box."""
    boxes = (body_box(symbol), *(slot_box(s) for s in symbol.slots))
    return _bounding(tuple(p for b in boxes for p in (b.min, b.max)))
