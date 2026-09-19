"""`to_svg` is total: whatever floats and strings a hand-built symbol carries, it returns XML."""

import math
import xml.etree.ElementTree as ET

import deal
import pytest
from build_symbol import plain_symbol
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import graphical_symbols.svg as svg_module
from graphical_symbols import (
    Anchor,
    Arc,
    Circle,
    Direction,
    Fill,
    Line,
    Point,
    Polyline,
    Port,
    Reference,
    Slot,
    Status,
    Style,
    Symbol,
    SymbolKind,
    Text,
    Weight,
    to_svg,
)

_SLOT_IDS = ["tag", "value", "marking.a", "marking.b", ""]

_floats = st.one_of(
    st.floats(allow_nan=True, allow_infinity=True),
    st.sampled_from(
        [math.nan, math.inf, -math.inf, 1e300, -1e300, 1e-300, 0.0, -0.0, 90.0, -450.0]
    ),
)
_points = st.builds(Point, _floats, _floats)
_strings = st.text(
    st.one_of(
        st.characters(),
        st.sampled_from(list("\r\n\t\x00\x0b\udfff\ud800\U0000fffe\U0000ffff&<>\"'")),
    ),
    max_size=12,
)
_weights, _styles, _fills = st.sampled_from(Weight), st.sampled_from(Style), st.sampled_from(Fill)
_directions = st.sampled_from(Direction)
_elements = st.one_of(
    st.builds(Line, _points, _points, _weights, _styles),
    st.builds(
        Polyline,
        st.lists(_points, max_size=4).map(tuple),
        st.booleans(),
        _fills,
        _weights,
        _styles,
    ),
    st.builds(Circle, _points, _floats, _fills, _weights),
    st.builds(Arc, _points, _floats, _floats, _floats, _weights, _styles),
    st.builds(Text, _strings, _points, _floats, _weights),
)
_symbols = st.builds(
    Symbol,
    name=_strings,
    kind=st.sampled_from(SymbolKind),
    status=st.sampled_from(Status),
    reference=st.just(Reference("X", "1")),
    elements=st.lists(_elements, max_size=4).map(tuple),
    ports=st.lists(st.builds(Port, _strings, _points, _directions), max_size=4).map(tuple),
    anchors=st.lists(st.builds(Anchor, _strings, _points, _directions), max_size=3).map(tuple),
    slots=st.lists(
        st.builds(
            Slot, st.sampled_from(_SLOT_IDS), _points, _directions, st.tuples(_floats, _floats)
        ),
        max_size=4,
    ).map(tuple),
)
_texts = st.one_of(
    st.none(), st.dictionaries(st.sampled_from([*_SLOT_IDS, "unknown"]), _strings, max_size=4)
)


def render_both_modes(symbol, texts=None, module_mm=2.5):
    """Render plain and annotated, check both parse as XML with no carriage return."""
    for annotate in (False, True):
        out = to_svg(symbol, module_mm=module_mm, annotate=annotate, texts=texts)
        assert "\r" not in out
        assert out.endswith("</svg>\n")
        ET.fromstring(out)  # noqa: S314 - parses this library's own output


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_symbols, _texts, _floats)
def test_to_svg_never_raises_and_always_writes_xml(symbol, texts, module_mm):
    render_both_modes(symbol, texts, module_mm)


def base(**changes):
    return plain_symbol(**{"elements": (), **changes})


@pytest.mark.parametrize("angle", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", ["start_deg", "end_deg"])
def test_an_arc_with_a_non_finite_angle_renders(angle, field):
    start, end = (angle, 100.0) if field == "start_deg" else (10.0, angle)
    render_both_modes(base(elements=(Arc(Point(0, 0), 1, start, end),)))


def test_empty_symbols_and_empty_tuples_render():
    render_both_modes(base())
    render_both_modes(base(elements=(Polyline(()),), ports=(), anchors=(), slots=()), {"tag": "x"})


def test_a_huge_text_and_huge_coordinates_render():
    slot = Slot("tag", Point(1e300, -1e300), Direction.E, (1e300, 1e300))
    symbol = base(
        elements=(Text("x" * 100_000, Point(0, 0), 1e300), Circle(Point(1e300, 0), math.inf)),
        slots=(slot,),
        ports=(Port("p" * 1000, Point(-1e300, 1e300), Direction.W),),
    )
    render_both_modes(symbol, {"tag": "y" * 100_000})


@pytest.mark.parametrize("box", [(0.0, 0.0), (-1.0, -1.0), (math.nan, 1.0), (1.0, math.nan)])
@pytest.mark.parametrize("side", list(Direction))
def test_a_slot_without_a_positive_box_renders(box, side):
    slot = Slot("tag", Point(0, 0), side, box)
    render_both_modes(base(slots=(slot,)), {"tag": "-K1"})


def test_the_property_can_fail_when_arc_point_raises_on_a_non_finite_angle(monkeypatch):
    def raising(arc, degrees):
        if not math.isfinite(degrees):
            msg = "angle is not finite"
            raise ValueError(msg)
        return Point(arc.center.x, arc.center.y)

    monkeypatch.setattr(svg_module, "arc_point", raising)
    with pytest.raises((ValueError, deal.ContractError)):
        render_both_modes(base(elements=(Arc(Point(0, 0), 1, math.inf, 0),)))


def test_the_property_can_fail_when_the_number_formatter_raises_on_nan(monkeypatch):
    def raising(value):
        if math.isnan(value):
            msg = "nan"
            raise ValueError(msg)
        return "0"

    monkeypatch.setattr(svg_module, "_num", raising)
    with pytest.raises((ValueError, deal.ContractError)):
        render_both_modes(base(elements=(Line(Point(math.nan, 0), Point(1, 1)),)))
