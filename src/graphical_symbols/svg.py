"""Deterministic SVG rendering of symbols."""

import math
import re
from collections.abc import Mapping, Sequence
from xml.sax.saxutils import escape

import deal

from graphical_symbols.boxes import body_box, keepout_box, slot_box
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
    Style,
    Text,
    Weight,
    arc_point,
    arc_sweep,
)
from graphical_symbols.model import Anchor, Port, Slot, Symbol
from graphical_symbols.units import DEFAULT_MODULE_MM

_HALF_TURN = 180
_FULL_TURN = 360
_MARGIN = 1.0
_DASHED = ' stroke-dasharray="0.5 0.25"'
_MAX_GRID_DOTS = 10_000

# Annotation sizes and colours (D33). Port and anchor label boxes are 1 em wide per character, a
# little wider than the glyphs on purpose, so a label never touches the edge of the view; slot
# label boxes are 0.6 em per character (0.18 M at size 0.3), the guide's own text width.
_LANE_HALF_WIDTH = 0.25
_PORT_FONT = 0.6
_PORT_COLOUR = "#d00"
_ANCHOR_FONT = 0.4
_ANCHOR_HALF = 0.2
_ANCHOR_LABEL_GAP = 0.75
_ANCHOR_COLOUR = "#088"
_SLOT_FONT = 0.3
_SLOT_LABEL_WIDTH = 0.18
_SLOT_COLOUR = "#06c"
_SAMPLE_COLOUR = "#c60"
_BODY_STYLE = 'fill="none" stroke="#0a0" stroke-width="0.05" stroke-dasharray="0.2 0.2"'
_KEEPOUT_STYLE = (
    'fill="none" stroke="#a0a" stroke-width="0.05" stroke-dasharray="0.2 0.2" '
    'stroke-dashoffset="0.2"'
)
_SLOT_STYLE = (
    f'fill="{_SLOT_COLOUR}" fill-opacity="0.12" stroke="{_SLOT_COLOUR}" stroke-width="0.03"'
)
_LANE_STYLE = f'fill="{_PORT_COLOUR}" fill-opacity="0.15" stroke="none"'

# Sample text (guide section 6). A capital is about 0.72 of the font size tall, so a baseline
# 0.36 below the slot point centres it there, and 0.72 below hangs it under the slot point.
_TEXT_WIDTH = 0.6
_SAMPLE_MAX_SIZE = 1.0
_CAP_HEIGHT = 0.72
_CAP_CENTRE = _CAP_HEIGHT / 2
_SAMPLE_ALIGN = {
    Direction.E: ("start", _CAP_CENTRE),
    Direction.W: ("end", _CAP_CENTRE),
    Direction.N: ("middle", 0.0),
    Direction.S: ("middle", _CAP_HEIGHT),
}
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
    """Render a text label, middle-anchored, in black without a stroke.

    The guide makes a text element a box centred on its position, so the baseline is a cap-centre
    below it (D33) and the capitals are centred on the position.
    """
    baseline = text.position.y + _CAP_CENTRE * text.height
    return (
        f'<text x="{_num(text.position.x)}" y="{_num(baseline)}" '
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
def _centred(at: Point, half_w: float, half_h: float) -> Box:
    """Return the box of the given half sizes around a point."""
    return Box(Point(at.x - half_w, at.y - half_h), Point(at.x + half_w, at.y + half_h))


@deal.pure
def _union(boxes: Sequence[Box]) -> Box:
    """Return the smallest box holding every box; the caller passes at least one."""
    return Box(
        Point(min(b.min.x for b in boxes), min(b.min.y for b in boxes)),
        Point(max(b.max.x for b in boxes), max(b.max.y for b in boxes)),
    )


@deal.pure
def _label(  # noqa: PLR0913 - one text tag is these six things
    css: str, at: Point, size: float, *, anchor: str, colour: str, content: str
) -> str:
    """Render one annotation or sample text; `at.y` is the baseline."""
    return (
        f'<text class="{css}" x="{_num(at.x)}" y="{_num(at.y)}" font-size="{_num(size)}" '
        f'text-anchor="{anchor}" fill="{colour}" stroke="none" font-family="sans-serif">'
        f"{_content(content)}</text>"
    )


@deal.pure
def _centred_label(css: str, at: Point, size: float, colour: str, content: str) -> str:
    """Render a middle-anchored text whose capitals are centred on `at` (D33)."""
    shifted = Point(at.x, at.y + _CAP_CENTRE * size)
    return _label(css, shifted, size, anchor="middle", colour=colour, content=content)


@deal.pure
def _rect(box: Box, css: str, style: str) -> str:
    """Render a box as a rect; a box turned inside out (a hand-built slot) has no size."""
    return (
        f'<rect class="{css}" x="{_num(box.min.x)}" y="{_num(box.min.y)}" '
        f'width="{_num(max(0.0, box.width))}" height="{_num(max(0.0, box.height))}" {style}/>'
    )


@deal.pure
def _label_at(port: Port) -> Point:
    """Return the centre of a port's id label, one module out along the port direction."""
    return Point(port.position.x + port.direction.dx, port.position.y + port.direction.dy)


@deal.pure
def _lane_start(port: Port) -> Box:
    """Return the port end of its lane: a segment 0.5 M wide across the direction."""
    d = port.direction
    return _centred(port.position, _LANE_HALF_WIDTH * abs(d.dy), _LANE_HALF_WIDTH * abs(d.dx))


@deal.pure
def _anchor_label_at(anchor: Anchor) -> Point:
    """Return the centre of an anchor's id label, 0.75 M out along the anchor direction."""
    d = anchor.direction
    return Point(
        anchor.position.x + _ANCHOR_LABEL_GAP * d.dx, anchor.position.y + _ANCHOR_LABEL_GAP * d.dy
    )


@deal.pure
def _slot_label_box(slot: Slot) -> Box:
    """Return the box a slot's id label takes: just above the top edge of the slot box."""
    box = slot_box(slot)
    return Box(
        Point(box.min.x, box.min.y - 4 * _SLOT_FONT / 3),
        Point(box.min.x + _SLOT_LABEL_WIDTH * len(slot.id), box.min.y),
    )


@deal.pure
def _annotation_boxes(symbol: Symbol) -> list[Box]:
    """Return every box the annotations occupy beyond the keep-out box, so nothing is clipped.

    A port label box is centred on the label point, half-width 0.3 M per id character and
    half-height 0.3 M (font-size 0.6); an anchor label box is 0.2 per character and 0.2 high; a
    lane counts from its start, 0.5 M wide.
    """
    boxes: list[Box] = []
    for port in symbol.ports:
        half = _PORT_FONT / 2
        boxes.append(_centred(_label_at(port), half * len(port.id), half))
        boxes.append(_lane_start(port))
    for anchor in symbol.anchors:
        half = _ANCHOR_FONT / 2
        boxes.append(_centred(anchor.position, _ANCHOR_HALF, _ANCHOR_HALF))
        boxes.append(_centred(_anchor_label_at(anchor), half * len(anchor.id), half))
    boxes.extend(_slot_label_box(slot) for slot in symbol.slots)
    return boxes


@deal.pure
def _slot_id(slot: Slot) -> str:
    """Return a slot's id, the sort key of the slots."""
    return slot.id


@deal.pure
def _slots_by_id(symbol: Symbol) -> list[Slot]:
    """Return the slots in id order (D33).

    Resolved JSON keeps slots in that order (D30), so a symbol read from a bundle must draw the
    same file as the one read from the sources.
    """
    return sorted(symbol.slots, key=_slot_id)


@deal.pure
def _sample_size(slot: Slot, content: str) -> float:
    """Return the font size of a sample text: the largest of at most 1 M that fits the slot box.

    It fits when `0.6 * size * characters <= width` and `size <= height`. The size is rounded down
    to 4 decimals, the precision of the output, so what is written still fits. Nothing to draw
    (no text, or a box without a positive size) gives 0.
    """
    w, h = slot.box
    if not content or not (w > 0 and h > 0):
        return 0.0
    size = min(_SAMPLE_MAX_SIZE, h, w / (_TEXT_WIDTH * len(content)))
    return math.floor(size * 10_000) / 10_000


@deal.pure
def _sampled(symbol: Symbol, texts: Mapping[str, str]) -> tuple[tuple[Slot, str, float], ...]:
    """Return the slots of the symbol that have a sample text, with the text and its size.

    A text for an id the symbol has no slot for is ignored; so is one that has nothing to draw.
    """
    found = []
    for slot in _slots_by_id(symbol):
        content = texts.get(slot.id, "")
        size = _sample_size(slot, content)
        if size > 0:
            found.append((slot, content, size))
    return tuple(found)


@deal.pure
def _sample_text(slot: Slot, content: str, size: float) -> str:
    """Render a sample text upright in its slot box, aligned by the slot side (guide section 6).

    E: start at the slot point, centred on its y. W: end at the slot point, centred on its y.
    N: middle, baseline on the slot point. S: middle, hanging below the slot point (D33).
    """
    anchor, baseline = _SAMPLE_ALIGN[slot.side]
    at = Point(slot.position.x, slot.position.y + baseline * size)
    return _label("sample-text", at, size, anchor=anchor, colour=_SAMPLE_COLOUR, content=content)


@deal.pure
def _slot(slot: Slot) -> list[str]:
    """Render a slot box, translucent, with its id just above it."""
    box = slot_box(slot)
    at = Point(box.min.x, box.min.y - _SLOT_FONT / 3)
    label = _label("slot-id", at, _SLOT_FONT, anchor="start", colour=_SLOT_COLOUR, content=slot.id)
    return [_rect(box, "slot-box", _SLOT_STYLE), label]


@deal.pure
def _anchor(anchor: Anchor) -> list[str]:
    """Render an anchor: a diamond on its position and its id beside it, along its direction."""
    x, y, r = _num(anchor.position.x), _num(anchor.position.y), _ANCHOR_HALF
    left, right = _num(anchor.position.x - r), _num(anchor.position.x + r)
    top, bottom = _num(anchor.position.y - r), _num(anchor.position.y + r)
    marker = (
        f'<path class="anchor" d="M {left} {y} L {x} {top} L {right} {y} L {x} {bottom} Z" '
        f'fill="{_ANCHOR_COLOUR}" stroke="none"/>'
    )
    label = _centred_label(
        "anchor-id", _anchor_label_at(anchor), _ANCHOR_FONT, _ANCHOR_COLOUR, anchor.id
    )
    return [marker, label]


@deal.pure
def _reach(here: float, low: float, high: float, step: int) -> float:
    """Return where a lane stops on one axis: the view edge it runs towards, or where it is."""
    if step > 0:
        return high
    return low if step < 0 else here


@deal.pure
def _lane(port: Port, view: tuple[float, float, float, float]) -> str:
    """Render the wire lane of a port: 0.5 M wide, from the port along its direction to the edge."""
    x, y, w, h = view
    start = _lane_start(port)
    d, p = port.direction, port.position
    far = Point(_reach(p.x, x, x + w, d.dx), _reach(p.y, y, y + h, d.dy))
    return _rect(_union([start, Box(far, far)]), "lane", _LANE_STYLE)


@deal.pure
def _port(port: Port) -> list[str]:
    """Render a port marker and its id label, one module out along the port direction."""
    p = port.position
    marker = (
        f'<circle class="port" cx="{_num(p.x)}" cy="{_num(p.y)}" r="0.2" fill="{_PORT_COLOUR}" '
        'stroke="none"/>'
    )
    label = _centred_label("port-id", _label_at(port), _PORT_FONT, _PORT_COLOUR, port.id)
    return [marker, label]


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
    """Return the annotation group (D33), in drawing order.

    The grid, the body box, the keep-out box, every slot box with its id, every anchor, the wire
    lane of every port, then every port marker with its id.
    """
    lines = ['<g class="annotation">', *_grid(view)]
    lines.append(_rect(body_box(symbol), "body-box", _BODY_STYLE))
    lines.append(_rect(keepout_box(symbol), "keepout-box", _KEEPOUT_STYLE))
    for slot in _slots_by_id(symbol):
        lines.extend(_slot(slot))
    for anchor in symbol.anchors:
        lines.extend(_anchor(anchor))
    lines.extend(_lane(port, view) for port in symbol.ports)
    for port in symbol.ports:
        lines.extend(_port(port))
    lines.append("</g>")
    return lines


@deal.pure
def _extent(symbol: Symbol, sampled: Sequence[tuple[Slot, str, float]], *, annotate: bool) -> Box:
    """Return what the view must hold, before the margin.

    Plain: the body box and the slot boxes of the sample texts. Annotated: the keep-out box and
    everything the annotations draw outside it (`_annotation_boxes`).
    """
    boxes = [keepout_box(symbol) if annotate else body_box(symbol)]
    boxes.extend(slot_box(slot) for slot, _, _ in sampled)
    if annotate:
        boxes.extend(_annotation_boxes(symbol))
    return _union(boxes)


@deal.pure
def to_svg(
    symbol: Symbol,
    *,
    module_mm: float = DEFAULT_MODULE_MM,
    annotate: bool = False,
    texts: Mapping[str, str] | None = None,
) -> str:
    """Render a symbol as an SVG document.

    The viewBox is in module units, the extent grown by a margin of 1 on every side; width and
    height are the viewBox size times module_mm, in mm. Plain, the extent is the body box; with
    annotate it is the keep-out box, every port label box, every anchor and its label, every slot
    label and the start of every lane, so no annotation is clipped. The elements are drawn first,
    then the annotations (in the order of `_annotation`), then the sample texts.

    Args:
        symbol: The symbol to render.
        module_mm: Millimetres per module unit.
        annotate: Draw the grid, the body and keep-out boxes, the slot boxes, the anchors and the
            ports with their ids and wire lanes.
        texts: Sample text per slot id. Each is drawn upright in its slot box (class
            `sample-text`) in the largest font of at most 1 M that fits the box; an id that is
            not a slot of the symbol is ignored. Drawn in both modes.

    Returns:
        The SVG text, ending with a single newline.
    """
    sampled = _sampled(symbol, texts or {})
    extent = _extent(symbol, sampled, annotate=annotate)
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
    if sampled:
        lines.extend(['<g class="samples">', *(_sample_text(*s) for s in sampled), "</g>"])
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


@deal.pure
def to_fragment(symbol: Symbol) -> str:
    """Render a symbol as a placeable SVG fragment: a `<g>` of its plain elements only.

    For embedding one placed symbol inside a larger document the caller assembles -- the caller
    wraps the result in its own `<g transform="...">` to position, orient and scale it; this
    function applies none of its own. No title, no annotations, no sample texts: built from the
    same element primitives `to_svg`'s plain mode uses (`_GROUP_OPEN` and `_element`), so a
    change to how one element renders never drifts between the two.

    Args:
        symbol: The symbol to render, already oriented and repeated by the caller (via
            `orient`/`repeat`), exactly as `to_svg` expects its own `symbol` argument.

    Returns:
        The `<g>...</g>` fragment text, ending with a single newline.
    """
    lines = [_GROUP_OPEN, *(_element(e) for e in symbol.elements), "</g>"]
    return "\n".join(lines) + "\n"
