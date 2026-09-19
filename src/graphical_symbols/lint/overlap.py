"""Overlap of a shape with an open rectangle, the test behind the slot and wire-lane rules.

The guide (section 3) says two shapes overlap when their open interiors intersect, so touching
along an edge or at a corner is not overlap. For this test a stroke is a zero-width curve, a filled
shape is its area, and an unfilled closed outline is only its outline. The rectangle is a slot
box or a wire lane and is always open: its own boundary never counts.

Segments are tested exactly, with rational arithmetic, so a line through a corner of the
rectangle is touching however inexact its slope. A circle is compared by squared distances,
which are exact on the drawing grid. Arcs need trigonometry and use the tolerance of 1e-9.
Everything here is total: any float, NaN and infinity included, gives a bool and never raises;
a shape with non-finite numbers overlaps nothing.
"""

import math
from fractions import Fraction
from itertools import pairwise

import deal

from graphical_symbols.boxes import element_box
from graphical_symbols.geometry import (
    Arc,
    Box,
    Circle,
    Direction,
    Element,
    Fill,
    Line,
    Point,
    Polyline,
    Text,
    arc_point,
    arc_sweep,
)
from graphical_symbols.lint.geometry import TOLERANCE

# Half the width of a wire lane, in module units (guide section 8, point 3).
LANE_HALF_WIDTH = 0.25
_FULL_TURN = 360
_MIN_POLYGON_POINTS = 3
_WIDE = (Fraction(-1), Fraction(2))

_Exact = tuple[Fraction, Fraction]


@deal.pure
def _finite(*values: float) -> bool:
    """Return whether every value is a finite number."""
    return all(math.isfinite(v) for v in values)


@deal.pure
def _has_area(rect: Box) -> bool:
    """Return whether the rectangle has an interior; NaN, zero and negative sizes have none."""
    return rect.min.x < rect.max.x and rect.min.y < rect.max.y


@deal.pure
def _corners(rect: Box) -> tuple[float, float, float, float]:
    """Return the four bounds of a rectangle as (min x, min y, max x, max y)."""
    return rect.min.x, rect.min.y, rect.max.x, rect.max.y


@deal.pure
def boxes_overlap(a: Box, b: Box) -> bool:
    """Return whether the open interiors of two boxes intersect; a box with no area has none."""
    return max(a.min.x, b.min.x) < min(a.max.x, b.max.x) and max(a.min.y, b.min.y) < min(
        a.max.y, b.max.y
    )


@deal.pure
def wire_lane(position: Point, direction: Direction, frame: Box) -> Box:
    """Return the wire lane of a port, clipped to a finite frame.

    The lane is the open region `position + t * d + u * n` with `t > 0` and `|u| < 0.25`; it is
    unbounded, so it runs here from the port to the edge of `frame`, which must reach past
    everything the lane is tested against.
    """
    x, y = position.x, position.y
    match direction:
        case Direction.N:
            return Box(Point(x - LANE_HALF_WIDTH, frame.min.y), Point(x + LANE_HALF_WIDTH, y))
        case Direction.S:
            return Box(Point(x - LANE_HALF_WIDTH, y), Point(x + LANE_HALF_WIDTH, frame.max.y))
        case Direction.E:
            return Box(Point(x, y - LANE_HALF_WIDTH), Point(frame.max.x, y + LANE_HALF_WIDTH))
        case Direction.W:
            return Box(Point(frame.min.x, y - LANE_HALF_WIDTH), Point(x, y + LANE_HALF_WIDTH))


@deal.pure
def _edges(points: tuple[Point, ...], *, closed: bool) -> tuple[tuple[Point, Point], ...]:
    """Return the segments of a chain of points, plus the closing one; a lone point is a dot."""
    if len(points) == 1:
        return ((points[0], points[0]),)
    chain = tuple(pairwise(points))
    return (*chain, (points[-1], points[0])) if closed and points else chain


@deal.pure
def _clip(
    start: Fraction, step: Fraction, low: Fraction, high: Fraction
) -> tuple[Fraction, Fraction] | None:
    """Return the open range of t where `start + t * step` is in (low, high), or None.

    A step of zero allows every t if the start is inside, returned as a range wider than [0, 1].
    """
    if step == 0:
        return _WIDE if low < start < high else None
    first, second = (low - start) / step, (high - start) / step
    return (min(first, second), max(first, second))


@deal.pure
def _segment_meets(a: Point, b: Point, rect: Box) -> bool:
    """Return whether the closed segment a-b meets the open rectangle; rectangle has an area.

    Clips the segment `a + t * (b - a)`, `0 <= t <= 1`, against the open interval of each axis with
    exact fractions: it meets the rectangle when the open range of t is non-empty and reaches
    into [0, 1]. Ending on the boundary, running along it and touching a corner all fail.
    """
    numbers = (a.x, a.y, b.x, b.y, rect.min.x, rect.min.y, rect.max.x, rect.max.y)
    if not _finite(*numbers):
        return False
    ax, ay, bx, by, x0, y0, x1, y1 = (Fraction(n) for n in numbers)
    x_range, y_range = _clip(ax, bx - ax, x0, x1), _clip(ay, by - ay, y0, y1)
    if x_range is None or y_range is None:
        return False
    low, high = max(x_range[0], y_range[0]), min(x_range[1], y_range[1])
    return low < high and low < 1 and high > 0


@deal.pure
def _inside(point: _Exact, corners: tuple[Point, ...]) -> bool:
    """Return whether an exact point is inside a polygon by the even-odd rule; edges not tested."""
    px, py = point
    inside = False
    for a, b in _edges(corners, closed=True):
        ay, by = Fraction(a.y), Fraction(b.y)
        if (ay > py) != (by > py):
            ax, bx = Fraction(a.x), Fraction(b.x)
            inside ^= px < ax + (py - ay) * (bx - ax) / (by - ay)
    return inside


@deal.pure
def _polyline_meets(polyline: Polyline, rect: Box) -> bool:
    """Return whether a polyline's outline, or its area if it is closed and filled, meets rect.

    A filled closed polyline covers its area by the even-odd rule. If no edge enters the open
    rectangle, the rectangle is wholly inside or wholly outside, so its centre decides. An open
    polyline is only a stroke, however it is filled.
    """
    points = polyline.points
    if any(_segment_meets(a, b, rect) for a, b in _edges(points, closed=polyline.closed)):
        return True
    numbers = (*_corners(rect), *(v for p in points for v in (p.x, p.y)))
    solid = polyline.closed and polyline.fill is Fill.SOLID and len(points) >= _MIN_POLYGON_POINTS
    if not (solid and _finite(*numbers)):
        return False
    x0, y0, x1, y1 = (Fraction(n) for n in numbers[:4])
    return _inside(((x0 + x1) / 2, (y0 + y1) / 2), points)


@deal.pure
def _circle_meets(circle: Circle, rect: Box) -> bool:
    """Return whether a circle's outline, or its disk if it is filled, meets the open rectangle.

    The outline meets it exactly when the radius lies strictly between the distance from the
    centre to the nearest and to the farthest point of the rectangle, and the disk when the
    nearest point is closer than the radius. Squared distances are compared: no root, no tolerance.
    A circle whose radius is not a positive number draws nothing.
    """
    c, r = circle.center, circle.radius
    if not (r > 0 and _finite(c.x, c.y, r)):
        return False
    near_x = max(rect.min.x - c.x, 0.0, c.x - rect.max.x)
    near_y = max(rect.min.y - c.y, 0.0, c.y - rect.max.y)
    far_x = max(abs(c.x - rect.min.x), abs(c.x - rect.max.x))
    far_y = max(abs(c.y - rect.min.y), abs(c.y - rect.max.y))
    near, far = near_x * near_x + near_y * near_y, far_x * far_x + far_y * far_y
    if circle.fill is Fill.SOLID:
        return near < r * r
    return near < r * r < far


@deal.pure
def _crossings(
    centre: float, radius: float, lines: tuple[float, float], *, x_axis: bool
) -> list[float]:
    """Return the angles in degrees where a circle crosses the two lines of one axis.

    A vertical line `x = v` is met where `cos t = (v - centre) / radius` and a horizontal one where
    `sin t = ...`; a line that only misses by rounding, within the tolerance, still counts as met.
    """
    angles: list[float] = []
    for line in lines:
        ratio = (line - centre) / radius
        if abs(ratio) <= 1 + TOLERANCE:
            ratio = max(-1.0, min(1.0, ratio))
            if x_axis:
                angle = math.degrees(math.acos(ratio))
                angles += [angle, -angle]
            else:
                angle = math.degrees(math.asin(ratio))
                angles += [angle, 180 - angle]
    return angles


@deal.pure
def _arc_meets(arc: Arc, rect: Box) -> bool:
    """Return whether an arc's curve meets the open rectangle.

    The circle is cut at every angle where it crosses one of the four lines of the rectangle, and
    at the ends of the sweep. Between two neighbouring cuts the curve is wholly inside or wholly
    outside the rectangle, so the middle of each piece decides; it counts as inside only if it is
    more than 1e-9 clear of every edge, so an arc that grazes an edge is touching.
    """
    c, r = arc.center, arc.radius
    numbers = (c.x, c.y, r, arc.start_deg, arc.end_deg, *_corners(rect))
    if not (r > 0 and _finite(*numbers)):
        return False
    start, sweep = arc.start_deg % _FULL_TURN, arc_sweep(arc)
    angles = (
        *_crossings(c.x, r, (rect.min.x, rect.max.x), x_axis=True),
        *_crossings(c.y, r, (rect.min.y, rect.max.y), x_axis=False),
    )
    cuts = sorted({0.0, sweep, *(u for a in angles if (u := (a - start) % _FULL_TURN) < sweep)})
    for low, high in pairwise(cuts):
        p = arc_point(arc, start + (low + high) / 2)
        if (
            rect.min.x + TOLERANCE < p.x < rect.max.x - TOLERANCE
            and rect.min.y + TOLERANCE < p.y < rect.max.y - TOLERANCE
        ):
            return True
    return False


@deal.pure
def _text_meets(text: Text, rect: Box) -> bool:
    """Return whether a text element's box overlaps the rectangle.

    The box is `boxes.element_box`. Its width comes from the factor 0.6, which is not a binary
    fraction, so the box is first shrunk by the tolerance: an edge that only touches stays
    touching.
    """
    box = element_box(text)
    shrunk = Box(
        Point(box.min.x + TOLERANCE, box.min.y + TOLERANCE),
        Point(box.max.x - TOLERANCE, box.max.y - TOLERANCE),
    )
    return boxes_overlap(shrunk, rect)


@deal.pure
def overlaps_rect(element: Element, rect: Box) -> bool:
    """Return whether an element overlaps an open rectangle, by the guide's definition.

    Lines and polyline segments are zero-width curves; an open polyline is only its segments,
    however it is filled; a closed polyline is its outline, and if it is filled also its area (even-
    odd rule); a circle is its outline, or its disk if filled; an arc is its swept curve; text is
    a box (`boxes.element_box`). Touching the rectangle's edge or corner is not overlap, and a
    rectangle with no area is overlapped by nothing.

    Args:
        element: One element of a symbol.
        rect: The open rectangle, a slot box or a wire lane.
    """
    if not _has_area(rect):
        return False
    match element:
        case Line(start=start, end=end):
            return _segment_meets(start, end, rect)
        case Polyline():
            return _polyline_meets(element, rect)
        case Circle():
            return _circle_meets(element, rect)
        case Arc():
            return _arc_meets(element, rect)
        case Text():
            return _text_meets(element, rect)
