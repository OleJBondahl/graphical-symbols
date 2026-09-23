"""The public names of guide section 11 import from the package, and its consumer snippet runs."""

import dataclasses
import inspect
from pathlib import Path

import pytest

import graphical_symbols
from graphical_symbols import (
    Box,
    Element,
    Orientation,
    Symbol,
    body_box,
    keepout_box,
    lint,
    load_library,
    orient,
    repeat,
    slot_box,
    to_svg,
)

GUIDE_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "guide"

# Guide section 11's API block, plus `Element` (the block writes it as the union of the shapes).
SECTION_11_NAMES = [
    *("Point", "Box", "Direction", "Orientation", "PathKind", "Line", "Polyline", "Circle", "Arc"),
    *("Text", "Port", "Node", "Path", "Anchor", "Slot", "Reference", "Symbol", "Library"),
    *("Finding", "load_library", "load_bundle", "orient", "translate", "repeat", "body_box"),
    *("keepout_box", "slot_box", "lint", "to_svg", "write_build", "stale_build", "Element"),
]


@pytest.mark.parametrize("name", SECTION_11_NAMES)
def test_a_section_11_name_is_public(name):
    assert name in graphical_symbols.__all__
    assert getattr(graphical_symbols, name) is not None


def test_the_placement_type_is_the_consumers_own():
    assert "Placement" not in graphical_symbols.__all__
    assert not hasattr(graphical_symbols, "Placement")


def test_the_guide_drawing_library_snippet_runs_on_the_guide_fixtures():
    # The guide's `from iec60617 import LIBRARY`, with the guide fixtures as the library and
    # S00227 (a make contact, one through path) in place of S00287. The `Placement` is left out.
    library = load_library(GUIDE_FIXTURES)
    breaker = orient(repeat(library.get("S00227"), 3), Orientation.R0)

    assert isinstance(breaker, Symbol)
    assert lint(breaker) == ()
    markings = {"1.in": "1", "1.out": "2", "2.in": "3", "2.out": "4", "3.in": "5", "3.out": "6"}
    assert set(markings) == {port.id for port in breaker.ports}

    keepout = keepout_box(breaker)
    assert isinstance(keepout, Box)
    assert keepout.min.x <= body_box(breaker).min.x
    assert keepout.max.x >= body_box(breaker).max.x
    assert all(isinstance(slot_box(slot), Box) for slot in breaker.slots)
    assert all(isinstance(element, Element) for element in breaker.elements)
    assert to_svg(breaker).startswith("<svg")


def shape(function):
    """Return the parameters of a function as (name, kind, default), the way a caller sees them."""
    return [
        (p.name, p.kind.name, "-" if p.default is p.empty else repr(p.default))
        for p in inspect.signature(function).parameters.values()
    ]


def positional(*names):
    return [(name, "POSITIONAL_OR_KEYWORD", "-") for name in names]


# Guide section 11's API block: the sibling repo `iec60617` codes against these exactly.
SECTION_11_SIGNATURES = {
    "load_library": positional("root"),
    "load_bundle": positional("json_path"),
    "orient": positional("symbol", "orientation"),
    "translate": positional("symbol", "dx", "dy"),
    "repeat": positional("symbol", "n"),
    "body_box": positional("symbol"),
    "keepout_box": positional("symbol"),
    "slot_box": positional("slot"),
    "lint": positional("symbol"),
    "to_svg": [
        *positional("symbol"),
        ("module_mm", "KEYWORD_ONLY", "2.5"),
        ("annotate", "KEYWORD_ONLY", "False"),
        ("texts", "KEYWORD_ONLY", "None"),
    ],
    "write_build": positional("library", "root"),
    "stale_build": positional("library", "root"),
}


@pytest.mark.parametrize("name", SECTION_11_SIGNATURES)
def test_a_section_11_function_has_the_guides_signature(name):
    assert shape(getattr(graphical_symbols, name)) == SECTION_11_SIGNATURES[name]


# The field order of each section 11 dataclass. `Symbol` ends with `lint_allow`, which the guide's
# block does not list (D1); `Library` also has `get`, `__iter__` and `__len__`.
SECTION_11_FIELDS = {
    "Point": ["x", "y"],
    "Box": ["min", "max"],
    "Line": ["start", "end", "weight", "style", "port"],
    "Polyline": ["points", "closed", "fill", "weight", "style"],
    "Circle": ["center", "radius", "fill", "weight"],
    "Arc": ["center", "radius", "start_deg", "end_deg", "weight", "style"],
    "Text": ["content", "position", "height", "weight"],
    "Port": ["id", "position", "direction", "description"],
    "Node": ["ports", "potential"],
    "Path": ["from_port", "to_port", "kind", "through"],
    "Anchor": ["id", "position", "direction"],
    "Slot": ["id", "position", "side", "box"],
    "Reference": ["standard", "number", "edition", "form"],
    "Symbol": [
        *("name", "kind", "status", "reference", "elements", "ports", "nodes", "paths"),
        *("anchors", "slots", "pole_pitch", "lint_allow"),
    ],
    "Library": ["standard", "title", "number_pattern", "symbols"],
    "Finding": ["rule", "severity", "message", "location", "orientation"],
}


@pytest.mark.parametrize("name", SECTION_11_FIELDS)
def test_a_section_11_dataclass_has_the_guides_fields_in_order(name):
    cls = getattr(graphical_symbols, name)
    assert [field.name for field in dataclasses.fields(cls)] == SECTION_11_FIELDS[name]


def test_the_library_methods_are_the_guides():
    assert shape(graphical_symbols.Library.get) == positional("self", "number")
    assert callable(graphical_symbols.Library.__iter__)
    assert callable(graphical_symbols.Library.__len__)


def test_the_signature_check_can_fail():
    def to_svg_positional(symbol, module_mm=2.5, annotate=False, texts=None): ...  # noqa: FBT002

    def to_svg_renamed(symbol, *, module=2.5, annotate=False, texts=None): ...

    def to_svg_no_default(symbol, *, module_mm, annotate=False, texts=None): ...

    for wrong in (to_svg_positional, to_svg_renamed, to_svg_no_default):
        assert shape(wrong) != SECTION_11_SIGNATURES["to_svg"]
