"""The resolver: flattening composites, placement, inheritance and the composition rules."""

import tomllib
from pathlib import Path as FilePath

import pytest

from graphical_symbols.geometry import Direction, Line, Orientation, Point, Style, Weight
from graphical_symbols.load import symbol_from_data
from graphical_symbols.model import (
    LibraryConfig,
    Node,
    Path,
    PathKind,
    Port,
    Potential,
    Severity,
    Slot,
)
from graphical_symbols.orient import inverse, orient_direction, orient_point
from graphical_symbols.resolve import Resolution, resolve_library

GUIDE = FilePath(__file__).resolve().parent / "fixtures" / "guide"
CONFIG = LibraryConfig("IEC 60617", "IEC 60617 symbols", r"^S\d{5}$")
N, E, S, W = Direction.N, Direction.E, Direction.S, Direction.W

HEAD = """schema = 1
name = "{name}"
kind = "{kind}"
status = "unverified"
reference = {{ standard = "IEC 60617", number = "{number}" }}
"""

# An element with a line and a `link` anchor facing east.
LINK_E = (
    HEAD.format(name="Link east", kind="element", number="S00010")
    + """anchors = [{ id = "link", at = [0, 0], dir = "E" }]
elements = [{ line = [[0, 0], [-1, 0]] }]
"""
)
# The same facing west.
LINK_W = (
    HEAD.format(name="Link west", kind="element", number="S00011")
    + """anchors = [{ id = "link", at = [1, 0], dir = "W" }]
elements = [{ line = [[0, 0], [1, 0]] }]
"""
)
# A two-port element with a through path.
TWO_PORT = (
    HEAD.format(name="Two port", kind="element", number="S00012")
    + """ports = [
  { id = "in", at = [0, -2], dir = "N" },
  { id = "out", at = [0, 2], dir = "S" },
]
paths = [{ from = "in", to = "out", kind = "switch_open", through = true }]
elements = [{ line = [[0, -2], [0, 2]] }]
"""
)
# The same without the through flag.
TWO_PORT_PLAIN = TWO_PORT.replace("through = true", "through = false").replace("S00012", "S00013")


def composite(number: str, body: str, kind: str = "element") -> str:
    return HEAD.format(name=f"Composite {number}", kind=kind, number=number) + body


def files(*texts: str) -> dict[str, dict]:
    """Decode TOML texts, keyed by the number in their reference (the file stem)."""
    decoded = [tomllib.loads(text) for text in texts]
    return {d["reference"]["number"]: d for d in decoded}


def guide_sources() -> dict[str, dict]:
    return {
        f.stem: tomllib.loads(f.read_text(encoding="utf-8"))
        for f in sorted((GUIDE / "symbols").glob("*.toml"))
    }


def resolve(*texts: str) -> Resolution:
    return resolve_library(CONFIG, files(*texts))


def located(resolution: Resolution, stem: str) -> list[tuple[str, str | None]]:
    return [(f.rule, f.location) for f in resolution.findings.get(stem, ())]


class TestGuideFixtures:
    @pytest.fixture
    def resolution(self) -> Resolution:
        return resolve_library(CONFIG, guide_sources())

    def test_all_six_files_resolve_without_findings(self, resolution):
        assert resolution.findings == {}
        assert list(resolution.symbols) == [
            "S00016",
            "S00171",
            "S00227",
            "S00230",
            "S00254",
            "S00305",
        ]

    def test_atomic_files_are_their_symbols(self, resolution):
        for stem, data in guide_sources().items():
            if "parts" not in data:
                assert resolution.symbols[stem] == symbol_from_data(data)

    def test_push_button_identity(self, resolution):
        push = resolution.symbols["S00254"]
        assert push.name == "Switch, manually operated, push-button, automatic return"
        assert (push.kind.value, push.status.value) == ("symbol", "unverified")
        assert (push.reference.standard, push.reference.number) == ("IEC 60617", "S00254")
        assert push.pole_pitch is None
        assert push.lint_allow == ()

    def test_push_button_ports_come_only_from_the_rename_map(self, resolution):
        assert resolution.symbols["S00254"].ports == (
            Port("in", Point(0, -2), N),
            Port("out", Point(0, 2), S),
        )

    def test_push_button_elements(self, resolution):
        assert resolution.symbols["S00254"].elements == (
            Line(Point(0, -2), Point(0, -1)),
            Line(Point(0, 2), Point(0, 1)),
            Line(Point(0, 1), Point(-1, -1)),
            Line(Point(-0.5, 0), Point(-2.5, 0), Weight.NORMAL, Style.DASHED),
            Line(Point(-2.5, -0.5), Point(-2.5, 0.5)),
            Line(Point(-2.5, 0), Point(-3.25, 0)),
        )

    def test_push_button_slots_follow_the_declaration_order(self, resolution):
        assert resolution.symbols["S00254"].slots == (
            Slot("tag", Point(-3.5, 0), W, (6, 1)),
            Slot("marking.in", Point(0.25, -1.5), E, (1.5, 1)),
            Slot("marking.out", Point(0.25, 1.5), E, (1.5, 1)),
        )

    def test_push_button_inherits_nodes_and_the_through_path(self, resolution):
        push = resolution.symbols["S00254"]
        assert push.nodes == (Node(("in",)), Node(("out",)))
        assert push.paths == (Path("in", "out", PathKind.SWITCH_OPEN, through=True),)

    def test_anchors_are_not_inherited(self, resolution):
        assert resolution.symbols["S00254"].anchors == ()


class TestPlacementArithmetic:
    """The part is translated by `T + length * dT - A`, and dA must equal -dT."""

    @staticmethod
    def attach(orientation: Orientation, length: float, *, via: bool = False) -> Resolution:
        # The part's own anchor direction is chosen so that it faces west after `orient`.
        own = orient_direction(W, inverse(orientation)).name
        part = (
            HEAD.format(name="P", kind="element", number="S00020")
            + f'anchors = [{{ id = "k", at = [0.25, -0.5], dir = "{own}" }}]\n'
            + "elements = [{ line = [[0.25, -0.5], [1, 1]] }]\n"
        )
        target = (
            HEAD.format(name="T", kind="element", number="S00021")
            + 'anchors = [{ id = "t", at = [2, 3], dir = "E" }]\n'
            + "elements = [{ line = [[2, 3], [1, 3]] }]\n"
        )
        link = ', via = "mechanical_link"' if via else ""
        top = composite(
            "S00022",
            'parts = [{ as = "a", use = "S00021" }, '
            f'{{ as = "b", use = "S00020", orient = "{orientation.value}", attach = "k", '
            f'to = "a.t", length = {length}{link} }}]\n',
        )
        return resolve(part, target, top)

    @pytest.mark.parametrize("orientation", list(Orientation))
    @pytest.mark.parametrize("length", [0, 1, 2.5])
    def test_the_attaching_anchor_lands_length_from_the_target(self, orientation, length):
        resolution = self.attach(orientation, length)
        assert resolution.findings == {}
        placed = resolution.symbols["S00022"].elements[-1]
        # T = (2, 3), dT = east, so the anchor must land at (2 + length, 3); the part's line
        # starts at its anchor and its end moves by the same translation.
        anchor = orient_point(Point(0.25, -0.5), orientation)
        end = orient_point(Point(1, 1), orientation)
        shift = (2 + length - anchor.x, 3 - anchor.y)
        assert placed == Line(Point(2 + length, 3), Point(end.x + shift[0], end.y + shift[1]))

    def test_via_adds_the_dashed_line_from_the_target_along_its_direction(self):
        elements = self.attach(Orientation.R0, 2, via=True).symbols["S00022"].elements
        assert elements == (
            Line(Point(2, 3), Point(1, 3)),
            Line(Point(2, 3), Point(4, 3), Weight.NORMAL, Style.DASHED),
            Line(Point(4, 3), Point(4.75, 4.5)),
        )

    def test_without_via_there_is_no_dashed_line(self):
        elements = self.attach(Orientation.R0, 2).symbols["S00022"].elements
        assert [(type(e), e.style) for e in elements if isinstance(e, Line)] == [
            (Line, Style.SOLID),
            (Line, Style.SOLID),
        ]

    def test_at_translates_the_part_by_its_origin(self):
        top = composite("S00030", 'parts = [{ as = "a", use = "S00010", at = [1.5, -2] }]\n')
        resolution = resolve(LINK_E, top)
        assert resolution.findings == {}
        assert resolution.symbols["S00030"].elements == (Line(Point(1.5, -2), Point(0.5, -2)),)

    def test_the_first_part_defaults_to_the_origin(self):
        top = composite("S00030", 'parts = [{ as = "a", use = "S00010" }]\n')
        assert resolve(LINK_E, top).symbols["S00030"].elements == (Line(Point(0, 0), Point(-1, 0)),)

    def test_orient_is_applied_before_placing(self):
        top = composite(
            "S00030", 'parts = [{ as = "a", use = "S00010", orient = "R90", at = [1, 1] }]\n'
        )
        # (-1, 0) turned clockwise is (0, -1); moved by (1, 1).
        assert resolve(LINK_E, top).symbols["S00030"].elements == (Line(Point(1, 1), Point(1, 0)),)

    def test_a_negative_length_is_placed_as_written(self):
        top = composite(
            "S00030",
            'parts = [{ as = "a", use = "S00010" }, '
            '{ as = "b", use = "S00011", attach = "link", to = "a.link", length = -1 }]\n',
        )
        resolution = resolve(LINK_E, LINK_W, top)
        assert resolution.findings == {}
        # a.link is at (0, 0) facing east; b's anchor lands at (-1, 0) and its line with it.
        assert resolution.symbols["S00030"].elements[-1] == Line(Point(-2, 0), Point(-1, 0))

    def test_an_anchor_of_a_nested_composite_is_usable_as_a_target(self):
        inner = composite(
            "S00030",
            'parts = [{ as = "a", use = "S00010", at = [5, 0] }]\n'
            'anchors = [{ id = "tip", at = [5, 0], dir = "E" }]\n',
        )
        top = composite(
            "S00031",
            'parts = [{ as = "i", use = "S00030" }, '
            '{ as = "b", use = "S00011", attach = "link", to = "i.tip", length = 1 }]\n',
        )
        resolution = resolve(LINK_E, LINK_W, inner, top)
        assert resolution.findings == {}
        assert resolution.symbols["S00031"].elements[-1] == Line(Point(5, 0), Point(6, 0))


class TestRepeatedPart:
    @pytest.fixture
    def resolution(self) -> Resolution:
        top = composite(
            "S00040",
            'parts = [{ as = "main", use = "S00227", repeat = 3 }]\n'
            'ports = { in1 = "main.1.in", out1 = "main.1.out", in2 = "main.2.in", '
            'out2 = "main.2.out", in3 = "main.3.in", out3 = "main.3.out" }\n'
            "[slots]\n"
            'tag = "main.tag"\n'
            '"marking.in2" = "main.marking.2.in"\n',
        )
        sources = guide_sources() | files(top)
        return resolve_library(CONFIG, sources)

    def test_findings(self, resolution):
        assert resolution.findings == {}

    def test_ports_of_the_poles_are_addressed_as_part_dot_pole_dot_port(self, resolution):
        ports = resolution.symbols["S00040"].ports
        assert [(p.id, p.position) for p in ports] == [
            ("in1", Point(0, -2)),
            ("out1", Point(0, 2)),
            ("in2", Point(4, -2)),
            ("out2", Point(4, 2)),
            ("in3", Point(8, -2)),
            ("out3", Point(8, 2)),
        ]

    def test_only_pole_one_stays_the_through_path(self, resolution):
        assert resolution.symbols["S00040"].paths == (
            Path("in1", "out1", PathKind.SWITCH_OPEN, through=True),
            Path("in2", "out2", PathKind.SWITCH_OPEN, through=False),
            Path("in3", "out3", PathKind.SWITCH_OPEN, through=False),
        )

    def test_nodes_repeat_per_pole(self, resolution):
        assert resolution.symbols["S00040"].nodes == tuple(
            Node((f"{d}{k}",)) for k in (1, 2, 3) for d in ("in", "out")
        )

    def test_the_link_line_of_repeat_is_kept_after_the_poles(self, resolution):
        elements = resolution.symbols["S00040"].elements
        assert len(elements) == 10
        assert elements[-1] == Line(Point(-0.5, 0), Point(7.5, 0), Weight.NORMAL, Style.DASHED)

    def test_slot_references_name_the_renamed_slots_of_the_part(self, resolution):
        assert resolution.symbols["S00040"].slots == (
            Slot("tag", Point(-1.5, 0), W, (6, 1)),
            Slot("marking.in2", Point(4.25, -1.5), E, (1.5, 1)),
        )

    def test_repeat_then_orient_then_place(self):
        top = composite(
            "S00041",
            'parts = [{ as = "m", use = "S00227", repeat = 2, orient = "R90", at = [1, 0] }]\n'
            'ports = { a = "m.1.in", b = "m.1.out", c = "m.2.in", d = "m.2.out" }\n',
        )
        resolution = resolve_library(CONFIG, guide_sources() | files(top))
        assert resolution.findings == {}
        # Pole 2 sits at x = 4; R90 maps (x, y) to (-y, x); then the part moves by (1, 0).
        assert [(p.id, p.position, p.direction) for p in resolution.symbols["S00041"].ports] == [
            ("a", Point(3, 0), E),
            ("b", Point(-1, 0), W),
            ("c", Point(3, 4), E),
            ("d", Point(-1, 4), W),
        ]

    def test_an_integral_float_count_is_accepted(self):
        top = composite(
            "S00041",
            'parts = [{ as = "m", use = "S00227", repeat = 2.0 }]\n'
            'ports = { a = "m.1.in", b = "m.1.out", c = "m.2.in", d = "m.2.out" }\n',
        )
        resolution = resolve_library(CONFIG, guide_sources() | files(top))
        assert resolution.findings == {}
        assert len(resolution.symbols["S00041"].ports) == 4


class TestTwoLevelComposite:
    @pytest.fixture
    def resolution(self) -> Resolution:
        top = composite(
            "S00050",
            'parts = [{ as = "pb", use = "S00254", at = [1, 0] }]\n'
            'ports = { in = "pb.in", out = "pb.out" }\n'
            '[slots]\ntag = "pb.tag"\n"marking.in" = "pb.marking.in"\n',
        )
        return resolve_library(CONFIG, guide_sources() | files(top))

    def test_findings(self, resolution):
        assert resolution.findings == {}

    def test_the_inner_composite_is_flattened_and_moved(self, resolution):
        inner = resolution.symbols["S00254"]
        top = resolution.symbols["S00050"]
        assert top.elements == tuple(
            type(e)(Point(e.start.x + 1, e.start.y), Point(e.end.x + 1, e.end.y), e.weight, e.style)
            for e in inner.elements
        )
        assert top.ports == (Port("in", Point(1, -2), N), Port("out", Point(1, 2), S))

    def test_slots_of_the_inner_composite_are_reachable_and_moved(self, resolution):
        assert resolution.symbols["S00050"].slots == (
            Slot("tag", Point(-2.5, 0), W, (6, 1)),
            Slot("marking.in", Point(1.25, -1.5), E, (1.5, 1)),
        )

    def test_nodes_and_paths_are_inherited_through_both_levels(self, resolution):
        top = resolution.symbols["S00050"]
        assert top.nodes == (Node(("in",)), Node(("out",)))
        assert top.paths == (Path("in", "out", PathKind.SWITCH_OPEN, through=True),)


class TestInheritance:
    def test_a_slot_reference_is_moved_with_its_part_placement(self):
        top = composite(
            "S00060",
            'parts = [{ as = "c", use = "S00227", orient = "R90", at = [2, 1] }]\n'
            'ports = { in = "c.in", out = "c.out" }\n'
            '[slots]\n"marking.in" = "c.marking.in"\n',
        )
        resolution = resolve_library(CONFIG, guide_sources() | files(top))
        assert resolution.findings == {}
        # (0.25, -1.5) turns to (1.5, 0.25) and moves to (3.5, 1.25); side E turns to S; the box
        # stays upright.
        assert resolution.symbols["S00060"].slots == (
            Slot("marking.in", Point(3.5, 1.25), S, (1.5, 1)),
        )

    def test_a_new_slot_table_is_kept_as_declared_and_slots_are_never_inherited(self):
        top = composite(
            "S00060",
            'parts = [{ as = "c", use = "S00227" }]\n'
            'ports = { in = "c.in", out = "c.out" }\n'
            '[slots]\ntag = { at = [-3, 0], side = "W", box = [6, 1] }\n',
        )
        resolution = resolve_library(CONFIG, guide_sources() | files(top))
        assert resolution.symbols["S00060"].slots == (Slot("tag", Point(-3, 0), W, (6, 1)),)

    def test_own_elements_come_after_the_parts_elements(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00010" }]\nelements = [{ line = [[0, 0], [0, 3]] }]\n',
        )
        assert resolve(LINK_E, top).symbols["S00060"].elements == (
            Line(Point(0, 0), Point(-1, 0)),
            Line(Point(0, 0), Point(0, 3)),
        )

    def test_anchors_pitch_and_exemptions_are_the_composites_own(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00010" }]\n'
            'anchors = [{ id = "tip", at = [-1, 0], dir = "W" }]\n'
            "pole_pitch = 8\n"
            'lint_allow = [{ rule = "degenerate", reason = "kept" }]\n',
        )
        symbol = resolve(LINK_E, top).symbols["S00060"]
        assert [(a.id, a.position, a.direction) for a in symbol.anchors] == [
            ("tip", Point(-1, 0), W)
        ]
        assert symbol.pole_pitch == 8
        assert [(a.rule, a.reason) for a in symbol.lint_allow] == [("degenerate", "kept")]

    def test_a_declared_path_replaces_the_inherited_path_between_the_same_nodes(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00012" }]\n'
            'ports = { p = "a.in", q = "a.out" }\n'
            'paths = [{ from = "q", to = "p", kind = "conductor", through = true }]\n',
        )
        resolution = resolve(TWO_PORT, top)
        assert resolution.findings == {}
        assert resolution.symbols["S00060"].paths == (
            Path("q", "p", PathKind.CONDUCTOR, through=True),
        )

    def test_a_declared_path_between_other_nodes_is_added(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00012" }, { as = "b", use = "S00012", at = [4, 0] }]\n'
            'ports = { ai = "a.in", ao = "a.out", bi = "b.in", bo = "b.out" }\n'
            'paths = [{ from = "ao", to = "bi", kind = "conductor" }]\n',
        )
        assert resolve(TWO_PORT, top).symbols["S00060"].paths == (
            Path("ai", "ao", PathKind.SWITCH_OPEN, through=False),
            Path("bi", "bo", PathKind.SWITCH_OPEN, through=False),
            Path("ao", "bi", PathKind.CONDUCTOR, through=False),
        )

    def test_a_single_inherited_through_path_stays_through(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00012" }, { as = "b", use = "S00013", at = [4, 0] }]\n'
            'ports = { ai = "a.in", ao = "a.out", bi = "b.in", bo = "b.out" }\n',
        )
        assert [
            p.through for p in resolve(TWO_PORT, TWO_PORT_PLAIN, top).symbols["S00060"].paths
        ] == [
            True,
            False,
        ]

    def test_more_than_one_inherited_through_clears_the_flag_on_all_of_them(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00012" }, { as = "b", use = "S00012", at = [4, 0] }]\n'
            'ports = { ai = "a.in", ao = "a.out", bi = "b.in", bo = "b.out" }\n',
        )
        resolution = resolve(TWO_PORT, top)
        assert resolution.findings == {}
        assert [p.through for p in resolution.symbols["S00060"].paths] == [False, False]

    def test_redeclaring_the_path_that_stays_keeps_only_that_flag(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00012" }, { as = "b", use = "S00012", at = [4, 0] }]\n'
            'ports = { ai = "a.in", ao = "a.out", bi = "b.in", bo = "b.out" }\n'
            'paths = [{ from = "ai", to = "ao", kind = "switch_open", through = true }]\n',
        )
        assert resolve(TWO_PORT, top).symbols["S00060"].paths == (
            Path("bi", "bo", PathKind.SWITCH_OPEN, through=False),
            Path("ai", "ao", PathKind.SWITCH_OPEN, through=True),
        )

    def test_a_declared_node_may_restate_an_inherited_one_to_add_a_potential(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00012" }]\n'
            'ports = { p = "a.in", q = "a.out" }\n'
            'nodes = [{ ports = ["p"], potential = "earth" }]\n',
        )
        resolution = resolve(TWO_PORT, top)
        assert resolution.findings == {}
        assert resolution.symbols["S00060"].nodes == (
            Node(("p",), Potential.EARTH),
            Node(("q",)),
        )

    def test_an_inherited_potential_survives_a_restatement_without_one(self):
        earth = (
            HEAD.format(name="Earth", kind="element", number="S00014")
            + 'ports = [{ id = "e", at = [0, 0], dir = "N" }]\n'
            + 'nodes = [{ ports = ["e"], potential = "protective_earth" }]\n'
            + "elements = [{ line = [[0, 0], [0, 1]] }]\n"
        )
        top = composite(
            "S00060",
            'parts = [{ as = "g", use = "S00014" }]\n'
            'ports = { pe = "g.e" }\n'
            'nodes = [{ ports = ["pe"] }]\n',
        )
        assert resolve(earth, top).symbols["S00060"].nodes == (
            Node(("pe",), Potential.PROTECTIVE_EARTH),
        )

    def test_any_other_declared_node_is_kept_for_the_linter_to_report(self):
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00012" }]\n'
            'ports = { p = "a.in", q = "a.out" }\n'
            'nodes = [{ ports = ["p", "q"] }]\n',
        )
        assert resolve(TWO_PORT, top).symbols["S00060"].nodes == (
            Node(("p",)),
            Node(("q",)),
            Node(("p", "q")),
        )

    def test_port_descriptions_are_carried_and_an_exported_port_may_be_renamed_twice(self):
        described = TWO_PORT.replace(
            '{ id = "in", at = [0, -2], dir = "N" }',
            '{ id = "in", at = [0, -2], dir = "N", description = "top" }',
        )
        top = composite(
            "S00060",
            'parts = [{ as = "a", use = "S00012" }]\n'
            'ports = { p = "a.in", q = "a.out", r = "a.in" }\n',
        )
        symbol = resolve(described, top).symbols["S00060"]
        assert symbol.ports == (
            Port("p", Point(0, -2), N, "top"),
            Port("q", Point(0, 2), S),
            Port("r", Point(0, -2), N, "top"),
        )
        assert symbol.nodes == (Node(("p", "r")), Node(("q",)))
        assert symbol.paths == (Path("p", "q", PathKind.SWITCH_OPEN, through=True),)


class TestPartUnknown:
    def test_fires_on_a_missing_file_at_the_use_key(self):
        top = composite("S00070", 'parts = [{ as = "a", use = "S99999" }]\n')
        resolution = resolve(top)
        assert located(resolution, "S00070") == [("part-unknown", "/parts/0/use")]
        assert "S99999" in resolution.findings["S00070"][0].message
        assert "S00070" not in resolution.symbols

    def test_every_unknown_part_is_reported(self):
        top = composite(
            "S00070", 'parts = [{ as = "a", use = "S99998" }, { as = "b", use = "S99999" }]\n'
        )
        assert located(resolve(top), "S00070") == [
            ("part-unknown", "/parts/0/use"),
            ("part-unknown", "/parts/1/use"),
        ]

    def test_does_not_fire_when_the_file_exists(self):
        top = composite("S00070", 'parts = [{ as = "a", use = "S00010" }]\n')
        resolution = resolve(LINK_E, top)
        assert resolution.findings == {}
        assert "S00070" in resolution.symbols


class TestPartCycle:
    def test_a_two_file_cycle_is_reported_on_both_files_at_the_part_that_leads_on(self):
        a = composite("S00071", 'parts = [{ as = "x", use = "S00072" }]\n')
        b = composite("S00072", 'parts = [{ as = "y", use = "S00071" }]\n')
        resolution = resolve(a, b)
        assert located(resolution, "S00071") == [("part-cycle", "/parts/0/use")]
        assert located(resolution, "S00072") == [("part-cycle", "/parts/0/use")]
        assert resolution.symbols == {}
        assert "S00071 -> S00072 -> S00071" in resolution.findings["S00071"][0].message

    def test_a_self_cycle(self):
        a = composite(
            "S00071", 'parts = [{ as = "x", use = "S00010" }, { as = "y", use = "S00071" }]\n'
        )
        resolution = resolve(LINK_E, a)
        assert located(resolution, "S00071") == [("part-cycle", "/parts/1/use")]
        assert "S00071 -> S00071" in resolution.findings["S00071"][0].message

    def test_a_file_entering_a_cycle_reports_nothing_of_its_own(self):
        a = composite("S00071", 'parts = [{ as = "x", use = "S00072" }]\n')
        b = composite("S00072", 'parts = [{ as = "y", use = "S00071" }]\n')
        c = composite("S00073", 'parts = [{ as = "z", use = "S00071" }]\n')
        resolution = resolve(a, b, c)
        assert sorted(resolution.findings) == ["S00071", "S00072"]
        assert "S00073" not in resolution.symbols

    def test_the_same_findings_whichever_file_is_reached_first(self):
        a = composite("S00071", 'parts = [{ as = "x", use = "S00072" }]\n')
        b = composite("S00072", 'parts = [{ as = "y", use = "S00073" }]\n')
        c = composite("S00073", 'parts = [{ as = "z", use = "S00071" }]\n')
        first = resolve(a, b, c)
        assert {s: located(first, s) for s in first.findings} == {
            "S00071": [("part-cycle", "/parts/0/use")],
            "S00072": [("part-cycle", "/parts/0/use")],
            "S00073": [("part-cycle", "/parts/0/use")],
        }
        assert first == resolve(c, b, a)

    def test_a_diamond_is_not_a_cycle(self):
        top = composite(
            "S00074",
            'parts = [{ as = "l", use = "S00075" }, { as = "r", use = "S00076", at = [3, 0] }]\n',
        )
        left = composite("S00075", 'parts = [{ as = "x", use = "S00010" }]\n')
        right = composite("S00076", 'parts = [{ as = "x", use = "S00010" }]\n')
        resolution = resolve(LINK_E, left, right, top)
        assert resolution.findings == {}
        assert len(resolution.symbols) == 4


class TestPartAnchor:
    @staticmethod
    def second(part: str, first: str = 'use = "S00010"') -> Resolution:
        top = composite("S00080", f'parts = [{{ as = "a", {first} }}, {{ as = "b", {part} }}]\n')
        return resolve(LINK_E, LINK_W, top)

    def test_a_good_pair_does_not_fire(self):
        resolution = self.second('use = "S00011", attach = "link", to = "a.link", length = 2')
        assert resolution.findings == {}
        assert "S00080" in resolution.symbols

    def test_unknown_attaching_anchor(self):
        resolution = self.second('use = "S00011", attach = "nope", to = "a.link"')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1/attach")]
        assert "S00080" not in resolution.symbols

    def test_unknown_target_anchor(self):
        resolution = self.second('use = "S00011", attach = "link", to = "a.nope"')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1/to")]

    def test_target_that_is_not_part_dot_anchor(self):
        resolution = self.second('use = "S00011", attach = "link", to = "link"')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1/to")]

    def test_target_naming_an_unknown_part(self):
        resolution = self.second('use = "S00011", attach = "link", to = "zz.link"')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1/to")]

    def test_target_naming_a_later_part(self):
        top = composite(
            "S00080",
            'parts = [{ as = "a", use = "S00011", attach = "link", to = "b.link" },'
            ' { as = "b", use = "S00010", at = [0, 0] }]\n',
        )
        assert located(resolve(LINK_E, LINK_W, top), "S00080") == [("part-anchor", "/parts/0/to")]

    def test_target_naming_the_part_itself(self):
        top = composite(
            "S00080",
            'parts = [{ as = "a", use = "S00010" },'
            ' { as = "b", use = "S00011", attach = "link", to = "b.link" }]\n',
        )
        assert located(resolve(LINK_E, LINK_W, top), "S00080") == [("part-anchor", "/parts/1/to")]

    def test_anchors_that_do_not_face_each_other(self):
        resolution = self.second('use = "S00010", attach = "link", to = "a.link"')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1")]
        assert "face" in resolution.findings["S00080"][0].message

    def test_anchors_that_face_after_orient_do_not_fire(self):
        resolution = self.second('use = "S00010", orient = "R180", attach = "link", to = "a.link"')
        assert resolution.findings == {}

    def test_via_needs_a_positive_length(self):
        for length in ("", ", length = 0", ", length = -1"):
            resolution = self.second(
                f'use = "S00011", attach = "link", to = "a.link", via = "mechanical_link"{length}'
            )
            assert located(resolution, "S00080") == [("part-anchor", "/parts/1/via")]

    def test_via_with_a_positive_length_does_not_fire(self):
        resolution = self.second(
            'use = "S00011", attach = "link", to = "a.link", length = 0.5, via = "mechanical_link"'
        )
        assert resolution.findings == {}

    def test_a_later_part_needs_attach_or_at(self):
        assert located(self.second('use = "S00011"'), "S00080") == [("part-anchor", "/parts/1")]

    def test_a_later_part_may_not_have_both(self):
        resolution = self.second('use = "S00011", attach = "link", to = "a.link", at = [1, 1]')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1")]

    def test_a_later_part_with_at_alone_does_not_fire(self):
        assert self.second('use = "S00011", at = [1, 1]').findings == {}

    @pytest.mark.parametrize("extra", ['to = "a.link"', "length = 1", 'via = "mechanical_link"'])
    def test_to_length_and_via_need_attach(self, extra):
        resolution = self.second(f'use = "S00011", at = [1, 1], {extra}')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1")]

    @pytest.mark.parametrize("extra", ['to = "a.link"', "length = 1", 'via = "mechanical_link"'])
    def test_to_length_and_via_without_attach_or_at_are_reported(self, extra):
        resolution = self.second(f'use = "S00011", {extra}')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1")]
        assert "need attach" in resolution.findings["S00080"][0].message

    def test_the_first_part_with_a_stray_length_is_reported(self):
        top = composite("S00080", 'parts = [{ as = "a", use = "S00010", length = 2 }]\n')
        assert located(resolve(LINK_E, top), "S00080") == [("part-anchor", "/parts/0")]

    def test_attach_needs_to(self):
        resolution = self.second('use = "S00011", attach = "link"')
        assert located(resolution, "S00080") == [("part-anchor", "/parts/1/attach")]

    def test_the_first_part_cannot_attach(self):
        top = composite(
            "S00080", 'parts = [{ as = "a", use = "S00011", attach = "link", to = "a.link" }]\n'
        )
        assert located(resolve(LINK_W, top), "S00080") == [("part-anchor", "/parts/0/to")]

    def test_every_problem_of_every_part_is_reported(self):
        top = composite(
            "S00080",
            'parts = [{ as = "a", use = "S00010" },'
            ' { as = "b", use = "S00011" },'
            ' { as = "c", use = "S00011", attach = "nope", to = "a.link" }]\n',
        )
        assert located(resolve(LINK_E, LINK_W, top), "S00080") == [
            ("part-anchor", "/parts/1"),
            ("part-anchor", "/parts/2/attach"),
        ]

    def test_a_part_that_failed_earlier_causes_no_further_finding_for_its_users(self):
        top = composite(
            "S00080",
            'parts = [{ as = "a", use = "S00227", repeat = 0 },'
            ' { as = "b", use = "S00011", attach = "link", to = "a.link" }]\n',
        )
        resolution = resolve_library(CONFIG, guide_sources() | files(LINK_W, top))
        assert located(resolution, "S00080") == [("schema", "/parts/0/repeat")]


class TestPartPortUnexported:
    def test_fires_for_every_port_missing_from_the_rename_map(self):
        top = composite(
            "S00081", 'parts = [{ as = "a", use = "S00012" }]\nports = { p = "a.in" }\n'
        )
        resolution = resolve(TWO_PORT, top)
        assert located(resolution, "S00081") == [("part-port-unexported", "/ports")]
        assert "a.out" in resolution.findings["S00081"][0].message
        assert "S00081" not in resolution.symbols

    def test_there_is_no_implicit_export(self):
        top = composite("S00081", 'parts = [{ as = "a", use = "S00012" }]\n')
        assert [f.message for f in resolve(TWO_PORT, top).findings["S00081"]] == [
            "the port 'a.in' of a part is not exported",
            "the port 'a.out' of a part is not exported",
        ]

    def test_does_not_fire_when_every_port_is_exported(self):
        top = composite(
            "S00081",
            'parts = [{ as = "a", use = "S00012" }]\nports = { p = "a.in", q = "a.out" }\n',
        )
        assert resolve(TWO_PORT, top).findings == {}

    def test_a_part_without_ports_needs_no_rename_map(self):
        top = composite("S00081", 'parts = [{ as = "a", use = "S00010" }]\n')
        assert resolve(LINK_E, top).findings == {}


class TestExportUnknown:
    def test_a_rename_naming_a_missing_port_or_part(self):
        top = composite(
            "S00082",
            'parts = [{ as = "a", use = "S00012" }]\n'
            'ports = { p = "a.in", q = "a.out", x = "a.nope", y = "zz.in", z = "in" }\n',
        )
        resolution = resolve(TWO_PORT, top)
        assert located(resolution, "S00082") == [
            ("export-unknown", "/ports/x"),
            ("export-unknown", "/ports/y"),
            ("export-unknown", "/ports/z"),
        ]
        assert "S00082" not in resolution.symbols

    def test_a_slot_reference_naming_a_missing_slot_or_part(self):
        top = composite(
            "S00082",
            'parts = [{ as = "c", use = "S00227" }]\n'
            'ports = { in = "c.in", out = "c.out" }\n'
            '[slots]\nx = "c.nope"\ny = "zz.tag"\nz = "tag"\nok = "c.tag"\n',
        )
        resolution = resolve_library(CONFIG, guide_sources() | files(top))
        assert located(resolution, "S00082") == [
            ("export-unknown", "/slots/x"),
            ("export-unknown", "/slots/y"),
            ("export-unknown", "/slots/z"),
        ]

    def test_pointer_locations_escape_slash_and_tilde(self):
        top = composite(
            "S00082", 'parts = [{ as = "a", use = "S00010" }]\nports = { "a/b~c" = "a.nope" }\n'
        )
        assert located(resolve(LINK_E, top), "S00082") == [("export-unknown", "/ports/a~1b~0c")]

    def test_does_not_fire_when_everything_named_exists(self):
        top = composite(
            "S00082",
            'parts = [{ as = "c", use = "S00227" }]\n'
            'ports = { in = "c.in", out = "c.out" }\n'
            '[slots]\n"marking.in" = "c.marking.in"\n',
        )
        assert resolve_library(CONFIG, guide_sources() | files(top)).findings == {}


class TestFileRules:
    def test_schema_failure_gives_findings_and_no_symbol(self):
        bad = tomllib.loads(LINK_E.replace('kind = "element"', 'kind = "bogus"'))
        resolution = resolve_library(CONFIG, {"S00010": bad})
        assert located(resolution, "S00010") == [("schema", "/kind")]
        assert resolution.symbols == {}

    def test_a_non_table_source_is_a_schema_finding(self):
        resolution = resolve_library(CONFIG, {"S00010": []})  # ty: ignore[invalid-argument-type]
        assert located(resolution, "S00010") == [("schema", None)]

    def test_a_file_that_uses_a_schema_broken_file_reports_nothing_of_its_own(self):
        bad = tomllib.loads(LINK_E.replace('kind = "element"', 'kind = "bogus"'))
        top = tomllib.loads(composite("S00090", 'parts = [{ as = "a", use = "S00010" }]\n'))
        resolution = resolve_library(CONFIG, {"S00010": bad, "S00090": top})
        assert sorted(resolution.findings) == ["S00010"]
        assert resolution.symbols == {}

    def test_a_file_that_uses_a_file_that_failed_to_resolve_reports_nothing_of_its_own(self):
        broken = composite("S00091", 'parts = [{ as = "a", use = "S99999" }]\n')
        user = composite("S00092", 'parts = [{ as = "b", use = "S00091" }]\n')
        resolution = resolve(broken, user)
        assert sorted(resolution.findings) == ["S00091"]
        assert resolution.symbols == {}

    def test_metadata_still_resolves_the_symbol(self):
        wrong = LINK_E.replace("Link east", "")
        resolution = resolve(wrong)
        assert located(resolution, "S00010") == [("metadata", "/name")]
        assert "S00010" in resolution.symbols

    def test_metadata_is_checked_against_the_config_and_the_stem(self):
        data = tomllib.loads(LINK_E)
        resolution = resolve_library(LibraryConfig("ISO 14617", "t", r"^X\d+$"), {"S00099": data})
        assert located(resolution, "S00099") == [
            ("metadata", "/reference/number"),
            ("metadata", "/reference/number"),
            ("metadata", "/reference/standard"),
        ]

    def test_metadata_is_checked_for_composites_too(self):
        top = composite("S00090", 'parts = [{ as = "a", use = "S00010" }]\n')
        resolution = resolve_library(
            CONFIG, {"S00010": tomllib.loads(LINK_E), "S00099": tomllib.loads(top)}
        )
        assert located(resolution, "S00099") == [("metadata", "/reference/number")]
        assert "S00099" in resolution.symbols

    def test_a_bad_part_id_is_an_id_format_finding_and_the_symbol_still_resolves(self):
        top = composite("S00093", 'parts = [{ as = "Bad-Id", use = "S00010" }]\n')
        resolution = resolve(LINK_E, top)
        assert located(resolution, "S00093") == [("id-format", "/parts/0/as")]
        assert "S00093" in resolution.symbols

    def test_a_duplicate_part_id_is_a_schema_finding(self):
        top = composite(
            "S00093",
            'parts = [{ as = "a", use = "S00010" }, { as = "a", use = "S00010", at = [2, 0] }]\n',
        )
        resolution = resolve(LINK_E, top)
        assert located(resolution, "S00093") == [("schema", "/parts/1/as")]
        assert "S00093" not in resolution.symbols

    def test_ports_as_an_array_in_a_composite_is_a_schema_finding(self):
        top = composite(
            "S00093",
            'parts = [{ as = "a", use = "S00012" }]\n'
            'ports = [{ id = "in", at = [0, -2], dir = "N" }]\n',
        )
        resolution = resolve(TWO_PORT, top)
        assert located(resolution, "S00093") == [("schema", "/ports")]
        assert "S00093" not in resolution.symbols

    def test_a_rename_map_without_parts_is_a_schema_finding(self):
        atomic = LINK_E + 'ports = { p = "a.in" }\n'
        assert located(resolve(atomic), "S00010") == [("schema", "/ports")]

    def test_a_slot_reference_without_parts_is_a_schema_finding(self):
        atomic = LINK_E + '[slots]\ntag = "a.tag"\n'
        resolution = resolve(atomic)
        assert located(resolution, "S00010") == [("schema", "/slots/tag")]
        assert resolution.symbols == {}

    def test_repeat_below_one_is_a_schema_finding_at_the_repeat_key(self):
        top = composite("S00094", 'parts = [{ as = "a", use = "S00227", repeat = 0 }]\n')
        resolution = resolve_library(CONFIG, guide_sources() | files(top))
        assert located(resolution, "S00094") == [("schema", "/parts/0/repeat")]
        assert "S00094" not in resolution.symbols

    def test_repeat_of_a_part_without_a_through_path_is_a_schema_finding(self):
        top = composite("S00094", 'parts = [{ as = "a", use = "S00013", repeat = 2 }]\n')
        resolution = resolve(TWO_PORT_PLAIN, top)
        assert located(resolution, "S00094") == [("schema", "/parts/0/repeat")]
        assert "through" in resolution.findings["S00094"][0].message

    def test_repeat_of_one_does_not_fire(self):
        top = composite(
            "S00094",
            'parts = [{ as = "a", use = "S00012", repeat = 1 }]\n'
            'ports = { p = "a.1.in", q = "a.1.out" }\n',
        )
        assert resolve(TWO_PORT, top).findings == {}

    def test_every_finding_is_an_error(self):
        top = composite("S00094", 'parts = [{ as = "a", use = "S99999" }]\n')
        assert {f.severity for fs in resolve(top).findings.values() for f in fs} == {Severity.ERROR}


class TestDeterminism:
    def test_findings_are_ordered_by_stem_then_rule_then_natural_location(self):
        parts = ", ".join(f'{{ as = "A{i}", use = "S00010", at = [{i}, 0] }}' for i in range(12))
        wrong = composite("S00096", f"parts = [{parts}]\n").replace("Composite S00096", "")
        broken = composite("S00095", 'parts = [{ as = "a", use = "S99999" }]\n')
        resolution = resolve(LINK_E, wrong, broken)
        assert list(resolution.findings) == ["S00095", "S00096"]
        assert located(resolution, "S00096") == [
            *[("id-format", f"/parts/{i}/as") for i in range(12)],
            ("metadata", "/name"),
        ]

    def test_the_result_does_not_depend_on_the_order_of_the_sources(self):
        forward = files(
            LINK_E,
            LINK_W,
            TWO_PORT,
            composite("S00097", 'parts = [{ as = "a", use = "S99999" }]\n'),
        )
        backward = dict(reversed(forward.items()))
        one, two = resolve_library(CONFIG, forward), resolve_library(CONFIG, backward)
        assert one == two
        assert list(one.symbols) == list(two.symbols) == sorted(one.symbols)
        assert list(one.findings) == list(two.findings)

    def test_stems_without_findings_are_not_listed(self):
        assert resolve(LINK_E, LINK_W).findings == {}
