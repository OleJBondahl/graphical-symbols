"""Resolved output: `symbol_to_data`, `bundle_to_data`, `to_json` and the round trip."""

import json
from dataclasses import replace
from pathlib import Path as FilePath

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from roundtrip import normalised, round_trips

from symdef.build import load_library
from symdef.geometry import (
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
from symdef.load import symbol_from_data, validate
from symdef.model import (
    Allow,
    Anchor,
    Library,
    Node,
    Path,
    Port,
    Reference,
    Slot,
    Status,
    Symbol,
    SymbolKind,
)
from symdef.repeat import repeat
from symdef.serialize import bundle_to_data, symbol_to_data, to_json

TESTS = FilePath(__file__).resolve().parent
GUIDE = TESTS / "fixtures" / "guide"
EXPECTED = TESTS / "fixtures" / "expected"
SCHEMA = json.loads((TESTS.parent / "schema" / "symbol.schema.json").read_text(encoding="utf-8"))
JSON_SCHEMA = Draft202012Validator(SCHEMA)

LIBRARY = load_library(GUIDE)
N, S = Direction.N, Direction.S


def bare(**changes) -> Symbol:
    """A symbol with one line and nothing else, and whatever the test changes."""
    return replace(
        Symbol(
            name="t",
            kind=SymbolKind.ELEMENT,
            status=Status.UNVERIFIED,
            reference=Reference("X", "1"),
            elements=(Line(Point(0, 0), Point(0, 1)),),
        ),
        **changes,
    )


class TestToJson:
    def test_a_whole_number_has_no_decimal_point(self):
        assert to_json([2.0, 0.0, -3.0, 1e22, 7]) == (
            "[\n  2,\n  0,\n  -3,\n  10000000000000000000000,\n  7\n]\n"
        )

    def test_negative_zero_prints_as_zero(self):
        assert to_json([-0.0]) == "[\n  0\n]\n"

    def test_any_other_number_is_the_shortest_exact_decimal(self):
        assert to_json([0.1, -1.125, 0.30000000000000004, 1e-07]) == (
            "[\n  0.1,\n  -1.125,\n  0.30000000000000004,\n  1e-07\n]\n"
        )

    def test_keys_are_sorted_at_every_level_and_arrays_keep_their_order(self):
        text = to_json({"b": [3, 1, 2], "a": {"z": 1, "y": 2}})
        assert text == (
            '{\n  "a": {\n    "y": 2,\n    "z": 1\n  },\n  "b": [\n    3,\n    1,\n    2\n  ]\n}\n'
        )

    def test_text_is_utf8_unescaped_and_control_characters_are_escaped(self):
        text = to_json({"name": 'Ω "x"\r\n'})
        assert text == '{\n  "name": "Ω \\"x\\"\\r\\n"\n}\n'
        assert b"\r" not in text.encode("utf-8")

    def test_empty_containers_and_one_trailing_newline(self):
        assert to_json({"a": [], "b": {}}) == '{\n  "a": [],\n  "b": {}\n}\n'
        assert to_json({}).endswith("}\n")
        assert not to_json({}).endswith("\n\n")

    def test_non_finite_numbers_do_not_raise(self):
        text = to_json([float("nan"), float("inf"), float("-inf")])
        assert text == "[\n  NaN,\n  Infinity,\n  -Infinity\n]\n"

    @given(
        st.recursive(
            st.none()
            | st.booleans()
            | st.integers(-(10**6), 10**6)
            | st.floats(allow_nan=False, allow_infinity=False)
            | st.text(),
            lambda inner: (
                st.lists(inner, max_size=4) | st.dictionaries(st.text(), inner, max_size=4)
            ),
            max_leaves=12,
        )
    )
    def test_the_text_parses_back_to_the_same_data(self, data):
        assert json.loads(to_json(data)) == data

    @given(st.floats(allow_nan=False, allow_infinity=False))
    def test_a_number_parses_back_to_the_same_value(self, value):
        assert json.loads(to_json([value])) == [value]


class TestGolden:
    def test_the_make_contact_matches_its_reviewed_file_byte_for_byte(self):
        golden = (EXPECTED / "S00227.json").read_bytes()
        assert to_json(symbol_to_data(LIBRARY.get("S00227"))).encode("utf-8") == golden

    def test_the_two_symbol_bundle_matches_its_reviewed_file_byte_for_byte(self):
        library = Library(
            "IEC 60617",
            "ignored",
            "ignored",
            {"S00227": LIBRARY.get("S00227"), "S00016": LIBRARY.get("S00016")},
        )
        golden = (EXPECTED / "bundle.json").read_bytes()
        assert to_json(bundle_to_data(library)).encode("utf-8") == golden


class TestSymbolToData:
    def test_the_key_set_of_a_minimal_symbol_is_explicit(self):
        assert set(symbol_to_data(bare())) == {
            "schema",
            "name",
            "kind",
            "status",
            "reference",
            "ports",
            "nodes",
            "paths",
            "anchors",
            "elements",
            "slots",
            "body_box",
            "keepout_box",
        }

    def test_slots_are_always_written_as_a_table(self):
        assert symbol_to_data(bare())["slots"] == {}

    def test_optional_keys_appear_only_when_set(self):
        data = symbol_to_data(
            bare(
                reference=Reference("X", "1", "2020", "form 2"),
                pole_pitch=8,
                lint_allow=(Allow("slot-missing", "why"),),
            )
        )
        assert data["reference"] == {
            "standard": "X",
            "number": "1",
            "edition": "2020",
            "form": "form 2",
        }
        assert data["pole_pitch"] == 8
        assert data["lint_allow"] == [{"rule": "slot-missing", "reason": "why"}]
        plain = symbol_to_data(bare())
        assert plain["reference"] == {"standard": "X", "number": "1"}
        assert "pole_pitch" not in plain
        assert "lint_allow" not in plain

    def test_every_element_writes_all_of_its_default_keys(self):
        symbol = bare(
            elements=(
                Line(Point(0, 0), Point(1, 1)),
                Polyline((Point(0, 0), Point(1, 0), Point(1, 1))),
                Circle(Point(0, 0), 0.5),
                Arc(Point(0, 0), 1, 0, 90),
                Text("M", Point(0, 0), 1),
            )
        )
        assert symbol_to_data(symbol)["elements"] == [
            {"line": [[0, 0], [1, 1]], "weight": "normal", "style": "solid"},
            {
                "polyline": [[0, 0], [1, 0], [1, 1]],
                "closed": False,
                "fill": "none",
                "weight": "normal",
                "style": "solid",
            },
            {"circle": [0, 0], "r": 0.5, "fill": "none", "weight": "normal"},
            {"arc": [0, 0], "r": 1, "start": 0, "end": 90, "weight": "normal", "style": "solid"},
            {"text": "M", "at": [0, 0], "height": 1, "weight": "normal"},
        ]

    def test_a_bound_leads_port_is_written_only_when_set(self):
        symbol = bare(
            elements=(Line(Point(0, -2), Point(0, -1), port="in"), Line(Point(0, 2), Point(0, 1)))
        )
        bound, unbound = symbol_to_data(symbol)["elements"]
        assert bound["port"] == "in"
        assert "port" not in unbound

    def test_non_default_element_values_are_written_as_names(self):
        symbol = bare(
            elements=(
                Polyline(
                    (Point(0, 0), Point(1, 0)),
                    closed=True,
                    fill=Fill.SOLID,
                    weight=Weight.THICK,
                    style=Style.DASHED,
                ),
            )
        )
        (element,) = symbol_to_data(symbol)["elements"]
        assert (element["closed"], element["fill"], element["weight"], element["style"]) == (
            True,
            "solid",
            "thick",
            "dashed",
        )

    def test_ports_are_an_array_with_their_description(self):
        symbol = bare(ports=(Port("in", Point(0, -2), N, "top"), Port("out", Point(0, 2), S)))
        assert symbol_to_data(symbol)["ports"] == [
            {"id": "in", "at": [0, -2], "dir": "N", "description": "top"},
            {"id": "out", "at": [0, 2], "dir": "S", "description": ""},
        ]

    def test_nodes_list_the_implicit_single_port_nodes_too(self):
        symbol = bare(
            ports=(Port("a", Point(0, 0), N), Port("b", Point(1, 0), N), Port("c", Point(2, 0), N)),
            nodes=(Node(("b",), "earth"),),
        )
        assert symbol_to_data(symbol)["nodes"] == [
            {"ports": ["b"], "potential": "earth"},
            {"ports": ["a"]},
            {"ports": ["c"]},
        ]

    def test_paths_anchors_and_slots(self):
        symbol = bare(
            paths=(Path("in", "out", "diode", through=True),),
            anchors=(Anchor("link", Point(-0.5, 0), Direction.W),),
            slots=(Slot("tag", Point(1, 2), Direction.E, (6, 1)),),
        )
        data = symbol_to_data(symbol)
        assert data["paths"] == [{"from": "in", "to": "out", "kind": "diode", "through": True}]
        assert data["anchors"] == [{"id": "link", "at": [-0.5, 0], "dir": "W"}]
        assert data["slots"] == {"tag": {"at": [1, 2], "side": "E", "box": [6, 1]}}

    def test_the_boxes_are_the_base_orientation_boxes(self):
        data = symbol_to_data(LIBRARY.get("S00227"))
        assert data["body_box"] == [[-1, -2], [0, 2]]
        assert data["keepout_box"] == [[-7.5, -2], [1.75, 2]]

    def test_there_are_no_parts(self):
        assert "parts" not in symbol_to_data(LIBRARY.get("S00254"))

    def test_a_hand_built_symbol_with_non_finite_numbers_does_not_raise(self):
        nan, inf = float("nan"), float("inf")
        symbol = bare(
            elements=(Line(Point(nan, 0), Point(inf, 1)), Arc(Point(0, 0), 1, inf, nan)),
            ports=(Port("a", Point(inf, nan), N),),
        )
        assert "NaN" in to_json(symbol_to_data(symbol))


class TestBundleToData:
    def test_it_has_exactly_the_three_keys_of_the_guide(self):
        data = bundle_to_data(LIBRARY)
        assert set(data) == {"schema", "standard", "symbols"}
        assert data["schema"] == 1
        assert data["standard"] == "IEC 60617"

    def test_symbols_are_keyed_by_number_and_hold_the_resolved_form(self):
        data = bundle_to_data(LIBRARY)
        numbers = [s.reference.number for s in LIBRARY]
        assert list(data["symbols"]) == sorted(data["symbols"]) == numbers
        assert data["symbols"]["S00227"] == symbol_to_data(LIBRARY.get("S00227"))


# -- the round trip

GUIDE_SYMBOLS = list(LIBRARY)


@pytest.mark.parametrize("symbol", GUIDE_SYMBOLS, ids=lambda s: s.reference.number)
def test_every_guide_symbol_round_trips(symbol):
    assert round_trips(symbol)


@pytest.mark.parametrize("symbol", GUIDE_SYMBOLS, ids=lambda s: s.reference.number)
def test_every_guide_symbol_round_trips_through_json_text(symbol):
    data = json.loads(to_json(symbol_to_data(symbol)))
    assert symbol_from_data(data) == normalised(symbol)


def test_a_repeated_symbol_round_trips():
    assert round_trips(repeat(LIBRARY.get("S00227"), 3))


def test_a_bound_lead_round_trips():
    assert round_trips(
        bare(
            ports=(Port("in", Point(0, -2), N),),
            elements=(Line(Point(0, -2), Point(0, -1), port="in"),),
        )
    )


def test_a_hand_built_symbol_with_an_implicit_node_round_trips():
    symbol = bare(
        ports=(Port("a", Point(0, -2), N), Port("b", Point(0, 2), S, "second")),
        anchors=(Anchor("k", Point(0, 0), Direction.E),),
        slots=(
            Slot("tag", Point(1, 0), Direction.E, (2, 1)),
            Slot("marking.a", Point(0, 0), N, (1, 1)),
        ),
    )
    assert normalised(symbol).nodes == (Node(("a",)), Node(("b",)))
    assert round_trips(symbol)


@pytest.mark.parametrize("symbol", GUIDE_SYMBOLS, ids=lambda s: s.reference.number)
def test_the_resolved_data_of_a_guide_symbol_validates_with_both_validators(symbol):
    data = json.loads(to_json(symbol_to_data(symbol)))
    assert validate(data) == ()
    assert JSON_SCHEMA.is_valid(data)


def test_the_repeated_symbol_validates_with_both_validators():
    data = json.loads(to_json(symbol_to_data(repeat(LIBRARY.get("S00227"), 3))))
    assert validate(data) == ()
    assert JSON_SCHEMA.is_valid(data)


def dropping_descriptions(symbol):
    """A faulty serialiser: it forgets port descriptions."""
    data = symbol_to_data(symbol)
    data["ports"] = [{k: v for k, v in p.items() if k != "description"} for p in data["ports"]]
    return data


def dropping_slots(symbol):
    """A faulty serialiser: it forgets the slots."""
    return {**symbol_to_data(symbol), "slots": {}}


def test_the_round_trip_check_can_fail():
    described = bare(ports=(Port("a", Point(0, 0), N, "text"),))
    assert round_trips(described)
    assert not round_trips(described, dropping_descriptions)
    assert not round_trips(LIBRARY.get("S00227"), dropping_slots)


_grid = st.integers(-64, 64).map(lambda n: n / 8)
_points = st.builds(Point, _grid, _grid)
_radii = st.integers(1, 32).map(lambda n: n / 8)
_angles = st.integers(0, 71).map(lambda n: n * 5.0)
_ids = st.text("abc12", min_size=1, max_size=3)
_names = st.text(max_size=6)
_weights = st.sampled_from(Weight)
_styles = st.sampled_from(Style)
_fills = st.sampled_from(Fill)
_directions = st.sampled_from(Direction)
_elements = st.one_of(
    st.builds(Line, _points, _points, _weights, _styles, st.none() | _ids),
    st.builds(
        Polyline,
        st.lists(_points, max_size=4).map(tuple),
        st.booleans(),
        _fills,
        _weights,
        _styles,
    ),
    st.builds(Circle, _points, _radii, _fills, _weights),
    st.builds(Arc, _points, _radii, _angles, _angles, _weights, _styles),
    st.builds(Text, _names, _points, _radii, _weights),
)
_symbols = st.builds(
    Symbol,
    name=_names,
    kind=st.sampled_from(SymbolKind),
    status=st.sampled_from(Status),
    reference=st.builds(Reference, _names, _names, st.none() | _names, st.none() | _names),
    elements=st.lists(_elements, max_size=5).map(tuple),
    ports=st.lists(st.builds(Port, _ids, _points, _directions, _names), max_size=3).map(tuple),
    nodes=st.lists(
        st.builds(
            Node,
            st.lists(_ids, max_size=2).map(tuple),
            st.none() | st.sampled_from(("earth", "protective_earth", "functional_earth", "frame")),
        ),
        max_size=2,
    ).map(tuple),
    paths=st.lists(
        st.builds(
            Path,
            _ids,
            _ids,
            st.sampled_from(
                ("conductor", "switch_open", "switch_closed", "impedance", "source", "diode")
            ),
            st.booleans(),
        ),
        max_size=2,
    ).map(tuple),
    anchors=st.lists(st.builds(Anchor, _ids, _points, _directions), max_size=2).map(tuple),
    slots=st.lists(
        st.builds(Slot, _ids, _points, _directions, st.tuples(_radii, _radii)),
        max_size=3,
        unique_by=lambda slot: slot.id,
    ).map(tuple),
    pole_pitch=st.none() | st.sampled_from([4, 8, 12]),
    lint_allow=st.lists(st.builds(Allow, _ids, _names), max_size=2).map(tuple),
)


@settings(max_examples=300)
@given(_symbols)
def test_any_generated_symbol_round_trips_through_json_text(symbol):
    data = json.loads(to_json(symbol_to_data(symbol)))
    assert symbol_from_data(data) == normalised(symbol)


@settings(max_examples=300)
@given(_symbols)
def test_the_generated_resolved_data_validates_with_both_validators(symbol):
    data = json.loads(to_json(symbol_to_data(symbol)))
    assert validate(data) == ()
    assert JSON_SCHEMA.is_valid(data)


@given(_symbols)
def test_the_json_text_has_no_carriage_return_and_ends_in_one_newline(symbol):
    text = to_json(symbol_to_data(symbol))
    assert "\r" not in text
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")
