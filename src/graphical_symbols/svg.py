"""Deterministic SVG rendering of symbols."""

import math
from xml.sax.saxutils import escape

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
    Weight,
    arc_point,
    arc_sweep,
)
from graphical_symbols.symbol import Box, Port, Symbol, bbox
from graphical_symbols.units import DEFAULT_MODULE_MM

_HALF_TURN = 180
_FULL_TURN = 360
_GROUP_OPEN = '<g fill="none" stroke="#000" stroke-linecap="butt" stroke-linejoin="miter">'


@deal.pure
def _num(value: float) -> str:
    """Format a number with at most 4 decimals, no trailing zeros and no negative zero."""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


@deal.pure
def _stroke(weight: Weight, fill: Fill = Fill.NONE) -> str:
    """Return the closing attributes of a stroked shape, with a black fill when solid."""
    solid = ' fill="#000"' if fill is Fill.SOLID else ""
    return f'stroke-width="{_num(weight.value)}"{solid}/>'


@deal.pure
def _arc(arc: Arc) -> str:
    """Render an arc as a path, clockwise on screen from its start to its end angle.

    A full circle has coincident endpoints, which SVG draws as nothing, so it becomes two half
    arcs through the opposite point.
    """
    start = arc_point(arc, arc.start_deg)
    sweep = arc_sweep(arc)
    r = _num(arc.radius)
    move = f"M {_num(start.x)} {_num(start.y)} A {r} {r} 0 "
    if sweep == _FULL_TURN:
        mid = arc_point(arc, arc.start_deg + _HALF_TURN)
        d = f"{move}0 1 {_num(mid.x)} {_num(mid.y)} A {r} {r} 0 0 1 {_num(start.x)} {_num(start.y)}"
    else:
        end = arc_point(arc, arc.end_deg)
        large = 1 if sweep > _HALF_TURN else 0
        d = f"{move}{large} 1 {_num(end.x)} {_num(end.y)}"
    return f'<path d="{d}" {_stroke(arc.weight)}'


@deal.pure
def _text(text: Text) -> str:
    """Render a text label, anchored as requested, in black without a stroke."""
    return (
        f'<text x="{_num(text.position.x)}" y="{_num(text.position.y)}" '
        f'font-size="{_num(text.height)}" text-anchor="{text.anchor.value}" fill="#000" '
        f'stroke="none" font-family="sans-serif">{escape(text.content)}</text>'
    )


@deal.pure
def _element(element: Element) -> str:
    """Render one element as an SVG tag."""
    match element:
        case Line(start=s, end=e, weight=weight):
            return (
                f'<line x1="{_num(s.x)}" y1="{_num(s.y)}" x2="{_num(e.x)}" y2="{_num(e.y)}" '
                f"{_stroke(weight)}"
            )
        case Polyline(points=points, closed=closed, fill=fill, weight=weight):
            tag = "polygon" if closed else "polyline"
            pts = " ".join(f"{_num(p.x)},{_num(p.y)}" for p in points)
            return f'<{tag} points="{pts}" {_stroke(weight, fill)}'
        case Circle(center=c, radius=r, fill=fill, weight=weight):
            return (
                f'<circle cx="{_num(c.x)}" cy="{_num(c.y)}" r="{_num(r)}" {_stroke(weight, fill)}'
            )
        case Arc() as arc:
            return _arc(arc)
        case Text() as text:
            return _text(text)


@deal.pure
def _label_at(port: Port) -> Point:
    """Return the centre of a port's id label, one module out along the port direction."""
    return Point(port.position.x + port.direction.dx, port.position.y + port.direction.dy)


@deal.pure
def _extent(symbol: Symbol, *, annotate: bool) -> Box:
    """Return the bbox, unioned with every port label box when annotating.

    A label box is centred on the label point, with half-width 0.3 M per id character and
    half-height 0.3 M (font-size 0.6).
    """
    box = bbox(symbol)
    if not annotate:
        return box
    boxes = [box]
    for port in symbol.ports:
        c = _label_at(port)
        half_w = 0.3 * len(port.id)
        boxes.append(Box(Point(c.x - half_w, c.y - 0.3), Point(c.x + half_w, c.y + 0.3)))
    return Box(
        Point(min(b.min.x for b in boxes), min(b.min.y for b in boxes)),
        Point(max(b.max.x for b in boxes), max(b.max.y for b in boxes)),
    )


@deal.pure
def _port(port: Port) -> tuple[str, str]:
    """Render a port marker and its id label, one module out along the port direction."""
    p = port.position
    marker = (
        f'<circle class="port" cx="{_num(p.x)}" cy="{_num(p.y)}" r="0.2" fill="#d00" '
        'stroke="none"/>'
    )
    label_at = _label_at(port)
    label = (
        f'<text class="port-id" x="{_num(label_at.x)}" y="{_num(label_at.y)}" font-size="0.6" '
        'text-anchor="middle" dominant-baseline="central" fill="#d00" stroke="none" '
        f'font-family="sans-serif">{escape(port.id)}</text>'
    )
    return marker, label


@deal.pure
def _annotation(symbol: Symbol, view: tuple[float, float, float, float]) -> list[str]:
    """Return the annotation group: integer grid dots, the bbox outline and port markers."""
    x, y, w, h = view
    box = bbox(symbol)
    lines = ['<g class="annotation">']
    lines.extend(
        f'<circle class="grid" cx="{gx}" cy="{gy}" r="0.06" fill="#888" stroke="none"/>'
        for gy in range(math.ceil(y), math.floor(y + h) + 1)
        for gx in range(math.ceil(x), math.floor(x + w) + 1)
    )
    lines.append(
        f'<rect class="bbox" x="{_num(box.min.x)}" y="{_num(box.min.y)}" '
        f'width="{_num(box.width)}" height="{_num(box.height)}" fill="none" stroke="#0a0" '
        'stroke-width="0.05" stroke-dasharray="0.2 0.2"/>'
    )
    for port in symbol.ports:
        lines.extend(_port(port))
    lines.append("</g>")
    return lines


@deal.pure
def to_svg(
    symbol: Symbol,
    *,
    module_mm: float = DEFAULT_MODULE_MM,
    margin: float = 1.0,
    annotate: bool = False,
) -> str:
    """Render a symbol as an SVG document.

    The viewBox is in module units, the symbol extent grown by margin on every side; width and
    height are the viewBox size times module_mm, in mm. The extent is the bbox, and with
    annotate it is also unioned with every port label box (centred one module out along the
    port direction, half-width 0.3 per id character, half-height 0.3), so no label is clipped.

    Args:
        symbol: The symbol to render.
        module_mm: Millimetres per module unit.
        margin: Empty space around the extent, in module units.
        annotate: Add grid dots at every whole module, the bbox outline and port markers.

    Returns:
        The SVG text, ending with a single newline.
    """
    extent = _extent(symbol, annotate=annotate)
    view = (
        extent.min.x - margin,
        extent.min.y - margin,
        extent.width + 2 * margin,
        extent.height + 2 * margin,
    )
    root = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_num(view[2] * module_mm)}mm" height="{_num(view[3] * module_mm)}mm" '
        f'viewBox="{" ".join(_num(v) for v in view)}">'
    )
    lines = [
        root,
        f"<title>{escape(symbol.name)}</title>",
        _GROUP_OPEN,
        *(_element(e) for e in symbol.elements),
        "</g>",
    ]
    if annotate:
        lines.extend(_annotation(symbol, view))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"
