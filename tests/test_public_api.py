"""The public names of guide section 11 import from the package, and its consumer snippet runs."""

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
