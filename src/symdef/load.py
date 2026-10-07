"""Read symbol files and `library.toml`: text or decoded data in, findings out, never raises.

`validate` is the hand-written twin of `schema/symbol.schema.json`; the agreement test keeps the
two in step. Both are structural only: types, required keys, enums and array shapes. The id
pattern, the grid, positive sizes and the number pattern are lint rules. The one bound on values
is that every number is finite with an absolute value of at most 1e6 module units, which keeps
all later arithmetic total.
"""

import json
import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

import deal

from symdef.geometry import (
    Arc,
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
)
from symdef.model import (
    Allow,
    Anchor,
    Finding,
    Library,
    LibraryConfig,
    Node,
    Path,
    PathKind,
    Port,
    Potential,
    Reference,
    Severity,
    Slot,
    Status,
    Symbol,
    SymbolKind,
)

# Every number in a file is finite with an absolute value of at most this (1e6 M is 2.5 km).
_LIMIT = 1_000_000

# A check takes a decoded value and its JSON-pointer-like location ("" is the root) and returns
# the violations it finds.
_Check = Callable[[object, str], list[Finding]]


@deal.pure
def _finding(location: str, message: str) -> Finding:
    """Make a `schema` error; the root location becomes `None`."""
    return Finding("schema", Severity.ERROR, message, location or None)


@deal.pure
def _short(text: object, limit: int = 60) -> str:
    """Cap text that comes from the input, so a finding stays readable whatever it was fed.

    A mapping key that is not a string is shown as `str` shows it.
    """
    shown = str(text)
    return shown if len(shown) <= limit else shown[:limit] + "..."


@deal.pure
def _child(location: str, key: str | int) -> str:
    """Extend a location by one key, escaping `~` and `/` as JSON Pointer does."""
    escaped = str(key).replace("~", "~0").replace("/", "~1")
    return f"{location}/{escaped}"


@deal.pure
def _is_number(value: object) -> bool:
    """Return whether a value is a JSON number: an int or float, never a bool."""
    return isinstance(value, int | float) and not isinstance(value, bool)


@deal.pure
def _is_integer(value: object) -> bool:
    """Return whether a value is a JSON integer; like JSON Schema, `8.0` counts."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, float) and value.is_integer())


@deal.pure
def _string(value: object, location: str) -> list[Finding]:
    """Check for a string."""
    return [] if isinstance(value, str) else [_finding(location, "must be a string")]


@deal.pure
def _within_limit(value: object) -> bool:
    """Return whether a number is at most `_LIMIT` in absolute value; NaN and infinity are not."""
    return isinstance(value, int | float) and -_LIMIT <= value <= _LIMIT


@deal.pure
def _number(value: object, location: str) -> list[Finding]:
    """Check for a number within the limit."""
    if not _is_number(value):
        return [_finding(location, "must be a number")]
    if not _within_limit(value):
        return [_finding(location, f"must be a number between -{_LIMIT} and {_LIMIT}")]
    return []


@deal.pure
def _integer(value: object, location: str) -> list[Finding]:
    """Check for an integer within the limit."""
    if not _is_integer(value):
        return [_finding(location, "must be an integer")]
    if not _within_limit(value):
        return [_finding(location, f"must be an integer between -{_LIMIT} and {_LIMIT}")]
    return []


@deal.pure
def _boolean(value: object, location: str) -> list[Finding]:
    """Check for a boolean."""
    return [] if isinstance(value, bool) else [_finding(location, "must be true or false")]


@deal.pure
def _schema_version(value: object, location: str) -> list[Finding]:
    """Check that the schema version is 1."""
    return [] if _is_number(value) and value == 1 else [_finding(location, "must be 1")]


@deal.pure
def _enum(*allowed: str) -> _Check:
    """Build a check for one of a fixed set of strings."""

    def check(value: object, location: str) -> list[Finding]:
        if isinstance(value, str) and value in allowed:
            return []
        return [_finding(location, f"must be one of {', '.join(allowed)}")]

    return check


@deal.pure
def _array(item: _Check, length: int | None = None) -> _Check:
    """Build a check for an array whose items pass `item`, optionally of an exact length."""

    def check(value: object, location: str) -> list[Finding]:
        if not isinstance(value, list):
            return [_finding(location, "must be an array")]
        found = []
        if length is not None and len(value) != length:
            found.append(_finding(location, f"must have exactly {length} items"))
        for index, entry in enumerate(value):
            found += item(entry, _child(location, index))
        return found

    return check


@deal.pure
def _table(fields: Mapping[str, _Check], required: tuple[str, ...] = ()) -> _Check:
    """Build a check for a table with these keys and no others."""

    def check(value: object, location: str) -> list[Finding]:
        if not isinstance(value, dict):
            return [_finding(location, "must be a table")]
        found = [
            _finding(location, f"missing required key {key!r}")
            for key in required
            if key not in value
        ]
        for key, entry in value.items():
            if key in fields:
                found += fields[key](entry, _child(location, key))
            else:
                found.append(_finding(_child(location, key), f"unknown key {_short(key)!r}"))
        return found

    return check


@deal.pure
def _map_of(item: _Check) -> _Check:
    """Build a check for a table with any keys whose values pass `item`."""

    def check(value: object, location: str) -> list[Finding]:
        if not isinstance(value, dict):
            return [_finding(location, "must be a table")]
        found = []
        for key, entry in value.items():
            found += item(entry, _child(location, key))
        return found

    return check


_POINT = _array(_number, 2)
_BOX = _array(_POINT, 2)
_DIRECTION = _enum("N", "E", "S", "W")
_WEIGHT = _enum("normal", "thick")
_STYLE = _enum("solid", "dashed")
_FILL = _enum("none", "solid")

_REFERENCE = _table(
    {"standard": _string, "number": _string, "edition": _string, "form": _string},
    required=("standard", "number"),
)
_PORT = _table(
    {"id": _string, "at": _POINT, "dir": _DIRECTION, "description": _string},
    required=("id", "at", "dir"),
)
_NODE = _table(
    {
        "ports": _array(_string),
        "potential": _enum("earth", "protective_earth", "functional_earth", "frame"),
    },
    required=("ports",),
)
_PATH = _table(
    {
        "from": _string,
        "to": _string,
        "kind": _enum("conductor", "switch_open", "switch_closed", "impedance", "source", "diode"),
        "through": _boolean,
    },
    required=("from", "to", "kind"),
)
_ANCHOR = _table({"id": _string, "at": _POINT, "dir": _DIRECTION}, required=("id", "at", "dir"))
_SLOT = _table(
    {"at": _POINT, "side": _DIRECTION, "box": _array(_number, 2)}, required=("at", "side", "box")
)
_PART = _table(
    {
        "as": _string,
        "use": _string,
        "orient": _enum("R0", "R90", "R180", "R270", "MR0", "MR90", "MR180", "MR270"),
        "attach": _string,
        "to": _string,
        "length": _number,
        "via": _enum("mechanical_link"),
        "at": _POINT,
        "repeat": _integer,
    },
    required=("as", "use"),
)
_ALLOW = _table({"rule": _string, "reason": _string}, required=("rule", "reason"))

# One table per shape, keyed by the shape key; an element has exactly one of these keys.
_ELEMENTS = {
    "line": _table(
        {"line": _array(_POINT, 2), "weight": _WEIGHT, "style": _STYLE, "port": _string},
        required=("line",),
    ),
    "polyline": _table(
        {
            "polyline": _array(_POINT),
            "closed": _boolean,
            "fill": _FILL,
            "weight": _WEIGHT,
            "style": _STYLE,
        },
        required=("polyline",),
    ),
    "circle": _table(
        {"circle": _POINT, "r": _number, "fill": _FILL, "weight": _WEIGHT},
        required=("circle", "r"),
    ),
    "arc": _table(
        {
            "arc": _POINT,
            "r": _number,
            "start": _number,
            "end": _number,
            "weight": _WEIGHT,
            "style": _STYLE,
        },
        required=("arc", "r", "start", "end"),
    ),
    "text": _table(
        {"text": _string, "at": _POINT, "height": _number, "weight": _WEIGHT},
        required=("text", "at", "height"),
    ),
}


@deal.pure
def _element(value: object, location: str) -> list[Finding]:
    """Check an element: a table with exactly one shape key and only that shape's other keys."""
    if not isinstance(value, dict):
        return [_finding(location, "must be a table")]
    shapes = [key for key in value if key in _ELEMENTS]
    if len(shapes) != 1:
        return [
            _finding(
                location,
                "an element needs exactly one shape key: line, polyline, circle, arc or text",
            )
        ]
    return _ELEMENTS[shapes[0]](value, location)


@deal.pure
def _ports(value: object, location: str) -> list[Finding]:
    """Check `ports`: an array of port tables (atomic) or a table of strings (composite)."""
    if isinstance(value, list):
        return _array(_PORT)(value, location)
    if isinstance(value, dict):
        return _map_of(_string)(value, location)
    return [_finding(location, "must be an array of tables, or a table of strings in a composite")]


@deal.pure
def _slot(value: object, location: str) -> list[Finding]:
    """Check one slot: a table, or in a composite a string reference to a part's slot."""
    return [] if isinstance(value, str) else _SLOT(value, location)


_FILE = _table(
    {
        "schema": _schema_version,
        "name": _string,
        "kind": _enum("symbol", "element", "qualifier"),
        "status": _enum("unverified", "verified"),
        "reference": _REFERENCE,
        "ports": _ports,
        "nodes": _array(_NODE),
        "paths": _array(_PATH),
        "anchors": _array(_ANCHOR),
        "elements": _array(_element),
        "parts": _array(_PART),
        "slots": _map_of(_slot),
        "pole_pitch": _integer,
        "lint_allow": _array(_ALLOW),
        "body_box": _BOX,
        "keepout_box": _BOX,
    },
    required=("schema", "name", "kind", "status", "reference"),
)


@deal.pure
def parse_toml(text: str) -> tuple[dict[str, Any] | None, tuple[Finding, ...]]:
    """Decode TOML text; input the parser rejects or cannot handle becomes a `schema` finding.

    `TOMLDecodeError` is a `ValueError`, as is the error for an integer of more than 4300 digits;
    absurdly deep nesting exhausts the stack instead.
    """
    try:
        data = tomllib.loads(text)
    except (ValueError, RecursionError) as error:
        return None, (_finding("", _short(f"invalid TOML: {error}", 200)),)
    return data, ()


@deal.pure
def validate(data: object) -> tuple[Finding, ...]:
    """Check decoded data against the symbol file format, atomic, composite or resolved.

    Args:
        data: A decoded TOML or JSON document.

    Returns:
        One `schema` error per violation, located by a JSON-pointer-like path (`/ports/0/dir`;
        `None` for the whole file). Empty when the data is acceptable to the JSON Schema.
    """
    found = _FILE(data, "")
    if isinstance(data, dict):
        if "elements" not in data and "parts" not in data:
            found.append(_finding("", "a file needs elements, parts, or both"))
        if data.get("kind") == "symbol" and "slots" not in data:
            found.append(
                _finding("", "missing required key 'slots' (required when kind is symbol)")
            )
    return tuple(found)


@deal.pure
def parse_json(text: str) -> tuple[Any, tuple[Finding, ...]]:
    """Decode JSON text; input the parser rejects or cannot handle becomes a `schema` finding.

    Like `parse_toml`, `ValueError` covers a syntax error and an integer of more than 4300
    digits; absurdly deep nesting exhausts the stack instead. The data is `None` on a finding
    (and also when the text is the JSON `null`, which `validate_bundle` then rejects).
    """
    try:
        return json.loads(text), ()
    except (ValueError, RecursionError) as error:
        return None, (_finding("", _short(f"invalid JSON: {error}", 200)),)


@deal.pure
def _point(value: list[float]) -> Point:
    """Build a point from an `[x, y]` array."""
    return Point(value[0], value[1])


@deal.pure
def _element_from_data(item: Mapping[str, Any]) -> Element:
    """Build an element, filling in the documented defaults for absent keys."""
    weight = Weight[item.get("weight", "normal").upper()]
    if "line" in item:
        start, end = item["line"]
        return Line(
            _point(start), _point(end), weight, Style(item.get("style", "solid")), item.get("port")
        )
    if "polyline" in item:
        return Polyline(
            tuple(_point(p) for p in item["polyline"]),
            item.get("closed", False),
            Fill(item.get("fill", "none")),
            weight,
            Style(item.get("style", "solid")),
        )
    if "circle" in item:
        return Circle(_point(item["circle"]), item["r"], Fill(item.get("fill", "none")), weight)
    if "arc" in item:
        return Arc(
            _point(item["arc"]),
            item["r"],
            item["start"],
            item["end"],
            weight,
            Style(item.get("style", "solid")),
        )
    return Text(item["text"], _point(item["at"]), item["height"], weight)


@deal.pure
def symbol_from_data(data: Mapping[str, Any]) -> Symbol:
    """Build a symbol from validated atomic data: a TOML file or a resolved JSON symbol.

    Absent optional keys take their documented defaults, so the explicit keys of the resolved
    form read the same way. `schema`, `body_box` and `keepout_box` are ignored. Slots keep
    their table order. Composite-only forms (`parts`, a rename-map `ports`, string slot
    references) are the resolver's business and not read here.

    Args:
        data: Decoded data for which `validate` returned no findings.

    Returns:
        The symbol.
    """
    reference = data["reference"]
    ports = data.get("ports")
    return Symbol(
        name=data["name"],
        kind=SymbolKind(data["kind"]),
        status=Status(data["status"]),
        reference=Reference(
            reference["standard"],
            reference["number"],
            reference.get("edition"),
            reference.get("form"),
        ),
        elements=tuple(_element_from_data(e) for e in data.get("elements", ())),
        ports=tuple(
            Port(p["id"], _point(p["at"]), Direction[p["dir"]], p.get("description", ""))
            for p in (ports if isinstance(ports, list) else ())
        ),
        nodes=tuple(
            Node(tuple(n["ports"]), Potential(n["potential"]) if "potential" in n else None)
            for n in data.get("nodes", ())
        ),
        paths=tuple(
            Path(p["from"], p["to"], PathKind(p["kind"]), p.get("through", False))
            for p in data.get("paths", ())
        ),
        anchors=tuple(
            Anchor(a["id"], _point(a["at"]), Direction[a["dir"]]) for a in data.get("anchors", ())
        ),
        slots=tuple(
            Slot(key, _point(s["at"]), Direction[s["side"]], (s["box"][0], s["box"][1]))
            for key, s in data.get("slots", {}).items()
            if isinstance(s, dict)
        ),
        pole_pitch=int(data["pole_pitch"]) if "pole_pitch" in data else None,
        lint_allow=tuple(Allow(a["rule"], a["reason"]) for a in data.get("lint_allow", ())),
    )


# A number is a file stem (`5.1.toml`, `ISO-14617-1.1.toml`) and `write_build` names files after
# it: letters, digits, `_` and `-`, in parts joined by single dots, so no separator, no `..`.
_STEM = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*")


@deal.pure
def is_file_stem(text: object) -> bool:
    """Return whether a reference number is safe to use as a file name in a build.

    Anything that is not a string is not.
    """
    return isinstance(text, str) and _STEM.fullmatch(text) is not None


@deal.pure
def _bundle_symbol(value: object, location: str) -> list[Finding]:
    """Check one bundle symbol: `validate` and the resolved form (no `parts`, arrays, tables)."""
    found = [replace(f, location=location + (f.location or "")) for f in validate(value)]
    if not isinstance(value, dict):
        return found
    if "parts" in value:
        found.append(_finding(_child(location, "parts"), "a bundle symbol has no parts"))
    if "ports" in value and not isinstance(value["ports"], list):
        found.append(_finding(_child(location, "ports"), "must be an array in a bundle"))
    slots = value.get("slots")
    if isinstance(slots, dict):
        found.extend(
            _finding(_child(_child(location, "slots"), key), "must be a table in a bundle")
            for key, slot in slots.items()
            if isinstance(slot, str)
        )
    return found


_BUNDLE = _table(
    {"schema": _schema_version, "standard": _string, "symbols": _map_of(_bundle_symbol)},
    required=("schema", "standard", "symbols"),
)


@deal.pure
def validate_bundle(data: object) -> tuple[Finding, ...]:
    """Check a decoded `bundle.json`: its three keys, and every symbol as a resolved symbol.

    Args:
        data: A decoded JSON document.

    Returns:
        One `schema` error per violation, located inside the bundle (`/symbols/S00227/ports/0`).
        A symbol is checked by `validate` and must also be resolved (no `parts`, `ports` an array,
        slots tables). Its key must be safe as a file name (`is_file_stem`: letters, digits, `_`
        and `-`, joined by single dots) and equal its `reference.number`, as a number equals
        its file stem. Empty when `library_from_bundle` may be called.
    """
    found = list(_BUNDLE(data, ""))
    if isinstance(data, dict) and isinstance(data.get("symbols"), dict):
        for key, symbol in data["symbols"].items():
            if not is_file_stem(key):
                found.append(
                    _finding(
                        _child("/symbols", key), f"{_short(key)!r} cannot be used as a file name"
                    )
                )
            reference = symbol.get("reference") if isinstance(symbol, dict) else None
            number = reference.get("number") if isinstance(reference, dict) else None
            if isinstance(number, str) and number != key:
                found.append(
                    _finding(
                        _child(_child(_child("/symbols", key), "reference"), "number"),
                        f"must equal the symbol's key {_short(key)!r}, got {_short(number)!r}",
                    )
                )
    return tuple(found)


@deal.pure
def library_from_bundle(data: Mapping[str, Any]) -> Library:
    """Build a library from a validated bundle (D7).

    The bundle carries neither a title nor a number pattern, so the title is the standard and the
    pattern is empty.

    Args:
        data: A decoded `bundle.json` for which `validate_bundle` returned no findings.

    Returns:
        The library, its symbols keyed by the bundle's keys.
    """
    symbols = {number: symbol_from_data(s) for number, s in data["symbols"].items()}
    return Library(data["standard"], data["standard"], "", symbols)


@deal.pure
def parse_config(text: str) -> tuple[LibraryConfig | None, tuple[Finding, ...]]:
    """Read `library.toml`: `standard`, `title` and `number_pattern`, all strings, the last a regex.

    Args:
        text: The file's TOML text.

    Returns:
        The config and no findings, or `None` and a `schema` finding per problem.
    """
    data, findings = parse_toml(text)
    if data is None:
        return None, findings
    problems: list[Finding] = []
    for key in ("standard", "title", "number_pattern"):
        if key not in data:
            problems.append(_finding("", f"missing required key {key!r}"))
        elif not isinstance(data[key], str):
            problems.append(_finding(_child("", key), "must be a string"))
    pattern = data.get("number_pattern")
    if isinstance(pattern, str):
        try:
            re.compile(pattern)
        except (re.error, OverflowError, RecursionError) as error:
            problems.append(
                _finding(
                    "/number_pattern", _short(f"must be a valid regular expression: {error}", 200)
                )
            )
    if problems:
        return None, tuple(problems)
    return LibraryConfig(data["standard"], data["title"], data["number_pattern"]), ()
