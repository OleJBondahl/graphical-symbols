"""Symbol definitions and their extents."""

from dataclasses import dataclass
from enum import Enum

import deal

from graphical_symbols.errors import InvalidSymbolError
from graphical_symbols.geometry import (
    Arc,
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

_AXIS_ANGLES = (0, 90, 180, 270)


class Status(Enum):
    """Whether a symbol's geometry was checked against the standard's own drawing."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class Port:
    """A connection point on a symbol; the id is the only pin identity."""

    id: str
    position: Point
    direction: Direction
    description: str = ""


@dataclass(frozen=True, slots=True)
class Reference:
    """Where a symbol is defined in its standard."""

    standard: str
    number: str
    edition: str | None = None
    form: str | None = None


@dataclass(frozen=True, slots=True)
class Symbol:
    """A symbol definition, not a placement: it has no label, tag or position."""

    name: str
    reference: Reference
    elements: tuple[Element, ...]
    ports: tuple[Port, ...] = ()
    status: Status = Status.UNVERIFIED

    def __post_init__(self) -> None:
        """Reject a symbol without elements.

        Raises:
            InvalidSymbolError: If elements is empty. Nothing else is checked here, so the
                linter can inspect malformed symbols.
        """
        if not self.elements:
            msg = f"symbol {self.name!r} has no elements"
            raise InvalidSymbolError(msg)


@dataclass(frozen=True, slots=True)
class Box:
    """An axis-aligned rectangle."""

    min: Point
    max: Point

    @property
    def width(self) -> float:
        """Horizontal extent."""
        return self.max.x - self.min.x

    @property
    def height(self) -> float:
        """Vertical extent."""
        return self.max.y - self.min.y

    @property
    def center(self) -> Point:
        """Midpoint of the rectangle."""
        return Point((self.min.x + self.max.x) / 2, (self.min.y + self.max.y) / 2)


@deal.pure
def _element_points(element: Element) -> tuple[Point, ...]:
    """Return points whose bounding box is the element's extent."""
    match element:
        case Line(start=start, end=end):
            return (start, end)
        case Polyline(points=points):
            return points
        case Circle(center=c, radius=r):
            return (Point(c.x - r, c.y - r), Point(c.x + r, c.y + r))
        case Arc() as arc:
            sweep = arc_sweep(arc)
            extremes = tuple(a for a in _AXIS_ANGLES if (a - arc.start_deg) % 360 <= sweep)
            return tuple(arc_point(arc, a) for a in (arc.start_deg, arc.end_deg, *extremes))
        case Text(position=position):
            return (position,)


@deal.pure
def bbox(symbol: Symbol) -> Box:
    """Return the extents of all elements, ignoring stroke; text counts as its position only."""
    points = [p for element in symbol.elements for p in _element_points(element)]
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return Box(Point(min(xs), min(ys)), Point(max(xs), max(ys)))
