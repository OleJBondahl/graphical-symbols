"""Anchors group: `anchor-duplicate-id` and `anchor-off-geometry`."""

import math

from build_symbol import plain_symbol

from graphical_symbols.geometry import Arc, Circle, Direction, Fill, Line, Point, Polyline, Text
from graphical_symbols.lint.anchors import anchor_duplicate_id, anchor_off_geometry
from graphical_symbols.model import Anchor, Severity

P = Point


def anchor(at, id_="link"):
    return Anchor(id_, at, Direction.W)


class TestAnchorDuplicateId:
    def test_distinct_ids_are_clean(self):
        symbol = plain_symbol(anchors=(anchor(P(0, 0), "a"), anchor(P(0, 0), "b")))
        assert anchor_duplicate_id(symbol) == ()

    def test_no_anchors_are_clean(self):
        assert anchor_duplicate_id(plain_symbol()) == ()

    def test_a_shared_id_fires_at_the_later_anchor(self):
        symbol = plain_symbol(anchors=(anchor(P(0, 0)), anchor(P(0, 1), "b"), anchor(P(0, 1))))
        (found,) = anchor_duplicate_id(symbol)
        assert (found.rule, found.severity, found.location) == (
            "anchor-duplicate-id",
            Severity.ERROR,
            "anchors[2]",
        )
        assert "'link'" in found.message
        assert "anchors[0]" in found.message

    def test_three_with_one_id_give_two_findings(self):
        symbol = plain_symbol(anchors=(anchor(P(0, 0)), anchor(P(0, 0)), anchor(P(0, 0))))
        assert [f.location for f in anchor_duplicate_id(symbol)] == ["anchors[1]", "anchors[2]"]

    def test_ids_are_compared_exactly(self):
        symbol = plain_symbol(anchors=(anchor(P(0, 0), "a"), anchor(P(0, 0), "A")))
        assert anchor_duplicate_id(symbol) == ()


class TestAnchorOffGeometry:
    def test_an_anchor_on_a_line_is_clean(self):
        symbol = plain_symbol(anchors=(anchor(P(0, 0.5)),))
        assert anchor_off_geometry(symbol) == ()

    def test_an_anchor_off_every_element_is_a_warning_at_the_anchor(self):
        symbol = plain_symbol(anchors=(anchor(P(0, 0.5), "a"), anchor(P(1, 0.5), "b")))
        (found,) = anchor_off_geometry(symbol)
        assert (found.rule, found.severity, found.location) == (
            "anchor-off-geometry",
            Severity.WARNING,
            "anchors[1]",
        )
        assert "'b'" in found.message

    def test_a_symbol_without_elements_has_every_anchor_off_geometry(self):
        symbol = plain_symbol(elements=(), anchors=(anchor(P(0, 0)),))
        assert len(anchor_off_geometry(symbol)) == 1

    def test_the_shapes_the_guide_names(self):
        symbol = plain_symbol(
            elements=(
                Polyline((P(0, 0), P(2, 0), P(2, 2)), closed=True),
                Circle(P(5, 0), 1),
                Arc(P(9, 0), 1, 0, 90),
                Circle(P(12, 0), 1, fill=Fill.SOLID),
                Polyline((P(20, 0), P(22, 0), P(22, 2), P(20, 2)), closed=True, fill=Fill.SOLID),
            ),
            anchors=(
                anchor(P(1, 0), "on_outline"),
                anchor(P(1, 1), "closing_segment"),
                anchor(P(5, 1), "on_circle"),
                anchor(P(9, 1), "on_arc"),
                anchor(P(12, 0), "in_filled_circle"),
                anchor(P(21, 1), "in_filled_outline"),
            ),
        )
        assert anchor_off_geometry(symbol) == ()

    def test_the_inside_of_an_unfilled_shape_is_off_geometry(self):
        symbol = plain_symbol(
            elements=(
                Polyline((P(0, 0), P(2, 0), P(2, 2), P(0, 2)), closed=True),
                Circle(P(5, 1), 1),
            ),
            anchors=(anchor(P(1, 1), "square"), anchor(P(5, 1), "ring")),
        )
        assert [f.location for f in anchor_off_geometry(symbol)] == ["anchors[0]", "anchors[1]"]

    def test_an_arc_anchor_outside_the_sweep_is_off_geometry(self):
        symbol = plain_symbol(
            elements=(Arc(P(0, 0), 1, 0, 90),), anchors=(anchor(P(-1, 0)), anchor(P(0, 1)))
        )
        assert [f.location for f in anchor_off_geometry(symbol)] == ["anchors[0]"]

    def test_text_is_not_geometry(self):
        symbol = plain_symbol(elements=(Text("M", P(0, 0), 1),), anchors=(anchor(P(0, 0)),))
        assert len(anchor_off_geometry(symbol)) == 1

    def test_the_tolerance_is_1e_9(self):
        symbol = plain_symbol(anchors=(anchor(P(5e-10, 0.5), "in"), anchor(P(2e-9, 0.5), "out")))
        assert [f.location for f in anchor_off_geometry(symbol)] == ["anchors[1]"]

    def test_odd_floats_never_raise(self):
        symbol = plain_symbol(
            elements=(Line(P(0, 0), P(math.inf, 1)),),
            anchors=(anchor(P(math.nan, 0)), anchor(P(math.inf, math.inf))),
        )
        anchor_off_geometry(symbol)
        anchor_off_geometry(plain_symbol(elements=(Line(P(1, 1), P(1, 1)),)))
