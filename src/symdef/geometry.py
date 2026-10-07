"""Geometry primitives, in module units with SVG axes (x right, y down)."""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Self


class Direction(Enum):
    """Compass direction, with the unit vector as its value.

    The axes are SVG's, so N is (0, -1) (up on screen) and S is (0, 1).
    """

    N = (0, -1)
    E = (1, 0)
    S = (0, 1)
    W = (-1, 0)

    @property
    def dx(self) -> int:
        """Horizontal component of the unit vector."""
        return self.value[0]

    @property
    def dy(self) -> int:
        """Vertical component of the unit vector."""
        return self.value[1]

    @property
    def opposite(self) -> Self:
        """The direction pointing the other way."""
        return type(self)((-self.dx, -self.dy))


class Weight(Enum):
    """Line weight; the value is the stroke width in module units."""

    NORMAL = 0.1
    THICK = 0.2


class Fill(Enum):
    """Whether a closed shape is filled."""

    NONE = "none"
    SOLID = "solid"


class Style(Enum):
    """Line style; dashed is drawn with a dash of 0.5 M and a gap of 0.25 M."""

    SOLID = "solid"
    DASHED = "dashed"


class Orientation(Enum):
    """One of the 8 orientations: an optional mirror (flip x), then a clockwise turn by n.

    `R<n>` turns by n degrees; `MR<n>` mirrors first, then turns. R0 is the symbol as defined.
    """

    R0 = "R0"
    R90 = "R90"
    R180 = "R180"
    R270 = "R270"
    MR0 = "MR0"
    MR90 = "MR90"
    MR180 = "MR180"
    MR270 = "MR270"


@dataclass(frozen=True, slots=True)
class Point:
    """A position in module units, x to the right and y downwards."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Box:
    """An axis-aligned rectangle in module units, from its min corner to its max corner."""

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


@dataclass(frozen=True, slots=True)
class Line:
    """A straight segment, optionally the lead of a port.

    Attributes:
        port: The id of the port this line is the lead of, or None for an ordinary line.
    """

    start: Point
    end: Point
    weight: Weight = Weight.NORMAL
    style: Style = Style.SOLID
    port: str | None = None


@dataclass(frozen=True, slots=True)
class Polyline:
    """A chain of segments through `points`, optionally closed and filled.

    Attributes:
        closed: Whether the last point joins back to the first.
        fill: Whether a closed polyline is filled.
    """

    points: tuple[Point, ...]
    closed: bool = False
    fill: Fill = Fill.NONE
    weight: Weight = Weight.NORMAL
    style: Style = Style.SOLID


@dataclass(frozen=True, slots=True)
class Circle:
    """A circle, optionally filled; the radius is in module units."""

    center: Point
    radius: float
    fill: Fill = Fill.NONE
    weight: Weight = Weight.NORMAL


@dataclass(frozen=True, slots=True)
class Arc:
    """A circular arc swept clockwise on screen from start_deg to end_deg.

    Angles are in degrees, measured clockwise on screen from +x (so 90 points down). Equal
    angles make a full circle.
    """

    center: Point
    radius: float
    start_deg: float
    end_deg: float
    weight: Weight = Weight.NORMAL
    style: Style = Style.SOLID


@dataclass(frozen=True, slots=True)
class Text:
    """A text label, always middle-anchored and upright; height is in module units.

    Attributes:
        position: The middle of the label.
    """

    content: str
    position: Point
    height: float = 1.0
    weight: Weight = Weight.NORMAL


Element = Line | Polyline | Circle | Arc | Text

_RIGHT_ANGLE_COS_SIN = {0: (1.0, 0.0), 90: (0.0, 1.0), 180: (-1.0, 0.0), 270: (0.0, -1.0)}


def arc_point(arc: Arc, degrees: float) -> Point:
    """Return the point on the arc's circle at an angle, exact at multiples of 90 degrees.

    Args:
        arc: Supplies the centre and radius; its own angles are ignored.
        degrees: Angle clockwise on screen from +x. A NaN or infinite angle has no direction, so
            it gives the centre (D32); files cannot carry one, only a hand-built arc can.

    Returns:
        The point, with trig-derived coordinates rounded to 12 decimal places.
    """
    if not math.isfinite(degrees):
        return arc.center
    if degrees % 90 == 0:
        cos, sin = _RIGHT_ANGLE_COS_SIN[int(degrees % 360)]
    else:
        cos, sin = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return Point(
        round(arc.center.x + arc.radius * cos, 12),
        round(arc.center.y + arc.radius * sin, 12),
    )


def arc_sweep(arc: Arc) -> float:
    """Return the clockwise sweep in degrees, in (0, 360]; equal angles are a full circle."""
    return (arc.end_deg - arc.start_deg) % 360 or 360
