"""Geometry primitives, in module units with SVG axes (x right, y down)."""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Self

import deal


class Direction(Enum):
    """Compass direction, with the unit vector as its value."""

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


class Anchor(Enum):
    """Horizontal text anchoring."""

    START = "start"
    MIDDLE = "middle"
    END = "end"


@dataclass(frozen=True, slots=True)
class Point:
    """A position in module units."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Line:
    """A straight segment."""

    start: Point
    end: Point
    weight: Weight = Weight.NORMAL


@dataclass(frozen=True, slots=True)
class Polyline:
    """A chain of segments, optionally closed and filled."""

    points: tuple[Point, ...]
    closed: bool = False
    fill: Fill = Fill.NONE
    weight: Weight = Weight.NORMAL


@dataclass(frozen=True, slots=True)
class Circle:
    """A circle, optionally filled."""

    center: Point
    radius: float
    fill: Fill = Fill.NONE
    weight: Weight = Weight.NORMAL


@dataclass(frozen=True, slots=True)
class Arc:
    """A circular arc swept clockwise on screen from start_deg to end_deg."""

    center: Point
    radius: float
    start_deg: float
    end_deg: float
    weight: Weight = Weight.NORMAL


@dataclass(frozen=True, slots=True)
class Text:
    """A text label; height is in module units."""

    content: str
    position: Point
    height: float = 1.0
    anchor: Anchor = Anchor.MIDDLE


Element = Line | Polyline | Circle | Arc | Text

_RIGHT_ANGLE_COS_SIN = {0: (1.0, 0.0), 90: (0.0, 1.0), 180: (-1.0, 0.0), 270: (0.0, -1.0)}


@deal.pure
def arc_point(arc: Arc, degrees: float) -> Point:
    """Return the point on the arc's circle at an angle, exact at multiples of 90 degrees.

    Args:
        arc: Supplies the centre and radius; its own angles are ignored.
        degrees: Angle clockwise on screen from +x.

    Returns:
        The point, with trig-derived coordinates rounded to 12 decimal places.
    """
    if degrees % 90 == 0:
        cos, sin = _RIGHT_ANGLE_COS_SIN[int(degrees % 360)]
    else:
        cos, sin = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return Point(
        round(arc.center.x + arc.radius * cos, 12),
        round(arc.center.y + arc.radius * sin, 12),
    )


@deal.pure
def arc_sweep(arc: Arc) -> float:
    """Return the clockwise sweep in degrees, in (0, 360]; equal angles are a full circle."""
    return (arc.end_deg - arc.start_deg) % 360 or 360
