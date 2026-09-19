import math
import re
import xml.etree.ElementTree as ET

import pytest

from graphical_symbols import (
    Arc,
    Circle,
    Direction,
    Fill,
    Line,
    Point,
    Polyline,
    Port,
    Reference,
    Status,
    Style,
    Symbol,
    SymbolKind,
    Text,
    Weight,
    to_svg,
)
from graphical_symbols.geometry import arc_point

NS = {"s": "http://www.w3.org/2000/svg"}


def sym(*elements, name="t", ports=()):
    return Symbol(
        name=name,
        kind=SymbolKind.SYMBOL,
        status=Status.UNVERIFIED,
        reference=Reference("X", "1"),
        elements=tuple(elements),
        ports=ports,
    )


def parse(svg):
    return ET.fromstring(svg)  # noqa: S314 - parses this library's own output


def rect_symbol():
    return sym(Polyline((Point(0, 0), Point(4, 0), Point(4, 2), Point(0, 2)), closed=True))


def test_output_parses_as_xml():
    root = parse(to_svg(rect_symbol()))
    assert root.tag == "{http://www.w3.org/2000/svg}svg"


def test_root_size_is_body_box_plus_margin_times_module():
    root = parse(to_svg(rect_symbol()))
    assert root.get("width") == "15mm"
    assert root.get("height") == "10mm"
    assert root.get("viewBox") == "-1 -1 6 4"


def test_module_scales_the_size_but_not_the_view_box():
    root = parse(to_svg(rect_symbol(), module_mm=5))
    assert root.get("width") == "30mm"
    assert root.get("height") == "20mm"
    assert root.get("viewBox") == "-1 -1 6 4"


def test_texts_are_accepted_and_ignored():
    s = rect_symbol()
    assert to_svg(s, texts={"tag": "-K1"}) == to_svg(s)


def test_symbol_without_elements_renders_around_the_origin():
    root = parse(to_svg(sym()))
    assert root.get("viewBox") == "-1 -1 2 2"


def test_output_is_deterministic():
    s = rect_symbol()
    assert to_svg(s, annotate=True) == to_svg(s, annotate=True)


def test_exact_output_for_one_line_symbol():
    expected = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="5mm" viewBox="-1 -1 4 2">\n'
        "<title>wire</title>\n"
        '<g fill="none" stroke="#000" stroke-linecap="butt" stroke-linejoin="miter">\n'
        '<line x1="0" y1="0" x2="2" y2="0" stroke-width="0.1"/>\n'
        "</g>\n"
        "</svg>\n"
    )
    assert to_svg(sym(Line(Point(0, 0), Point(2, 0)), name="wire")) == expected


def test_output_ends_with_single_lf_and_has_no_cr():
    out = to_svg(rect_symbol(), annotate=True)
    assert out.endswith("</svg>\n")
    assert not out.endswith("\n\n")
    assert "\r" not in out


def test_line_weight_and_polyline_forms():
    out = to_svg(
        sym(
            Line(Point(0, 0), Point(1, 0), Weight.THICK),
            Polyline((Point(0, 0), Point(1, 1), Point(2, 0))),
            Polyline((Point(0, 0), Point(1, 1), Point(2, 0)), closed=True, fill=Fill.SOLID),
        )
    )
    assert '<line x1="0" y1="0" x2="1" y2="0" stroke-width="0.2"/>' in out
    assert '<polyline points="0,0 1,1 2,0" stroke-width="0.1"/>' in out
    assert '<polygon points="0,0 1,1 2,0" stroke-width="0.1" fill="#000"/>' in out


def test_dashed_style_is_drawn_as_a_dash_pattern():
    out = to_svg(
        sym(
            Line(Point(0, 0), Point(1, 0), style=Style.DASHED),
            Polyline((Point(0, 0), Point(1, 1)), style=Style.DASHED),
            Arc(Point(0, 0), 1, 0, 90, style=Style.DASHED),
            Line(Point(0, 1), Point(1, 1)),
        )
    )
    assert out.count('stroke-dasharray="0.5 0.25"') == 3
    assert (
        '<line x1="0" y1="0" x2="1" y2="0" stroke-width="0.1" stroke-dasharray="0.5 0.25"/>' in out
    )
    assert '<line x1="0" y1="1" x2="1" y2="1" stroke-width="0.1"/>' in out


def test_circle_forms():
    out = to_svg(sym(Circle(Point(1, 1), 0.5), Circle(Point(3, 1), 0.25, Fill.SOLID, Weight.THICK)))
    assert '<circle cx="1" cy="1" r="0.5" stroke-width="0.1"/>' in out
    assert '<circle cx="3" cy="1" r="0.25" stroke-width="0.2" fill="#000"/>' in out


def test_elements_keep_symbol_order():
    out = to_svg(
        sym(Circle(Point(1, 1), 1), Line(Point(0, 0), Point(1, 0)), Text("a", Point(0, 0)))
    )
    assert out.index("<circle") < out.index("<line") < out.index("<text")


def test_arc_path_and_large_arc_flag():
    quarter = to_svg(sym(Arc(Point(0, 0), 1, 0, 90)))
    assert '<path d="M 1 0 A 1 1 0 0 1 0 1" stroke-width="0.1"/>' in quarter
    three_quarter = to_svg(sym(Arc(Point(0, 0), 1, 0, 270)))
    assert '<path d="M 1 0 A 1 1 0 1 1 0 -1" stroke-width="0.1"/>' in three_quarter


def test_arc_sweep_wraps_past_360():
    wrapped = to_svg(sym(Arc(Point(0, 0), 1, 270, 90)))
    assert "A 1 1 0 0 1" in wrapped


def test_text_attributes_and_escaping():
    out = to_svg(sym(Text("a<&>b", Point(1, 2), 0.5)))
    assert (
        '<text x="1" y="2" font-size="0.5" text-anchor="middle" fill="#000" stroke="none" '
        'font-family="sans-serif">a&lt;&amp;&gt;b</text>'
    ) in out
    text = parse(out).find(".//s:text", NS)
    assert text is not None
    assert text.text == "a<&>b"


def test_title_is_escaped():
    out = to_svg(sym(Line(Point(0, 0), Point(1, 0)), name='R<1> & "x"'))
    assert '<title>R&lt;1&gt; &amp; "x"</title>' in out
    title = parse(out).find("s:title", NS)
    assert title is not None
    assert title.text == 'R<1> & "x"'


_ODD_TEXT = [
    ("a\rb", "a\rb"),
    ("a\r\nb", "a\r\nb"),
    ("\r", "\r"),
    ("a\nb\tc", "a\nb\tc"),
    ("a\x00b", "a\U0000fffdb"),
    ("a\x08\x0b\x0c\x0e\x1fb", "a\U0000fffd\U0000fffd\U0000fffd\U0000fffd\U0000fffdb"),
    ("a\ud800b\udfffc", "a\U0000fffdb\U0000fffdc"),
    ("a\U0000fffe\U0000ffffb", "a\U0000fffd\U0000fffdb"),
    ("&<>\"'", "&<>\"'"),
    ("\U000000e9\U00002713\U0001f600", "\U000000e9\U00002713\U0001f600"),
    ("", None),
]


@pytest.mark.parametrize(("content", "parsed"), _ODD_TEXT)
def test_title_and_text_are_well_formed_xml_without_a_carriage_return(content, parsed):
    out = to_svg(sym(Text(content, Point(0, 0)), name=content))
    assert "\r" not in out
    assert out.encode("utf-8")
    root = parse(out)
    assert root.find("s:title", NS).text == parsed
    assert root.find(".//s:text", NS).text == parsed


def test_a_carriage_return_is_a_numeric_character_reference():
    assert "<title>a&#13;b</title>" in to_svg(sym(name="a\rb"))


@pytest.mark.parametrize(
    "value", [math.nan, math.inf, -math.inf, 1e300, -1e300, 1e-300, -0.0, 0.00001]
)
def test_any_float_is_written_as_a_plain_number(value):
    out = to_svg(sym(Line(Point(value, 0), Point(1, 1))))
    found = re.search(r'x1="([^"]*)"', out)
    assert found
    x1 = found.group(1)
    assert re.fullmatch(r"-?\d+(\.\d{1,4})?", x1)
    assert "-0." not in x1
    assert x1 != "-0"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_a_non_finite_number_is_written_as_zero(value):
    out = to_svg(sym(Line(Point(value, value), Point(1, 1))))
    assert '<line x1="0" y1="0" x2="1" y2="1" stroke-width="0.1"/>' in out


def test_negative_zero_never_rendered():
    tricky = Arc(Point(0, 0), 1, 180 + 1e-11, 270)
    # Guard: this arc really does hit arc_point's trig path and yield -0.0.
    assert str(arc_point(tricky, tricky.start_deg).y) == "-0.0"
    out = to_svg(
        sym(
            Line(Point(-0.0, 0), Point(2, -0.0)),
            Line(Point(-0.00001, 0), Point(1, 0)),
            tricky,
            Text("z", Point(-0.0, -0.0)),
        ),
        annotate=True,
    )
    assert "-0.0" not in out
    assert re.search(r"-0(?![.\d])", out) is None


def test_numbers_have_at_most_four_decimals():
    out = to_svg(sym(Line(Point(0.123456, 0), Point(1 / 3, 2.5))))
    assert 'x1="0.1235" y1="0" x2="0.3333" y2="2.5"' in out


def test_plain_output_has_no_annotation():
    out = to_svg(sym(Line(Point(0, 0), Point(2, 0)), ports=(Port("1", Point(0, 0), Direction.W),)))
    assert 'class="grid"' not in out
    assert "annotation" not in out
    assert "port" not in out


def annotated_root(symbol):
    return parse(to_svg(symbol, annotate=True))


def by_class(root, name):
    return [e for e in root.iter() if e.get("class") == name]


def test_annotation_has_one_port_circle_per_port_and_its_id():
    ports = (
        Port("A<1>", Point(0, 0), Direction.W),
        Port("B", Point(2, 0), Direction.E),
        Port("C", Point(1, 0), Direction.N),
    )
    root = annotated_root(sym(Line(Point(0, 0), Point(2, 0)), ports=ports))
    circles = by_class(root, "port")
    assert [(c.get("cx"), c.get("cy")) for c in circles] == [("0", "0"), ("2", "0"), ("1", "0")]
    assert all(c.get("r") == "0.2" and c.get("fill") == "#d00" for c in circles)
    labels = by_class(root, "port-id")
    assert [t.text for t in labels] == ["A<1>", "B", "C"]
    assert all(t.get("font-size") == "0.6" for t in labels)


def test_port_id_placed_one_module_out_along_direction():
    ports = (Port("W", Point(0, 0), Direction.W), Port("S", Point(2, 0), Direction.S))
    root = annotated_root(sym(Line(Point(0, 0), Point(2, 0)), ports=ports))
    positions = [(t.get("x"), t.get("y")) for t in by_class(root, "port-id")]
    assert positions == [("-1", "0"), ("2", "1")]


def test_annotation_grid_covers_every_integer_point_in_viewbox():
    root = annotated_root(sym(Line(Point(0, 0), Point(2, 0))))
    grid = {(g.get("cx"), g.get("cy")) for g in by_class(root, "grid")}
    # viewBox is -1 -1 4 2: x in -1..3, y in -1..1.
    assert grid == {(str(x), str(y)) for x in range(-1, 4) for y in range(-1, 2)}
    assert all(g.get("r") == "0.06" for g in by_class(root, "grid"))


def test_annotation_grid_skips_points_outside_viewbox():
    root = annotated_root(sym(Line(Point(0.5, 0.5), Point(1.5, 0.5))))
    # viewBox is -0.5 -0.5 3 2: x in 0..2, y in 0..1.
    grid = {(g.get("cx"), g.get("cy")) for g in by_class(root, "grid")}
    assert grid == {(str(x), str(y)) for x in range(3) for y in range(2)}


def test_annotation_body_box_rect():
    root = annotated_root(rect_symbol())
    (rect,) = by_class(root, "body-box")
    assert (rect.get("x"), rect.get("y"), rect.get("width"), rect.get("height")) == (
        "0",
        "0",
        "4",
        "2",
    )
    assert rect.get("stroke-dasharray") == "0.2 0.2"
    assert rect.get("stroke") == "#0a0"


def test_annotation_group_follows_main_group():
    root = annotated_root(rect_symbol())
    groups = root.findall("s:g", NS)
    assert [g.get("class") for g in groups] == [None, "annotation"]


def path_d(svg):
    (path,) = parse(svg).findall(".//s:path", NS)
    return path.get("d")


def path_commands(d):
    """Split path data into (letter, numbers) commands."""
    return [
        (m.group(1), [float(v) for v in m.group(2).split()])
        for m in re.finditer(r"([MA])([^MA]*)", d)
    ]


def test_full_circle_arc_becomes_two_half_arcs():
    d = path_d(to_svg(sym(Arc(Point(1, 1), 2, 90, 90))))
    assert d == "M 1 3 A 2 2 0 0 1 1 -1 A 2 2 0 0 1 1 3"


def test_zero_to_360_arc_becomes_two_half_arcs():
    d = path_d(to_svg(sym(Arc(Point(0, 0), 1, 0, 360))))
    assert d == "M 1 0 A 1 1 0 0 1 -1 0 A 1 1 0 0 1 1 0"


def test_full_circle_arc_is_a_visible_closed_path():
    for arc in (Arc(Point(0, 0), 1, 45, 45), Arc(Point(2, 1), 1.5, 0, 360)):
        commands = path_commands(path_d(to_svg(sym(arc))))
        assert [c for c, _ in commands] == ["M", "A", "A"]
        (_, (sx, sy)), (_, (*_, mx, my)), (_, (*_, ex, ey)) = commands
        assert (ex, ey) == (sx, sy)
        # The midpoint is diametrically opposite, so the path is a drawn circle, not a dot.
        assert math.dist((sx, sy), (mx, my)) == pytest.approx(2 * arc.radius, abs=1e-3)
        assert all(args[3:5] == [0, 1] for _, args in commands[1:])


def test_partial_arc_is_not_split():
    assert path_d(to_svg(sym(Arc(Point(0, 0), 1, 0, 180)))).count("A") == 1


def test_full_circle_arc_is_drawn_and_boxed_as_a_full_circle():
    s = sym(Arc(Point(0, 0), 1, 30, 30))
    assert path_d(to_svg(s)).count("A") == 2
    assert parse(to_svg(s)).get("viewBox") == "-2 -2 4 4"


def port_symbol():
    ports = (
        Port("PE", Point(0, 1), Direction.W),
        Port("A1", Point(4, 1), Direction.E),
        Port("PE", Point(2, 0), Direction.N),
        Port("A1", Point(2, 2), Direction.S),
    )
    return sym(
        Polyline((Point(0, 0), Point(4, 0), Point(4, 2), Point(0, 2)), closed=True), ports=ports
    )


def test_annotated_viewbox_contains_every_port_label_box():
    root = annotated_root(port_symbol())
    vx, vy, vw, vh = (float(v) for v in root.get("viewBox").split())
    labels = by_class(root, "port-id")
    assert len(labels) == len(port_symbol().ports)
    for label in labels:
        x, y, half_w = float(label.get("x")), float(label.get("y")), 0.3 * len(label.text)
        assert vx <= x - half_w
        assert x + half_w <= vx + vw
        assert vy <= y - 0.3
        assert y + 0.3 <= vy + vh


def test_annotated_size_follows_extent_including_labels():
    root = annotated_root(port_symbol())
    # Labels reach x -1.6..5.6 and y -1.3..3.3; margin 1 goes on every side of that.
    assert root.get("viewBox") == "-2.6 -2.3 9.2 6.6"
    assert root.get("width") == "23mm"
    assert root.get("height") == "16.5mm"
    (rect,) = by_class(root, "body-box")
    assert (rect.get("x"), rect.get("y"), rect.get("width"), rect.get("height")) == (
        "0",
        "0",
        "4",
        "2",
    )


def test_plain_render_ignores_port_labels():
    plain = to_svg(port_symbol())
    root = parse(plain)
    assert root.get("viewBox") == "-1 -1 6 4"
    assert root.get("width") == "15mm"
    assert plain == to_svg(sym(*port_symbol().elements))
