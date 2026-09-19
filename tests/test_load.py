import copy
import re

import pytest

from graphical_symbols.geometry import (
    Arc,
    Circle,
    Direction,
    Fill,
    Line,
    Point,
    Polyline,
    Style,
    Text,
    Weight,
)
from graphical_symbols.load import parse_config, parse_toml, symbol_from_data, validate
from graphical_symbols.model import (
    Allow,
    Anchor,
    Finding,
    Node,
    Path,
    PathKind,
    Port,
    Potential,
    Reference,
    Severity,
    Slot,
    Status,
    SymbolKind,
)

FULL_TOML = """
schema = 1
name = "Make contact"
kind = "symbol"
status = "verified"
reference = { standard = "IEC 60617", number = "S00227", edition = "2", form = "1" }
pole_pitch = 8

ports = [
  { id = "in",  at = [0, -2], dir = "N", description = "top" },
  { id = "out", at = [0, 2],  dir = "S" },
]
nodes = [
  { ports = ["in"], potential = "protective_earth" },
]
paths = [
  { from = "in", to = "out", kind = "switch_open", through = true },
  { from = "out", to = "in", kind = "diode" },
]
anchors = [
  { id = "link", at = [-0.5, 0], dir = "W" },
]
elements = [
  { line = [[0, -2], [0, -1]], weight = "thick", style = "dashed" },
  { polyline = [[0, 0], [1, 0], [1, 1]], closed = true, fill = "solid" },
  { circle = [0, 0], r = 0.25, fill = "solid", weight = "thick" },
  { arc = [0, 0], r = 1, start = 180, end = 0, style = "dashed" },
  { text = "M", at = [0, 0], height = 0.5 },
]
lint_allow = [
  { rule = "port-lane-clear", reason = "junction" },
]

[slots]
tag = { at = [-1.5, 0], side = "W", box = [6, 1] }
"marking.in" = { at = [0.25, -1.5], side = "E", box = [1.5, 1] }
"""


def atomic():
    return {
        "schema": 1,
        "name": "x",
        "kind": "symbol",
        "status": "unverified",
        "reference": {"standard": "IEC 60617", "number": "S00001"},
        "elements": [{"line": [[0, 0], [1, 0]]}],
    }


def composite():
    return {
        "schema": 1,
        "name": "x",
        "kind": "symbol",
        "status": "unverified",
        "reference": {"standard": "IEC 60617", "number": "S00001"},
        "parts": [
            {"as": "contact", "use": "S00227"},
            {
                "as": "actuator",
                "use": "S00171",
                "attach": "link",
                "to": "contact.link",
                "length": 2,
                "via": "mechanical_link",
                "orient": "MR90",
                "repeat": 3,
            },
            {"as": "inside", "use": "S00171", "at": [0.5, 0.5]},
        ],
        "ports": {"in": "contact.in"},
        "slots": {
            "tag": {"at": [0, 0], "side": "W", "box": [6, 1]},
            "marking.in": "contact.marking.in",
        },
    }


def resolved():
    """The resolved JSON form of guide section 10: everything explicit, plus the two boxes."""
    return {
        "schema": 1,
        "name": "x",
        "kind": "symbol",
        "status": "unverified",
        "reference": {"standard": "IEC 60617", "number": "S00001"},
        "ports": [{"id": "in", "at": [0, -2], "dir": "N", "description": ""}],
        "nodes": [{"ports": ["in"]}],
        "elements": [
            {"line": [[0, 0], [1, 0]], "weight": "normal", "style": "solid"},
            {
                "polyline": [[0, 0], [1, 0]],
                "closed": False,
                "fill": "none",
                "weight": "normal",
                "style": "solid",
            },
            {"circle": [0, 0], "r": 1, "fill": "none", "weight": "normal"},
            {"arc": [0, 0], "r": 1, "start": 0, "end": 90, "weight": "normal", "style": "solid"},
            {"text": "M", "at": [0, 0], "height": 1, "weight": "normal"},
        ],
        "slots": {"tag": {"at": [0, 0], "side": "W", "box": [6, 1]}},
        "body_box": [[0, 0], [1, 0]],
        "keepout_box": [[-6, -0.5], [1, 0.5]],
    }


def locations(data):
    return {f.location for f in validate(data)}


def edited(base, *path, value):
    data = copy.deepcopy(base)
    target = data
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return data


# parse_toml


def test_parse_toml_returns_the_decoded_table():
    data, findings = parse_toml('a = 1\n[t]\nb = "x"\n')
    assert data == {"a": 1, "t": {"b": "x"}}
    assert findings == ()


def test_parse_toml_reports_a_syntax_error_as_a_schema_finding():
    data, findings = parse_toml("a = = 1\n")
    assert data is None
    assert len(findings) == 1
    assert findings[0].rule == "schema"
    assert findings[0].severity is Severity.ERROR
    assert "TOML" in findings[0].message


# What validate accepts


def test_the_minimal_atomic_and_composite_files_are_valid():
    assert validate(atomic()) == ()
    assert validate(composite()) == ()


def test_the_resolved_json_form_is_valid():
    assert validate(resolved()) == ()


def test_the_full_toml_file_is_valid():
    data, _ = parse_toml(FULL_TOML)
    assert validate(data) == ()


def test_a_file_with_both_elements_and_parts_is_valid():
    both = composite()
    both["elements"] = [{"line": [[0, 0], [1, 0]]}]
    assert validate(both) == ()


def test_integral_floats_count_as_integers():
    data = atomic()
    data["schema"] = 1.0
    data["pole_pitch"] = 8.0
    assert validate(data) == ()


# What validate reports


def test_a_finding_is_a_schema_error_with_a_pointer_location():
    (finding,) = validate(edited(atomic(), "kind", value="widget"))
    assert finding.rule == "schema"
    assert finding.severity is Severity.ERROR
    assert finding.location == "/kind"
    assert "widget" in finding.message


def test_the_root_has_no_location():
    (finding,) = validate([1])
    assert finding.rule == "schema"
    assert finding.location is None


def test_a_missing_required_key_is_reported_on_its_table():
    data = atomic()
    del data["name"]
    del data["reference"]["number"]
    assert {(f.location, f.message) for f in validate(data)} == {
        (None, "missing required key 'name'"),
        ("/reference", "missing required key 'number'"),
    }


def test_an_unknown_key_is_reported_at_the_key():
    data = atomic()
    data["colour"] = "red"
    data["elements"][0]["colour"] = "red"
    assert locations(data) == {"/colour", "/elements/0/colour"}


def test_a_file_needs_elements_or_parts():
    data = atomic()
    del data["elements"]
    (finding,) = validate(data)
    assert finding.location is None
    assert "elements" in finding.message
    assert "parts" in finding.message


def test_every_problem_in_a_file_is_reported():
    data = atomic()
    data["name"] = 3
    data["status"] = "maybe"
    data["pole_pitch"] = "wide"
    assert locations(data) == {"/name", "/status", "/pole_pitch"}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema",), 2),
        (("schema",), "1"),
        (("schema",), True),
        (("name",), 1),
        (("kind",), "Symbol"),
        (("status",), None),
        (("reference",), "S00227"),
        (("reference", "standard"), 1),
        (("reference", "edition"), 2),
        (("reference", "form"), ["1"]),
        (("pole_pitch",), 8.5),
        (("pole_pitch",), True),
        (("elements",), {"line": [[0, 0], [1, 0]]}),
        (("elements", 0), [[0, 0], [1, 0]]),
        (("elements", 0, "weight"), "bold"),
        (("elements", 0, "style"), "dotted"),
        (("elements", 0, "line"), [[0, 0]]),
        (("elements", 0, "line"), [[0, 0], [1, 0], [2, 0]]),
        (("elements", 0, "line"), [[0, 0], [1]]),
        (("elements", 0, "line"), [[0, 0], [1, "0"]]),
        (("elements", 0, "line"), [[0, 0], [1, True]]),
    ],
)
def test_wrong_scalar_and_shape_values_are_findings(path, value):
    data = edited(atomic(), *path, value=value)
    expected = "/" + "/".join(str(step) for step in path)
    assert any(
        loc == expected or loc.startswith(expected + "/") for loc in map(str, locations(data))
    )


def test_polyline_elements_are_checked():
    base = {**atomic(), "elements": [{"polyline": [[0, 0], [1, 0]]}]}
    assert validate(base) == ()
    assert locations(edited(base, "elements", 0, "closed", value="yes")) == {"/elements/0/closed"}
    assert locations(edited(base, "elements", 0, "fill", value="hatched")) == {"/elements/0/fill"}
    assert locations(edited(base, "elements", 0, "polyline", value=[0, 0])) == {
        "/elements/0/polyline/0",
        "/elements/0/polyline/1",
    }
    assert validate(edited(base, "elements", 0, "polyline", value=[])) == ()


def test_circle_arc_and_text_elements_are_checked():
    circle = {**atomic(), "elements": [{"circle": [0, 0], "r": 1}]}
    assert validate(circle) == ()
    assert locations(edited(circle, "elements", 0, "r", value="1")) == {"/elements/0/r"}
    assert locations(edited(circle, "elements", 0, "circle", value=[0])) == {"/elements/0/circle"}
    del circle["elements"][0]["r"]
    assert locations(circle) == {"/elements/0"}

    arc = {**atomic(), "elements": [{"arc": [0, 0], "r": 1, "start": 0, "end": 90}]}
    assert validate(arc) == ()
    assert locations(edited(arc, "elements", 0, "end", value="90")) == {"/elements/0/end"}
    del arc["elements"][0]["start"]
    assert locations(arc) == {"/elements/0"}

    text = {**atomic(), "elements": [{"text": "M", "at": [0, 0], "height": 1}]}
    assert validate(text) == ()
    assert locations(edited(text, "elements", 0, "text", value=1)) == {"/elements/0/text"}
    assert locations(edited(text, "elements", 0, "height", value="1")) == {"/elements/0/height"}
    del text["elements"][0]["at"]
    assert locations(text) == {"/elements/0"}


@pytest.mark.parametrize(
    "element",
    [
        {},
        {"weight": "thick"},
        {"line": [[0, 0], [1, 0]], "circle": [0, 0], "r": 1},
        {"polyline": [[0, 0], [1, 0]], "text": "M", "at": [0, 0], "height": 1},
    ],
)
def test_an_element_needs_exactly_one_shape_key(element):
    data = {**atomic(), "elements": [element]}
    (finding,) = validate(data)
    assert finding.location == "/elements/0"
    assert "exactly one shape" in finding.message


@pytest.mark.parametrize(
    "element",
    [
        {"circle": [0, 0], "r": 1, "style": "dashed"},
        {"text": "M", "at": [0, 0], "height": 1, "style": "dashed"},
        {"line": [[0, 0], [1, 0]], "fill": "solid"},
        {"arc": [0, 0], "r": 1, "start": 0, "end": 1, "fill": "solid"},
        {"line": [[0, 0], [1, 0]], "closed": True},
        {"circle": [0, 0], "r": 1, "closed": True},
        {"line": [[0, 0], [1, 0]], "r": 1},
    ],
)
def test_optional_keys_belong_to_their_shapes(element):
    (finding,) = validate({**atomic(), "elements": [element]})
    assert finding.rule == "schema"
    assert finding.message.startswith("unknown key")


def test_ports_are_checked():
    data = edited(resolved(), "ports", value=[{"id": "in", "at": [0, 0], "dir": "N"}])
    assert validate(data) == ()
    assert locations(edited(data, "ports", 0, "dir", value="X")) == {"/ports/0/dir"}
    assert locations(edited(data, "ports", 0, "at", value=[0])) == {"/ports/0/at"}
    assert locations(edited(data, "ports", 0, "id", value=1)) == {"/ports/0/id"}
    assert locations(edited(data, "ports", 0, "description", value=1)) == {"/ports/0/description"}
    assert locations(edited(data, "ports", 0, "n", value=1)) == {"/ports/0/n"}
    del data["ports"][0]["at"]
    assert locations(data) == {"/ports/0"}
    assert locations(edited(data, "ports", value="in")) == {"/ports"}
    assert locations(edited(data, "ports", value=["in"])) == {"/ports/0"}


def test_composite_ports_are_a_map_of_strings():
    data = composite()
    assert locations(edited(data, "ports", "in", value=1)) == {"/ports/in"}
    assert locations(edited(data, "ports", value="contact.in")) == {"/ports"}
    assert validate(edited(data, "ports", value={})) == ()


def test_nodes_paths_anchors_and_allowances_are_checked():
    base = {**atomic()}
    base["nodes"] = [{"ports": ["a", "b"], "potential": "earth"}]
    base["paths"] = [{"from": "a", "to": "b", "kind": "source", "through": True}]
    base["anchors"] = [{"id": "link", "at": [0, 0], "dir": "E"}]
    base["lint_allow"] = [{"rule": "x", "reason": "y"}]
    assert validate(base) == ()
    assert locations(edited(base, "nodes", 0, "potential", value="ground")) == {
        "/nodes/0/potential"
    }
    assert locations(edited(base, "nodes", 0, "ports", value="a")) == {"/nodes/0/ports"}
    assert locations(edited(base, "nodes", 0, "ports", value=[1])) == {"/nodes/0/ports/0"}
    assert locations(edited(base, "paths", 0, "kind", value="wire")) == {"/paths/0/kind"}
    assert locations(edited(base, "paths", 0, "through", value="yes")) == {"/paths/0/through"}
    assert locations(edited(base, "paths", 0, "from", value=1)) == {"/paths/0/from"}
    assert locations(edited(base, "anchors", 0, "dir", value="up")) == {"/anchors/0/dir"}
    assert locations(edited(base, "lint_allow", 0, "reason", value=1)) == {"/lint_allow/0/reason"}
    del base["lint_allow"][0]["rule"]
    del base["paths"][0]["to"]
    assert locations(base) == {"/lint_allow/0", "/paths/0"}


def test_slots_are_tables_or_string_references():
    data = composite()
    assert locations(edited(data, "slots", "tag", "side", value="up")) == {"/slots/tag/side"}
    assert locations(edited(data, "slots", "tag", "box", value=[6])) == {"/slots/tag/box"}
    assert locations(edited(data, "slots", "tag", "at", value="0")) == {"/slots/tag/at"}
    assert locations(edited(data, "slots", "tag", "extra", value=1)) == {"/slots/tag/extra"}
    assert locations(edited(data, "slots", "tag", value=3)) == {"/slots/tag"}
    assert locations(edited(data, "slots", value=[])) == {"/slots"}
    assert validate(edited(data, "slots", value={})) == ()
    del data["slots"]["tag"]["box"]
    assert locations(data) == {"/slots/tag"}


def test_slot_keys_with_slashes_are_escaped_in_locations():
    data = edited(composite(), "slots", "a/b~c", value=3)
    assert "/slots/a~1b~0c" in locations(data)


def test_parts_are_checked():
    data = composite()
    assert locations(edited(data, "parts", 1, "orient", value="R45")) == {"/parts/1/orient"}
    assert locations(edited(data, "parts", 1, "via", value="glue")) == {"/parts/1/via"}
    assert locations(edited(data, "parts", 1, "length", value="2")) == {"/parts/1/length"}
    assert locations(edited(data, "parts", 1, "repeat", value=1.5)) == {"/parts/1/repeat"}
    assert locations(edited(data, "parts", 2, "at", value=[1])) == {"/parts/2/at"}
    assert locations(edited(data, "parts", 1, "extra", value=1)) == {"/parts/1/extra"}
    assert locations(edited(data, "parts", value={})) == {"/parts"}
    del data["parts"][0]["use"]
    del data["parts"][1]["as"]
    assert locations(data) == {"/parts/0", "/parts/1"}


def test_the_resolved_boxes_are_checked():
    assert locations(edited(resolved(), "body_box", value=[[0, 0]])) == {"/body_box"}
    assert locations(edited(resolved(), "keepout_box", value=[[0, 0], [1]])) == {"/keepout_box/1"}


def test_the_validator_does_not_raise_on_unhashable_or_odd_values():
    data = atomic()
    data["kind"] = [1]
    data["status"] = {"a": 1}
    data["elements"] = [None, 3, "x", [], {"line": {"a": 1}}]
    assert {f.location for f in validate(data)} >= {"/kind", "/status", "/elements/0"}


def test_the_id_pattern_and_grid_are_not_schema_matters():
    data = atomic()
    data["ports"] = [{"id": "Bad.Id", "at": [0.3, 0], "dir": "N"}]
    data["slots"] = {"tag": {"at": [0, 0], "side": "N", "box": [-1, 0]}}
    data["reference"] = {"standard": "", "number": "not a number"}
    data["pole_pitch"] = 5
    data["elements"] = [{"circle": [0, 0], "r": -1}]
    assert validate(data) == ()


# symbol_from_data


def test_symbol_from_data_builds_every_field():
    data, _ = parse_toml(FULL_TOML)
    assert data is not None
    symbol = symbol_from_data(data)
    assert symbol.name == "Make contact"
    assert symbol.kind is SymbolKind.SYMBOL
    assert symbol.status is Status.VERIFIED
    assert symbol.reference == Reference("IEC 60617", "S00227", edition="2", form="1")
    assert symbol.pole_pitch == 8
    assert symbol.ports == (
        Port("in", Point(0, -2), Direction.N, "top"),
        Port("out", Point(0, 2), Direction.S),
    )
    assert symbol.nodes == (Node(("in",), Potential.PROTECTIVE_EARTH),)
    assert symbol.paths == (
        Path("in", "out", PathKind.SWITCH_OPEN, through=True),
        Path("out", "in", PathKind.DIODE),
    )
    assert symbol.anchors == (Anchor("link", Point(-0.5, 0), Direction.W),)
    assert symbol.lint_allow == (Allow("port-lane-clear", "junction"),)
    assert symbol.slots == (
        Slot("tag", Point(-1.5, 0), Direction.W, (6, 1)),
        Slot("marking.in", Point(0.25, -1.5), Direction.E, (1.5, 1)),
    )
    assert symbol.elements == (
        Line(Point(0, -2), Point(0, -1), Weight.THICK, Style.DASHED),
        Polyline((Point(0, 0), Point(1, 0), Point(1, 1)), closed=True, fill=Fill.SOLID),
        Circle(Point(0, 0), 0.25, Fill.SOLID, Weight.THICK),
        Arc(Point(0, 0), 1, 180, 0, style=Style.DASHED),
        Text("M", Point(0, 0), 0.5),
    )


def test_symbol_from_data_applies_the_documented_defaults():
    data = {
        **atomic(),
        "elements": [
            {"line": [[0, 0], [1, 0]]},
            {"polyline": [[0, 0], [1, 0]]},
            {"circle": [0, 0], "r": 1},
            {"arc": [0, 0], "r": 1, "start": 0, "end": 90},
            {"text": "M", "at": [0, 0], "height": 1},
        ],
    }
    symbol = symbol_from_data(data)
    assert symbol.elements == (
        Line(Point(0, 0), Point(1, 0)),
        Polyline((Point(0, 0), Point(1, 0))),
        Circle(Point(0, 0), 1),
        Arc(Point(0, 0), 1, 0, 90),
        Text("M", Point(0, 0), 1),
    )
    assert (symbol.ports, symbol.nodes, symbol.paths, symbol.anchors, symbol.slots) == ((),) * 5
    assert symbol.reference == Reference("IEC 60617", "S00001")
    assert symbol.pole_pitch is None
    assert symbol.lint_allow == ()


def test_symbol_from_data_accepts_the_explicit_resolved_form():
    data = resolved()
    data["nodes"] = [{"ports": ["in"], "potential": "earth"}]
    symbol = symbol_from_data(data)
    assert symbol.nodes == (Node(("in",), Potential.EARTH),)
    assert symbol.ports == (Port("in", Point(0, -2), Direction.N, ""),)
    assert symbol.slots == (Slot("tag", Point(0, 0), Direction.W, (6, 1)),)
    assert symbol.elements[1] == Polyline((Point(0, 0), Point(1, 0)), closed=False, fill=Fill.NONE)
    assert symbol.elements[4] == Text("M", Point(0, 0), 1, Weight.NORMAL)
    assert not hasattr(symbol, "body_box")


def test_symbol_from_data_turns_integral_floats_into_ints():
    data = {**atomic(), "pole_pitch": 8.0}
    assert symbol_from_data(data).pole_pitch == 8
    assert isinstance(symbol_from_data(data).pole_pitch, int)


# parse_config

CONFIG = """standard = "IEC 60617"
title = "IEC 60617 symbols"
number_pattern = '^S\\d{5}$'
"""


def test_parse_config_reads_the_three_strings():
    config, findings = parse_config(CONFIG)
    assert findings == ()
    assert config is not None
    assert (config.standard, config.title) == ("IEC 60617", "IEC 60617 symbols")
    assert re.fullmatch(config.number_pattern, "S00227")


def test_parse_config_reports_a_syntax_error():
    config, findings = parse_config("standard = ")
    assert config is None
    assert [f.rule for f in findings] == ["schema"]


@pytest.mark.parametrize("key", ["standard", "title", "number_pattern"])
def test_parse_config_requires_every_key(key):
    text = "\n".join(line for line in CONFIG.splitlines() if not line.startswith(key))
    config, findings = parse_config(text)
    assert config is None
    assert findings == (
        Finding("schema", Severity.ERROR, f"missing required key {key!r}", location=None),
    )


@pytest.mark.parametrize("key", ["standard", "title", "number_pattern"])
def test_parse_config_requires_strings(key):
    text = re.sub(rf"^{key} = .*$", f"{key} = 3", CONFIG, flags=re.MULTILINE)
    config, findings = parse_config(text)
    assert config is None
    assert [f.location for f in findings] == [f"/{key}"]


def test_parse_config_requires_a_pattern_that_compiles():
    config, findings = parse_config(CONFIG.replace(r"^S\d{5}$", "^S(\\d{5}$"))
    assert config is None
    assert len(findings) == 1
    assert findings[0].rule == "schema"
    assert findings[0].location == "/number_pattern"


def test_parse_config_reports_every_problem():
    config, findings = parse_config('title = 3\nnumber_pattern = "("\n')
    assert config is None
    assert {(f.location, f.message.split(" ")[0]) for f in findings} == {
        (None, "missing"),
        ("/title", "must"),
        ("/number_pattern", "must"),
    }
