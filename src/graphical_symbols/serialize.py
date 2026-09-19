"""Resolved output: a symbol or a library as plain data, and that data as canonical JSON text.

The resolved form is explicit (D11): every key that has a default is written, so a consumer in
another language needs no defaults and no composition. `to_json` is deterministic: UTF-8 text with
LF endings, 2-space indent, sorted object keys, arrays in source order, whole numbers without a
decimal point, any other number as Python's `repr` gives it, one trailing newline.
"""

import json
from typing import Any

import deal

from graphical_symbols.boxes import body_box, keepout_box
from graphical_symbols.geometry import Arc, Box, Circle, Element, Line, Point, Polyline, Text
from graphical_symbols.model import Library, Slot, Symbol, nodes_of

_SCHEMA_VERSION = 1

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


@deal.pure
def _point(point: Point) -> list[float]:
    """Write a point as `[x, y]`."""
    return [point.x, point.y]


@deal.pure
def _box(box: Box) -> list[list[float]]:
    """Write a box as `[[min_x, min_y], [max_x, max_y]]`."""
    return [_point(box.min), _point(box.max)]


@deal.pure
def _slot_id(slot: Slot) -> str:
    """Return a slot's id, the sort key of the slot table."""
    return slot.id


@deal.pure
def _element(element: Element) -> dict[str, Any]:
    """Write an element in the source vocabulary with every default key present."""
    match element:
        case Line(start=start, end=end, weight=weight, style=style):
            return {
                "line": [_point(start), _point(end)],
                "weight": weight.name.lower(),
                "style": style.value,
            }
        case Polyline(points=points, closed=closed, fill=fill, weight=weight, style=style):
            return {
                "polyline": [_point(p) for p in points],
                "closed": closed,
                "fill": fill.value,
                "weight": weight.name.lower(),
                "style": style.value,
            }
        case Circle(center=center, radius=radius, fill=fill, weight=weight):
            return {
                "circle": _point(center),
                "r": radius,
                "fill": fill.value,
                "weight": weight.name.lower(),
            }
        case Arc(center=center, radius=radius, start_deg=start, end_deg=end, weight=w, style=s):
            return {
                "arc": _point(center),
                "r": radius,
                "start": start,
                "end": end,
                "weight": w.name.lower(),
                "style": s.value,
            }
        case Text(content=content, position=at, height=height, weight=weight):
            return {
                "text": content,
                "at": _point(at),
                "height": height,
                "weight": weight.name.lower(),
            }


@deal.pure
def symbol_to_data(symbol: Symbol) -> dict[str, Any]:
    """Return the resolved form of a symbol (guide section 10) as plain data.

    Ports, nodes, paths, anchors, elements and slots are always written, empty when the symbol has
    none; `nodes` lists every node, the single-port ones included (`nodes_of`); slots are a table
    keyed by slot id, in id order. `edition`, `form`, `pole_pitch` and a non-empty `lint_allow`
    appear only when set. `body_box` and `keepout_box` are computed in base orientation.

    Args:
        symbol: A flattened symbol in base orientation.

    Returns:
        A dict of JSON-like values; feed it to `to_json`, or to `symbol_from_data` to read it back.
    """
    reference = {"standard": symbol.reference.standard, "number": symbol.reference.number}
    if symbol.reference.edition is not None:
        reference["edition"] = symbol.reference.edition
    if symbol.reference.form is not None:
        reference["form"] = symbol.reference.form
    data: dict[str, Any] = {
        "schema": _SCHEMA_VERSION,
        "name": symbol.name,
        "kind": symbol.kind.value,
        "status": symbol.status.value,
        "reference": reference,
        "ports": [
            {
                "id": port.id,
                "at": _point(port.position),
                "dir": port.direction.name,
                "description": port.description,
            }
            for port in symbol.ports
        ],
        "nodes": [
            {"ports": list(node.ports)}
            if node.potential is None
            else {"ports": list(node.ports), "potential": node.potential.value}
            for node in nodes_of(symbol)
        ],
        "paths": [
            {
                "from": path.from_port,
                "to": path.to_port,
                "kind": path.kind.value,
                "through": path.through,
            }
            for path in symbol.paths
        ],
        "anchors": [
            {"id": a.id, "at": _point(a.position), "dir": a.direction.name} for a in symbol.anchors
        ],
        "elements": [_element(e) for e in symbol.elements],
        "slots": {
            slot.id: {
                "at": _point(slot.position),
                "side": slot.side.name,
                "box": [slot.box[0], slot.box[1]],
            }
            for slot in sorted(symbol.slots, key=_slot_id)
        },
        "body_box": _box(body_box(symbol)),
        "keepout_box": _box(keepout_box(symbol)),
    }
    if symbol.pole_pitch is not None:
        data["pole_pitch"] = symbol.pole_pitch
    if symbol.lint_allow:
        data["lint_allow"] = [{"rule": a.rule, "reason": a.reason} for a in symbol.lint_allow]
    return data


@deal.pure
def bundle_to_data(library: Library) -> dict[str, Any]:
    """Return the bundle: the schema version, the standard and every symbol, by number (D7)."""
    return {
        "schema": _SCHEMA_VERSION,
        "standard": library.standard,
        "symbols": {
            number: symbol_to_data(library.symbols[number]) for number in sorted(library.symbols)
        },
    }


@deal.pure
def _whole_as_int(value: JsonValue) -> JsonValue:
    """Return the data with every whole finite float replaced by the int, so `2.0` prints as `2`."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_whole_as_int(v) for v in value]
    if isinstance(value, dict):
        return {key: _whole_as_int(v) for key, v in value.items()}
    return value


@deal.pure
def to_json(data: JsonValue) -> str:
    """Render JSON-like data as canonical text (guide section 10).

    Numbers: a whole number has no decimal point (`-0.0` is `0`), any other is the float's `repr`.
    NaN and infinity have no JSON form; they are written as `NaN`, `Infinity` and `-Infinity`,
    which Python's `json.loads` reads back and both validators reject.

    Args:
        data: Dicts with string keys, lists, strings, numbers, booleans and `None`.

    Returns:
        The text, ending with a single newline and containing no carriage return.
    """
    text = json.dumps(_whole_as_int(data), indent=2, sort_keys=True, ensure_ascii=False)
    return text + "\n"
