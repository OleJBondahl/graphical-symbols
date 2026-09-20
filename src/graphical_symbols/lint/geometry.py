"""Geometry-group rules, and `point_on_geometry`, which the port and anchor rules share."""

import math
from itertools import pairwise

import deal

from graphical_symbols.geometry import (
    Arc,
    Circle,
    Element,
    Fill,
    Line,
    Point,
    Polyline,
    Text,
    arc_point,
    arc_sweep,
)
from graphical_symbols.lint.registry import rule_finding
from graphical_symbols.model import Finding, Symbol
from graphical_symbols.units import GRID_DIVISION

# The distance under which a point counts as on a curve; the guide's tolerance for derived values.
TOLERANCE = 1e-9
_MAX_TEXT_HEIGHT = 1
_FULL_TURN = 360
_PER_GRID = round(1 / GRID_DIVISION)


@deal.pure
def _on_grid(value: float) -> bool:
    """Return whether a value is a multiple of the drawing grid.

    Exact: 0.125 is a power of two, so `value * 8` loses nothing, and NaN and infinity are not
    multiples. Multiplying instead of dividing cannot overflow into an exception.
    """
    return (value * _PER_GRID).is_integer()


@deal.pure
def _grid_values(element: Element) -> tuple[tuple[str, float], ...]:
    """Return the labelled values of an element that must be on the drawing grid."""
    match element:
        case Line(start=start, end=end):
            return (
                ("start.x", start.x),
                ("start.y", start.y),
                ("end.x", end.x),
                ("end.y", end.y),
            )
        case Polyline(points=points):
            return tuple(
                (f"points[{i}].{axis}", value)
                for i, p in enumerate(points)
                for axis, value in (("x", p.x), ("y", p.y))
            )
        case Circle(center=c, radius=r) | Arc(center=c, radius=r):
            return (("center.x", c.x), ("center.y", c.y), ("radius", r))
        case Text(position=at, height=height):
            return (("position.x", at.x), ("position.y", at.y), ("height", height))


@deal.pure
def _off_grid(location: str, values: tuple[tuple[str, float], ...]) -> tuple[Finding, ...]:
    """Return one finding naming every value that is not on the grid, or none if all are."""
    bad = [f"{label} {value!r}" for label, value in values if not _on_grid(value)]
    if not bad:
        return ()
    message = f"not a multiple of {GRID_DIVISION}: {', '.join(bad)}"
    return (rule_finding("off-drawing-grid", message, location),)


@deal.pure
def off_drawing_grid(symbol: Symbol) -> tuple[Finding, ...]:
    """Check every element value, anchor, slot point and slot box size against the drawing grid.

    Element values are coordinates, radii, text positions and heights, not arc angles. Port
    positions are on the wiring grid, which `port-off-wiring-grid` checks. One finding per
    element, anchor or slot, naming each value that is off.
    """
    return (
        *(
            f
            for i, element in enumerate(symbol.elements)
            for f in _off_grid(f"elements[{i}]", _grid_values(element))
        ),
        *(
            f
            for i, anchor in enumerate(symbol.anchors)
            for f in _off_grid(
                f"anchors[{i}]",
                (("position.x", anchor.position.x), ("position.y", anchor.position.y)),
            )
        ),
        *(
            f
            for slot in symbol.slots
            for f in _off_grid(
                f"slots.{slot.id}",
                (
                    ("position.x", slot.position.x),
                    ("position.y", slot.position.y),
                    ("box.width", slot.box[0]),
                    ("box.height", slot.box[1]),
                ),
            )
        ),
    )


@deal.pure
def _problem(element: Element) -> str | None:
    """Return what is degenerate about an element, or None."""
    match element:
        case Line(start=start, end=end) if start == end:
            return "a line of zero length"
        case Circle(radius=r) | Arc(radius=r) if r <= 0:
            return f"a radius of {r!r}, which is not positive"
        case Polyline(points=points, closed=closed) if len(points) < (3 if closed else 2):
            return f"{len(points)} point(s) in a {'closed ' if closed else ''}polyline"
        case Arc(start_deg=start, end_deg=end) if start % _FULL_TURN == end % _FULL_TURN:
            return "an arc whose start and end angle are equal"
    return None


@deal.pure
def degenerate(symbol: Symbol) -> tuple[Finding, ...]:
    """Report elements that draw nothing or repeat, and slot boxes with a non-positive side.

    A zero-length line, a circle or arc with a radius of zero or less, a polyline with fewer than
    2 points (3 when closed), an arc whose angles are equal after normalising to [0, 360), and an
    element exactly equal to an earlier one, which is reported at the later copy.
    """
    first_seen: dict[Element, int] = {}
    found: list[Finding] = []
    for i, element in enumerate(symbol.elements):
        if (problem := _problem(element)) is not None:
            found.append(rule_finding("degenerate", problem, f"elements[{i}]"))
        if element in first_seen:
            message = f"an exact duplicate of elements[{first_seen[element]}]"
            found.append(rule_finding("degenerate", message, f"elements[{i}]"))
        else:
            first_seen[element] = i
    found.extend(
        rule_finding(
            "degenerate",
            f"a slot box of {slot.box[0]!r} by {slot.box[1]!r} has a side that is not positive",
            f"slots.{slot.id}",
        )
        for slot in symbol.slots
        if slot.box[0] <= 0 or slot.box[1] <= 0
    )
    return tuple(found)


@deal.pure
def text_too_large(symbol: Symbol) -> tuple[Finding, ...]:
    """Report every text element taller than 1 M."""
    return tuple(
        rule_finding(
            "text-too-large",
            f"text {element.content!r} is {element.height!r} M tall; the limit is 1 M",
            f"elements[{i}]",
        )
        for i, element in enumerate(symbol.elements)
        if isinstance(element, Text) and element.height > _MAX_TEXT_HEIGHT
    )


@deal.pure
def segments(points: tuple[Point, ...], *, closed: bool) -> tuple[tuple[Point, Point], ...]:
    """Return the segments of a chain of points, plus the closing one; a lone point is a dot."""
    if len(points) == 1:
        return ((points[0], points[0]),)
    chain = tuple(pairwise(points))
    return (*chain, (points[-1], points[0])) if closed and points else chain


@deal.pure
def _near_segment(point: Point, start: Point, end: Point) -> bool:
    """Return whether the point is within the tolerance of a segment; a zero-length one is a dot."""
    dx, dy = end.x - start.x, end.y - start.y
    length_squared = dx * dx + dy * dy
    along = 0.0
    if length_squared > 0:
        along = max(
            0.0, min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared)
        )
    return (
        math.hypot(point.x - (start.x + along * dx), point.y - (start.y + along * dy)) <= TOLERANCE
    )


@deal.pure
def _near(point: Point, other: Point) -> bool:
    """Return whether two points are within the tolerance of each other."""
    return math.hypot(point.x - other.x, point.y - other.y) <= TOLERANCE


@deal.pure
def _inside(point: Point, corners: tuple[Point, ...]) -> bool:
    """Return whether a point is inside a polygon by the even-odd rule; the edge is not tested."""
    crossings = sum(
        1
        for a, b in segments(corners, closed=True)
        if (a.y > point.y) != (b.y > point.y)
        and point.x < a.x + (point.y - a.y) * (b.x - a.x) / (b.y - a.y)
    )
    return crossings % 2 == 1


@deal.pure
def _on_arc(point: Point, arc: Arc) -> bool:
    """Return whether the point is on the arc's swept curve, its two end points included."""
    if abs(math.hypot(point.x - arc.center.x, point.y - arc.center.y) - arc.radius) > TOLERANCE:
        return False
    angle = math.degrees(math.atan2(point.y - arc.center.y, point.x - arc.center.x))
    if (angle - arc.start_deg) % _FULL_TURN <= arc_sweep(arc):
        return True
    ends = (arc_point(arc, arc.start_deg % _FULL_TURN), arc_point(arc, arc.end_deg % _FULL_TURN))
    return any(_near(point, end) for end in ends)


@deal.pure
def _on_chain(
    point: Point, points: tuple[Point, ...], *, closed: bool, endpoints_only: bool
) -> bool:
    """Return whether a point is on a line or polyline; only at its ends if it is open and asked."""
    if endpoints_only and not closed:
        return bool(points) and (_near(point, points[0]) or _near(point, points[-1]))
    return any(_near_segment(point, a, b) for a, b in segments(points, closed=closed))


@deal.pure
def _on_element(point: Point, element: Element, *, endpoints_only: bool) -> bool:
    """Return whether a point is on one element; text is never geometry."""
    match element:
        case Line(start=start, end=end):
            return _on_chain(point, (start, end), closed=False, endpoints_only=endpoints_only)
        case Polyline(points=points, closed=closed, fill=fill):
            filled = closed and fill is Fill.SOLID and _inside(point, points)
            return filled or _on_chain(point, points, closed=closed, endpoints_only=endpoints_only)
        case Circle(center=c, radius=r, fill=fill):
            distance = math.hypot(point.x - c.x, point.y - c.y)
            return abs(distance - r) <= TOLERANCE or (fill is Fill.SOLID and distance <= r)
        case Arc():
            return _on_arc(point, element)
        case Text():
            return False


@deal.pure
def point_on_geometry(
    point: Point, elements: tuple[Element, ...], *, endpoints_only: bool = False
) -> bool:
    """Return whether a point is on the geometry of any element, within 1e-9.

    On a line or polyline segment, on a circle or arc curve, on a closed polyline's outline, or
    inside a filled circle or a filled closed polyline (decision D5). A text element is not
    geometry.

    Args:
        point: The point to test.
        elements: The symbol's elements.
        endpoints_only: Count only the ends of a line and of an open polyline; circles, arcs and
            closed polylines stay whole. This is what a port needs, an anchor does not.
    """
    return any(_on_element(point, element, endpoints_only=endpoints_only) for element in elements)
