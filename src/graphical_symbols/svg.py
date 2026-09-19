"""Deterministic SVG rendering of symbols."""

import math
import re
from collections.abc import Mapping
from xml.sax.saxutils import escape

import deal

from graphical_symbols.boxes import body_box
from graphical_symbols.geometry import (
    Arc,
    Box,
    Circle,
    Element,
    Fill,
    Line,
    Point,
    Polyline,
    Style,
    Text,
    Weight,
    arc_point,
    arc_sweep,
)
from graphical_symbols.model import Port, Symbol
from graphical_symbols.units import DEFAULT_MODULE_MM

_HALF_TURN = 180
_FULL_TURN = 360
_MARGIN = 1.0
_DASHED = ' stroke-dasharray="0.5 0.25"'
_MAX_GRID_DOTS = 10_000
# What XML 1.0 cannot carry: most C0 controls, lone surrogates, U+FFFE and U+FFFF.
_XML_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\U0000fffe\U0000ffff]")
_GROUP_OPEN = '<g fill="none" stroke="#000" stroke-linecap="butt" stroke-linejoin="miter">'


@deal.pure
def _num(value: float) -> str:
    """Format a number with at most 4 decimals, no trailing zeros and no negative zero.

    NaN and infinity have no SVG spelling and are written as `0` (D32), so the output stays
    well formed for a hand-built symbol.
    """
    if not math.isfinite(value):
        return "0"
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


@deal.pure
def _content(text: str) -> str:
    r"""Make text safe as XML character data (D32).

    A character XML 1.0 cannot carry becomes U+FFFD. `&`, `<` and `>` become entities and a
    carriage return becomes `&#13;`, so no `\r` byte reaches the file and a parser reads it back.
    A line feed or a tab is left as it is: XML keeps both.
    """
    return escape(_XML_ILLEGAL.sub("\U0000fffd", text), {"\r": "&#13;"})


@deal.pure
def _stroke(weight: Weight, fill: Fill = Fill.NONE, style: Style = Style.SOLID) -> str:
    """Return the closing attributes of a stroked shape: dashed when asked, black when solid."""
    dashed = _DASHED if style is Style.DASHED else ""
    solid = ' fill="#000"' if fill is Fill.SOLID else ""
    return f'stroke-width="{_num(weight.value)}"{dashed}{solid}/>'


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
    return f'<path d="{d}" {_stroke(arc.weight, style=arc.style)}'


@deal.pure
def _text(text: Text) -> str:
    """Render a text label, middle-anchored, in black without a stroke."""
    return (
        f'<text x="{_num(text.position.x)}" y="{_num(text.position.y)}" '
        f'font-size="{_num(text.height)}" text-anchor="middle" fill="#000" '
        f'stroke="none" font-family="sans-serif">{_content(text.content)}</text>'
    )


@deal.pure
def _element(element: Element) -> str:
    """Render one element as an SVG tag."""
    match element:
        case Line(start=s, end=e, weight=weight, style=style):
            return (
                f'<line x1="{_num(s.x)}" y1="{_num(s.y)}" x2="{_num(e.x)}" y2="{_num(e.y)}" '
                f"{_stroke(weight, style=style)}"
            )
        case Polyline(points=points, closed=closed, fill=fill, weight=weight, style=style):
            tag = "polygon" if closed else "polyline"
            pts = " ".join(f"{_num(p.x)},{_num(p.y)}" for p in points)
            return f'<{tag} points="{pts}" {_stroke(weight, fill, style)}'
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
    """Return the body box, unioned with every port label box when annotating.

    A label box is centred on the label point, with half-width 0.3 M per id character and
    half-height 0.3 M (font-size 0.6).
    """
    box = body_box(symbol)
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
        f'font-family="sans-serif">{_content(port.id)}</text>'
    )
    return marker, label


@deal.pure
def _grid(view: tuple[float, float, float, float]) -> list[str]:
    """Return a dot at every whole module inside the view.

    A view that is not finite, or that holds more than 10 000 dots, gets no grid (D32): only a
    hand-built symbol reaches either, and a dot per module of it would not end.
    """
    x, y, w, h = view
    if not all(math.isfinite(v) for v in (x, y, x + w, y + h)):
        return []
    x0, x1, y0, y1 = math.ceil(x), math.floor(x + w), math.ceil(y), math.floor(y + h)
    if max(0, x1 - x0 + 1) * max(0, y1 - y0 + 1) > _MAX_GRID_DOTS:
        return []
    return [
        f'<circle class="grid" cx="{gx}" cy="{gy}" r="0.06" fill="#888" stroke="none"/>'
        for gy in range(y0, y1 + 1)
        for gx in range(x0, x1 + 1)
    ]


@deal.pure
def _annotation(symbol: Symbol, view: tuple[float, float, float, float]) -> list[str]:
    """Return the annotation group: integer grid dots, the body box outline and port markers."""
    box = body_box(symbol)
    lines = ['<g class="annotation">']
    lines.extend(_grid(view))
    lines.append(
        f'<rect class="body-box" x="{_num(box.min.x)}" y="{_num(box.min.y)}" '
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
    annotate: bool = False,
    texts: Mapping[str, str] | None = None,  # noqa: ARG001 - sample slot texts arrive with the full renderer
) -> str:
    """Render a symbol as an SVG document.

    The viewBox is in module units, the symbol extent grown by a margin of 1 on every side; width
    and height are the viewBox size times module_mm, in mm. The extent is the body box, and with
    annotate it is also unioned with every port label box (centred one module out along the
    port direction, half-width 0.3 per id character, half-height 0.3), so no label is clipped.

    Args:
        symbol: The symbol to render.
        module_mm: Millimetres per module unit.
        annotate: Add grid dots at every whole module, the body box outline and port markers.
        texts: Sample text per slot id; accepted for the final signature and not yet drawn.

    Returns:
        The SVG text, ending with a single newline.
    """
    extent = _extent(symbol, annotate=annotate)
    view = (
        extent.min.x - _MARGIN,
        extent.min.y - _MARGIN,
        extent.width + 2 * _MARGIN,
        extent.height + 2 * _MARGIN,
    )
    root = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_num(view[2] * module_mm)}mm" height="{_num(view[3] * module_mm)}mm" '
        f'viewBox="{" ".join(_num(v) for v in view)}">'
    )
    lines = [
        root,
        f"<title>{_content(symbol.name)}</title>",
        _GROUP_OPEN,
        *(_element(e) for e in symbol.elements),
        "</g>",
    ]
    if annotate:
        lines.extend(_annotation(symbol, view))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"
