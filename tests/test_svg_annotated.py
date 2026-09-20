"""The annotated renderer and the sample texts: what is drawn, where, and never clipped."""

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

from graphical_symbols import (
    Anchor,
    Direction,
    Line,
    Orientation,
    Point,
    Polyline,
    Port,
    Reference,
    Slot,
    Status,
    Symbol,
    SymbolKind,
    body_box,
    keepout_box,
    orient,
    slot_box,
    to_svg,
)
from graphical_symbols.build import load_library
from graphical_symbols.gallery import sample_texts

GUIDE = Path(__file__).resolve().parent / "fixtures" / "guide"
LIBRARY = load_library(GUIDE)
NS = {"s": "http://www.w3.org/2000/svg"}
TOL = 1e-9
PRINT_TOL = 1e-4  # numbers are written with 4 decimals
E, W, N, S = Direction.E, Direction.W, Direction.N, Direction.S
ANNOTATION_CLASSES = [
    "annotation",
    "grid",
    "body-box",
    "keepout-box",
    "slot-box",
    "slot-id",
    "anchor",
    "anchor-id",
    "lane",
    "port",
    "port-id",
]


def sym(*elements, ports=(), anchors=(), slots=()):
    return Symbol(
        name="t",
        kind=SymbolKind.SYMBOL,
        status=Status.UNVERIFIED,
        reference=Reference("X", "1"),
        elements=tuple(elements),
        ports=tuple(ports),
        anchors=tuple(anchors),
        slots=tuple(slots),
    )


def parse(svg):
    return ET.fromstring(svg)  # noqa: S314 - parses this library's own output


def by_class(root, name):
    return [e for e in root.iter() if e.get("class") == name]


def view_of(root):
    x, y, w, h = (float(v) for v in root.get("viewBox").split())
    return x, y, x + w, y + h


def full_symbol():
    """A body, two ports, one anchor and three slots, one of each kind of side."""
    return sym(
        Polyline((Point(-1, -1), Point(1, -1), Point(1, 1), Point(-1, 1)), closed=True),
        Line(Point(0, -3), Point(0, -1)),
        Line(Point(0, 1), Point(0, 3)),
        ports=(Port("in", Point(0, -3), N), Port("out", Point(0, 3), S)),
        anchors=(Anchor("link", Point(-0.5, 0), W),),
        slots=(
            Slot("tag", Point(-1.5, 0), W, (6, 1)),
            Slot("marking.in", Point(0.25, -2.5), E, (1.5, 1)),
            Slot("marking.out", Point(0.25, 2.5), E, (1.5, 1)),
        ),
    )


def annotated(symbol, texts=None):
    return parse(to_svg(symbol, annotate=True, texts=texts))


class TestPlainMode:
    def test_it_draws_no_annotation_even_for_a_symbol_with_ports_anchors_and_slots(self):
        out = to_svg(full_symbol())
        for name in ANNOTATION_CLASSES:
            assert f'class="{name}"' not in out

    def test_with_texts_it_draws_only_the_texts(self):
        out = to_svg(full_symbol(), texts={"tag": "-X1", "marking.in": "1"})
        for name in ANNOTATION_CLASSES:
            assert f'class="{name}"' not in out
        assert out.count('class="sample-text"') == 2

    def test_the_view_holds_the_slot_boxes_of_the_texts_and_nothing_else_of_the_slots(self):
        symbol = sym(Line(Point(0, 0), Point(2, 0)), slots=(Slot("tag", Point(-1, 0), W, (6, 1)),))
        assert parse(to_svg(symbol)).get("viewBox") == "-1 -1 4 2"
        with_text = parse(to_svg(symbol, texts={"tag": "x"}))
        assert with_text.get("viewBox") == "-8 -1.5 11 3"


class TestAnnotationClasses:
    def test_every_class_is_drawn_once_per_thing(self):
        root = annotated(full_symbol())
        assert len(by_class(root, "annotation")) == 1
        assert len(by_class(root, "body-box")) == 1
        assert len(by_class(root, "keepout-box")) == 1
        assert len(by_class(root, "slot-box")) == 3
        assert [t.text for t in by_class(root, "slot-id")] == ["marking.in", "marking.out", "tag"]
        assert len(by_class(root, "anchor")) == 1
        assert [t.text for t in by_class(root, "anchor-id")] == ["link"]
        assert len(by_class(root, "lane")) == 2
        assert len(by_class(root, "port")) == 2
        assert [t.text for t in by_class(root, "port-id")] == ["in", "out"]

    def test_the_draw_order_is_grid_boxes_slots_anchors_lanes_ports(self):
        out = to_svg(full_symbol(), annotate=True)
        order = ("grid", "body-box", "keepout-box", "slot-box", "anchor", "lane", "port")
        first = [out.index(f'class="{name}"') for name in order]
        assert first == sorted(first)
        assert len(set(first)) == len(first)

    def test_the_elements_are_drawn_under_the_annotations_and_the_texts_over_them(self):
        out = to_svg(full_symbol(), annotate=True, texts={"tag": "-X1"})
        assert out.index("<line") < out.index('class="annotation"') < out.index('class="samples"')

    def test_the_body_box_and_keepout_box_are_the_boxes_of_the_symbol(self):
        symbol = full_symbol()
        root = annotated(symbol)
        for name, box in (("body-box", body_box(symbol)), ("keepout-box", keepout_box(symbol))):
            (rect,) = by_class(root, name)
            assert rect.get("stroke-dasharray") == "0.2 0.2"
            assert (
                float(rect.get("x")),
                float(rect.get("y")),
                float(rect.get("width")),
                float(rect.get("height")),
            ) == (box.min.x, box.min.y, box.width, box.height)
        assert by_class(root, "body-box")[0].get("stroke") != by_class(root, "keepout-box")[0].get(
            "stroke"
        )

    @pytest.mark.parametrize("side", list(Direction))
    def test_a_slot_box_is_where_the_side_table_puts_it(self, side):
        slot = Slot("tag", Point(2, 3), side, (4, 1.5))
        (rect,) = by_class(annotated(sym(slots=(slot,))), "slot-box")
        box = slot_box(slot)
        assert (
            float(rect.get("x")),
            float(rect.get("y")),
            float(rect.get("width")),
            float(rect.get("height")),
        ) == (box.min.x, box.min.y, box.width, box.height)
        assert float(rect.get("fill-opacity")) < 0.5

    def test_the_slot_boxes_follow_the_guide_table_in_numbers(self):
        expected = {
            E: (2, 2.25, 4, 1.5),
            W: (-2, 2.25, 4, 1.5),
            N: (0, 1.5, 4, 1.5),
            S: (0, 3, 4, 1.5),
        }
        for side, numbers in expected.items():
            slot = Slot("tag", Point(2, 3), side, (4, 1.5))
            (rect,) = by_class(annotated(sym(slots=(slot,))), "slot-box")
            got = tuple(float(rect.get(k)) for k in ("x", "y", "width", "height"))
            assert got == numbers, side

    def test_an_anchor_is_a_diamond_on_its_position_with_its_id_beside_it(self):
        symbol = sym(anchors=(Anchor("link", Point(-0.5, 0), W), Anchor("up", Point(1, 2), N)))
        root = annotated(symbol)
        markers = by_class(root, "anchor")
        assert [m.get("d") for m in markers] == [
            "M -0.7 0 L -0.5 -0.2 L -0.3 0 L -0.5 0.2 Z",
            "M 0.8 2 L 1 1.8 L 1.2 2 L 1 2.2 Z",
        ]
        labels = by_class(root, "anchor-id")
        assert [t.text for t in labels] == ["link", "up"]
        # 0.75 M out along the direction, capitals centred on that point (font size 0.4).
        assert [(t.get("x"), t.get("y")) for t in labels] == [("-1.25", "0.144"), ("1", "1.394")]

    def test_a_port_has_a_marker_and_an_id_one_module_out(self):
        root = annotated(sym(ports=(Port("a", Point(2, 3), E),)))
        (marker,) = by_class(root, "port")
        assert (marker.get("cx"), marker.get("cy"), marker.get("r")) == ("2", "3", "0.2")
        (label,) = by_class(root, "port-id")
        assert (label.get("x"), label.get("y"), label.get("text-anchor")) == (
            "3",
            "3.216",
            "middle",
        )


class TestLanes:
    @pytest.mark.parametrize(
        ("direction", "expected"),
        [
            # x, y, width, height of the lane of a port at (2, 3), for a view of -3 .. 7 by -2 .. 8.
            (E, (2, 2.75, 5, 0.5)),
            (W, (-3, 2.75, 5, 0.5)),
            (N, (1.75, -2, 0.5, 5)),
            (S, (1.75, 3, 0.5, 5)),
        ],
    )
    def test_the_lane_runs_from_the_port_along_its_direction_to_the_view_edge(
        self, direction, expected
    ):
        symbol = sym(Line(Point(-2, -1), Point(6, 7)), ports=(Port("p", Point(2, 3), direction),))
        root = annotated(symbol)
        assert view_of(root) == (-3, -2, 7, 8)
        (lane,) = by_class(root, "lane")
        got = tuple(float(lane.get(k)) for k in ("x", "y", "width", "height"))
        assert got == expected
        assert float(lane.get("fill-opacity")) < 0.5

    @pytest.mark.parametrize("direction", list(Direction))
    def test_the_lane_is_half_a_module_wide_and_centred_on_the_port_line(self, direction):
        root = annotated(
            sym(Line(Point(0, 0), Point(4, 4)), ports=(Port("p", Point(2, 2), direction),))
        )
        (lane,) = by_class(root, "lane")
        x, y = float(lane.get("x")), float(lane.get("y"))
        w, h = float(lane.get("width")), float(lane.get("height"))
        across = h if direction in (E, W) else w
        centre = y + h / 2 if direction in (E, W) else x + w / 2
        assert across == 0.5
        assert centre == 2

    def test_the_lane_is_on_the_outer_side_of_the_port(self):
        root = annotated(full_symbol())
        _, vy0, _, vy1 = view_of(root)
        north, south = by_class(root, "lane")
        assert float(north.get("y")) == vy0
        assert float(north.get("y")) + float(north.get("height")) == pytest.approx(-3)
        assert float(south.get("y")) == 3
        assert float(south.get("y")) + float(south.get("height")) == pytest.approx(vy1)


def sample(root):
    (text,) = by_class(root, "sample-text")
    return text


class TestSampleTexts:
    @pytest.mark.parametrize(
        ("side", "anchor", "y"),
        [(E, "start", 3.36), (W, "end", 3.36), (N, "middle", 3), (S, "middle", 3.72)],
    )
    def test_the_alignment_follows_the_slot_side(self, side, anchor, y):
        symbol = sym(slots=(Slot("tag", Point(2, 3), side, (4, 1.5)),))
        text = sample(parse(to_svg(symbol, texts={"tag": "abc"})))
        assert text.text == "abc"
        assert text.get("x") == "2"
        assert text.get("text-anchor") == anchor
        assert float(text.get("y")) == pytest.approx(y)
        assert text.get("font-size") == "1"

    @pytest.mark.parametrize("side", list(Direction))
    @pytest.mark.parametrize("box", [(4, 1.5), (1.5, 1), (0.9, 2), (3, 0.5), (2, 0.3)])
    @pytest.mark.parametrize("content", ["a", "-X1", "marking.out", "10 A"])
    def test_the_text_lies_inside_the_slot_box(self, side, box, content):
        slot = Slot("tag", Point(2, 3), side, box)
        text = sample(parse(to_svg(sym(slots=(slot,)), texts={"tag": content})))
        size, x, baseline = (float(text.get(k)) for k in ("font-size", "x", "y"))
        width = 0.6 * size * len(content)
        x0 = {"start": x, "end": x - width, "middle": x - width / 2}[text.get("text-anchor")]
        top = baseline - 0.72 * size
        b = slot_box(slot)
        assert b.min.x - TOL <= x0
        assert x0 + width <= b.max.x + TOL
        assert b.min.y - PRINT_TOL <= top
        assert baseline <= b.max.y + PRINT_TOL

    @pytest.mark.parametrize(
        ("box", "content", "size"),
        [
            ((4, 1.5), "abc", "1"),
            ((1.5, 1), "1", "1"),
            ((1.5, 1), "abcde", "0.5"),
            ((6, 0.5), "-X1", "0.5"),
            ((0.6, 1), "ab", "0.5"),
            ((1, 1), "abc", "0.5555"),
            ((100, 100), "abc", "1"),
        ],
    )
    def test_the_size_is_the_largest_of_at_most_one_that_fits(self, box, content, size):
        slot = Slot("tag", Point(0, 0), E, box)
        text = sample(parse(to_svg(sym(slots=(slot,)), texts={"tag": content})))
        assert text.get("font-size") == size
        chosen = float(size)
        assert 0.6 * chosen * len(content) <= box[0] + TOL
        assert chosen <= box[1] + TOL
        bigger = chosen + 0.0001
        assert chosen == 1 or 0.6 * bigger * len(content) > box[0] or bigger > box[1]

    @pytest.mark.parametrize(
        "box", [(0, 1), (1, 0), (-1, 1), (1, -1), (math.nan, 1), (1, math.nan)]
    )
    def test_a_box_without_a_positive_size_gets_no_text(self, box):
        slot = Slot("tag", Point(0, 0), E, box)
        assert "sample-text" not in to_svg(sym(slots=(slot,)), texts={"tag": "-X1"})

    def test_an_empty_text_draws_nothing(self):
        symbol = sym(slots=(Slot("tag", Point(0, 0), E, (4, 1)),))
        assert to_svg(symbol, texts={"tag": ""}) == to_svg(symbol)

    def test_an_unknown_slot_id_is_ignored_and_a_known_one_is_still_drawn(self):
        symbol = sym(slots=(Slot("tag", Point(0, 0), E, (4, 1)),))
        out = to_svg(symbol, texts={"nope": "x", "tag": "-X1"})
        assert out.count('class="sample-text"') == 1

    def test_the_text_is_upright_unstroked_and_in_its_own_colour(self):
        symbol = full_symbol()
        root = annotated(symbol, {"tag": "-X1"})
        text = sample(root)
        assert text.get("stroke") == "none"
        assert text.get("fill") not in {"#000", "#d00", "#06c", "#0a0", "#a0a", "#088"}
        assert "transform" not in text.attrib
        assert "dominant-baseline" not in ET.tostring(text, encoding="unicode")

    def test_the_text_is_escaped(self):
        symbol = sym(slots=(Slot("tag", Point(0, 0), E, (8, 1)),))
        out = to_svg(symbol, texts={"tag": "a<&>\r"})
        assert "&lt;&amp;&gt;&#13;" in out
        assert sample(parse(out)).text == "a<&>\r"

    def test_it_is_deterministic_lf_only_and_ends_with_one_newline(self):
        symbol = full_symbol()
        texts = {"tag": "-X1", "marking.in": "1", "marking.out": "2"}
        out = to_svg(symbol, annotate=True, texts=texts)
        assert out == to_svg(symbol, annotate=True, texts=texts)
        assert "\r" not in out
        assert out.endswith("</svg>\n")
        assert not out.endswith("\n\n")


def inside(box, view):
    (x0, y0, x1, y1), (vx0, vy0, vx1, vy1) = box, view
    return vx0 - TOL <= x0 and vy0 - TOL <= y0 and x1 <= vx1 + TOL and y1 <= vy1 + TOL


def annotation_boxes(root):
    """Every box the annotation draws, from the SVG itself: (x0, y0, x1, y1) and a name."""
    boxes = []
    for e in root.iter():
        css = e.get("class")
        if css in ("body-box", "keepout-box", "slot-box", "lane"):
            x, y = float(e.get("x")), float(e.get("y"))
            boxes.append((css, (x, y, x + float(e.get("width")), y + float(e.get("height")))))
        elif css == "port":
            cx, cy = float(e.get("cx")), float(e.get("cy"))
            boxes.append((css, (cx - 0.2, cy - 0.2, cx + 0.2, cy + 0.2)))
        elif css == "anchor":
            xs = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", e.get("d"))][0::2]
            ys = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", e.get("d"))][1::2]
            boxes.append((css, (min(xs), min(ys), max(xs), max(ys))))
        elif css in ("port-id", "anchor-id", "slot-id", "sample-text"):
            x, y, size = (float(e.get(k)) for k in ("x", "y", "font-size"))
            width = 0.6 * size * len(e.text)
            anchor = e.get("text-anchor")
            x0 = {"start": x, "end": x - width, "middle": x - width / 2}[anchor]
            boxes.append((css, (x0, y - 0.72 * size, x0 + width, y)))
    return boxes


class TestTheViewHoldsEverything:
    @pytest.mark.parametrize("with_texts", [False, True])
    @pytest.mark.parametrize("number", sorted(LIBRARY.symbols))
    def test_every_annotation_of_a_guide_symbol_is_inside_the_view(self, number, with_texts):
        symbol = LIBRARY.get(number)
        root = annotated(symbol, sample_texts(symbol) if with_texts else None)
        view = view_of(root)
        found = annotation_boxes(root)
        assert found
        for name, box in found:
            assert inside(box, view), (number, name, box, view)

    def test_the_view_is_the_keepout_box_the_label_boxes_and_the_lane_starts_plus_one_module(self):
        symbol = sym(
            Line(Point(0, 0), Point(2, 0)),
            ports=(Port("a_long_port_id", Point(2, 0), E),),
            anchors=(Anchor("an_anchor_id", Point(0, 0), W),),
        )
        vx0, vy0, vx1, vy1 = view_of(annotated(symbol))
        # Port label: centred 1 M east of (2, 0), 0.3 M per character on each side: to 3 + 4.2.
        assert vx1 == pytest.approx(3 + 0.3 * len("a_long_port_id") + 1)
        # Anchor label: centred 0.75 M west of (0, 0), 0.2 M per character: to -0.75 - 2.4.
        assert vx0 == pytest.approx(-0.75 - 0.2 * len("an_anchor_id") - 1)
        assert (vy0, vy1) == pytest.approx((-1.3, 1.3))

    def test_a_port_beyond_the_body_still_has_its_lane_start_in_view(self):
        root = annotated(sym(ports=(Port("p", Point(5, 5), N),)))
        assert inside((4.75, 5, 5.25, 5), view_of(root))

    def test_a_slot_label_wider_than_its_box_is_inside_the_view(self):
        symbol = sym(slots=(Slot("marking.out", Point(0, 0), E, (1, 1)),))
        root = annotated(symbol)
        (label,) = by_class(root, "slot-id")
        assert inside((0, -0.9, 0.18 * len("marking.out"), -0.5), view_of(root))
        assert label.text == "marking.out"


class TestGuideSymbols:
    def test_the_dashed_link_of_the_push_button_is_drawn_dashed(self):
        out = to_svg(LIBRARY.get("S00254"))
        assert out.count('stroke-dasharray="0.5 0.25"') == 1
        assert '<line x1="-0.5" y1="0" x2="-2.5" y2="0" stroke-width="0.1" ' in out

    def test_the_lanes_of_the_change_over_contact_leave_the_three_ports_outward(self):
        symbol = LIBRARY.get("S00230")
        root = annotated(symbol)
        _, vy0, _, vy1 = view_of(root)
        lanes = {
            port.id: tuple(float(lane.get(k)) for k in ("x", "y", "width", "height"))
            for port, lane in zip(symbol.ports, by_class(root, "lane"), strict=True)
        }
        assert lanes["com"] == pytest.approx((-0.25, 2, 0.5, vy1 - 2))
        assert lanes["no"] == pytest.approx((-0.25, vy0, 0.5, -2 - vy0))
        assert lanes["nc"] == pytest.approx((-2.25, vy0, 0.5, -2 - vy0))

    def test_the_connection_point_has_four_lanes_out_of_one_point(self):
        root = annotated(LIBRARY.get("S00016"))
        vx0, vy0, vx1, vy1 = view_of(root)
        lanes = sorted(
            tuple(float(lane.get(k)) for k in ("x", "y", "width", "height"))
            for lane in by_class(root, "lane")
        )
        wanted = sorted(
            [
                (0, -0.25, vx1, 0.5),
                (vx0, -0.25, -vx0, 0.5),
                (-0.25, vy0, 0.5, -vy0),
                (-0.25, 0, 0.5, vy1),
            ]
        )
        for got, want in zip(lanes, wanted, strict=True):
            assert got == pytest.approx(want)


def test_the_order_of_the_slots_does_not_change_the_output():
    symbol = full_symbol()
    reversed_slots = replace(symbol, slots=tuple(reversed(symbol.slots)))
    texts = {"tag": "-X1", "marking.in": "1", "marking.out": "2"}
    assert to_svg(reversed_slots, annotate=True, texts=texts) == to_svg(
        symbol, annotate=True, texts=texts
    )


def expected_lane(port, view):
    """The lane by the guide's definition: 0.5 M wide, from the port to the view edge."""
    vx0, vy0, vx1, vy1 = view
    px, py, d = port.position.x, port.position.y, port.direction
    if d is E:
        return (px, py - 0.25, vx1 - px, 0.5)
    if d is W:
        return (vx0, py - 0.25, px - vx0, 0.5)
    if d is N:
        return (px - 0.25, vy0, 0.5, py - vy0)
    return (px - 0.25, py, 0.5, vy1 - py)


class TestOrientedSymbols:
    """The slot boxes do not turn with the symbol; ports, anchors and slot points and sides do."""

    @pytest.mark.parametrize("number", ["S00227", "S00230", "S00254"])
    @pytest.mark.parametrize("orientation", list(Orientation))
    def test_the_annotated_render_follows_the_oriented_ports_and_slots(self, number, orientation):
        base = LIBRARY.get(number)
        symbol = orient(base, orientation)
        root = annotated(symbol, sample_texts(base))
        view = view_of(root)

        lanes = by_class(root, "lane")
        assert len(lanes) == len(symbol.ports)
        for port, lane in zip(symbol.ports, lanes, strict=True):
            got = tuple(float(lane.get(k)) for k in ("x", "y", "width", "height"))
            assert got == pytest.approx(expected_lane(port, view), abs=1e-4)
        markers = by_class(root, "port")
        for port, marker in zip(symbol.ports, markers, strict=True):
            assert (float(marker.get("cx")), float(marker.get("cy"))) == pytest.approx(
                (port.position.x, port.position.y)
            )

        slots = sorted(symbol.slots, key=lambda s: s.id)
        boxes = by_class(root, "slot-box")
        assert len(boxes) == len(slots)
        for slot, rect in zip(slots, boxes, strict=True):
            box = slot_box(slot)
            got = tuple(float(rect.get(k)) for k in ("x", "y", "width", "height"))
            assert got == pytest.approx((box.min.x, box.min.y, box.width, box.height))
            # The box keeps the declared size in every orientation.
            assert (got[2], got[3]) == pytest.approx(slot.box)

        samples = by_class(root, "sample-text")
        assert len(samples) == len(slots)
        anchors = {E: "start", W: "end", N: "middle", S: "middle"}
        for slot, text in zip(slots, samples, strict=True):
            assert text.get("text-anchor") == anchors[slot.side]
            assert float(text.get("x")) == pytest.approx(slot.position.x)
            assert "transform" not in text.attrib
            width = 0.6 * float(text.get("font-size")) * len(text.text)
            box = slot_box(slot)
            x, x0 = float(text.get("x")), {"start": 0, "end": -1, "middle": -0.5}
            left = x + x0[text.get("text-anchor")] * width
            assert box.min.x - 1e-4 <= left
            assert left + width <= box.max.x + 1e-4

        for name, found in annotation_boxes(root):
            assert inside(found, view), (number, orientation, name, found, view)
