"""`repeat`: n poles along +x, ports and marking slots prefixed, one dashed link line."""

from dataclasses import replace
from pathlib import Path as FilePath

import deal
import pytest
from hypothesis import given
from hypothesis import strategies as st

from graphical_symbols.geometry import Direction, Line, Point, Style, Weight
from graphical_symbols.load import parse_toml, symbol_from_data
from graphical_symbols.model import (
    Allow,
    Anchor,
    Node,
    Path,
    PathKind,
    Port,
    Potential,
    Reference,
    Slot,
    Status,
    Symbol,
    SymbolKind,
    nodes_of,
)
from graphical_symbols.orient import translate
from graphical_symbols.repeat import repeat

SYMBOLS = FilePath(__file__).resolve().parent / "fixtures" / "guide" / "symbols"
N, E, S, W = Direction.N, Direction.E, Direction.S, Direction.W


def guide_symbol(stem: str) -> Symbol:
    data, findings = parse_toml((SYMBOLS / f"{stem}.toml").read_text(encoding="utf-8"))
    assert data is not None
    assert findings == ()
    return symbol_from_data(data)


def bare(**fields) -> Symbol:
    """A symbol with a vertical through path, plus whatever `fields` override."""
    base = Symbol(
        name="t",
        kind=SymbolKind.SYMBOL,
        status=Status.UNVERIFIED,
        reference=Reference("X", "1"),
        elements=(),
        ports=(Port("in", Point(0, -2), N), Port("out", Point(0, 2), S)),
        paths=(Path("in", "out", PathKind.CONDUCTOR, through=True),),
    )
    return replace(base, **fields)


@pytest.fixture(scope="module")
def s227() -> Symbol:
    return guide_symbol("S00227")


@pytest.fixture(scope="module")
def s230() -> Symbol:
    return guide_symbol("S00230")


class TestOnePole:
    def test_ports_are_renamed_and_not_moved(self, s227):
        result = repeat(s227, 1)
        assert result.ports == (
            Port("1.in", Point(0, -2), N),
            Port("1.out", Point(0, 2), S),
        )

    def test_marking_slots_are_renamed_and_tag_kept(self, s227):
        result = repeat(s227, 1)
        assert result.slots == (
            Slot("tag", Point(-1.5, 0), W, (6, 1)),
            Slot("marking.1.in", Point(0.25, -1.5), E, (1.5, 1)),
            Slot("marking.1.out", Point(0.25, 1.5), E, (1.5, 1)),
        )

    def test_implicit_nodes_become_explicit(self, s227):
        assert s227.nodes == ()
        assert repeat(s227, 1).nodes == (Node(("1.in",)), Node(("1.out",)))

    def test_through_path_stays_through(self, s227):
        assert repeat(s227, 1).paths == (Path("1.in", "1.out", PathKind.SWITCH_OPEN, through=True),)

    def test_elements_anchors_and_kind_are_unchanged(self, s227):
        result = repeat(s227, 1)
        assert result.elements == s227.elements
        assert result.anchors == s227.anchors
        assert (result.name, result.kind, result.status, result.reference) == (
            s227.name,
            s227.kind,
            s227.status,
            s227.reference,
        )

    def test_pole_pitch_is_the_default_pitch(self, s227):
        assert repeat(s227, 1).pole_pitch == 4

    def test_pole_pitch_is_the_declared_pitch(self, s230):
        assert repeat(s230, 1).pole_pitch == 8


class TestBoundLeadsAreRenamed:
    """A bound lead's `port` is prefixed `<k>.`, the same prefix its port gets (D40)."""

    def test_a_bound_leads_port_is_prefixed_per_pole(self):
        symbol = bare(
            elements=(
                Line(Point(0, -2), Point(0, -1), port="in"),
                Line(Point(0, 2), Point(0, 1), port="out"),
            )
        )
        result = repeat(symbol, 2)
        ports = [e.port for e in result.elements if isinstance(e, Line)]
        assert ports == ["1.in", "1.out", "2.in", "2.out"]

    def test_an_unbound_lead_is_left_alone(self):
        symbol = bare(elements=(Line(Point(0, -2), Point(0, -1)),))
        result = repeat(symbol, 2)
        ports = [e.port for e in result.elements if isinstance(e, Line)]
        assert ports == [None, None]


class TestThreePolesOfS00227:
    @pytest.fixture
    def result(self, s227) -> Symbol:
        return repeat(s227, 3)

    def test_ports_are_prefixed_and_four_apart(self, result):
        assert result.ports == (
            Port("1.in", Point(0, -2), N),
            Port("1.out", Point(0, 2), S),
            Port("2.in", Point(4, -2), N),
            Port("2.out", Point(4, 2), S),
            Port("3.in", Point(8, -2), N),
            Port("3.out", Point(8, 2), S),
        )

    def test_slots(self, result):
        assert result.slots == (
            Slot("tag", Point(-1.5, 0), W, (6, 1)),
            Slot("marking.1.in", Point(0.25, -1.5), E, (1.5, 1)),
            Slot("marking.1.out", Point(0.25, 1.5), E, (1.5, 1)),
            Slot("marking.2.in", Point(4.25, -1.5), E, (1.5, 1)),
            Slot("marking.2.out", Point(4.25, 1.5), E, (1.5, 1)),
            Slot("marking.3.in", Point(8.25, -1.5), E, (1.5, 1)),
            Slot("marking.3.out", Point(8.25, 1.5), E, (1.5, 1)),
        )

    def test_nodes_repeat_per_pole(self, result):
        assert result.nodes == tuple(Node((f"{k}.{p}",)) for k in (1, 2, 3) for p in ("in", "out"))

    def test_only_pole_one_is_through(self, result):
        assert result.paths == (
            Path("1.in", "1.out", PathKind.SWITCH_OPEN, through=True),
            Path("2.in", "2.out", PathKind.SWITCH_OPEN, through=False),
            Path("3.in", "3.out", PathKind.SWITCH_OPEN, through=False),
        )

    def test_elements_are_kept_in_pole_order(self, result, s227):
        poles = tuple(e for k in range(3) for e in translate(s227, 4 * k, 0).elements)
        assert result.elements[:-1] == poles
        assert len(result.elements) == 3 * 3 + 1

    def test_dashed_link_line_spans_pole_one_to_pole_three(self, result):
        assert result.elements[-1] == Line(
            Point(-0.5, 0), Point(7.5, 0), Weight.NORMAL, Style.DASHED
        )

    def test_only_pole_one_anchors_remain(self, result):
        assert result.anchors == (Anchor("link", Point(-0.5, 0), W),)

    def test_pole_pitch_is_the_pole_count_times_the_pitch(self, result):
        assert result.pole_pitch == 12


class TestTwoPolesOfS00230:
    @pytest.fixture
    def result(self, s230) -> Symbol:
        return repeat(s230, 2)

    def test_ports_use_the_declared_pitch(self, result):
        assert result.ports == (
            Port("1.com", Point(0, 2), S, "common"),
            Port("1.no", Point(0, -2), N, "closes on actuation"),
            Port("1.nc", Point(-2, -2), N, "opens on actuation"),
            Port("2.com", Point(8, 2), S, "common"),
            Port("2.no", Point(8, -2), N, "closes on actuation"),
            Port("2.nc", Point(6, -2), N, "opens on actuation"),
        )

    def test_paths_clear_through_on_pole_two_only(self, result):
        assert result.paths == (
            Path("1.no", "1.com", PathKind.SWITCH_OPEN, through=True),
            Path("1.nc", "1.com", PathKind.SWITCH_CLOSED),
            Path("2.no", "2.com", PathKind.SWITCH_OPEN),
            Path("2.nc", "2.com", PathKind.SWITCH_CLOSED),
        )

    def test_nodes_repeat_per_pole(self, result):
        assert result.nodes == (
            Node(("1.com",)),
            Node(("1.no",)),
            Node(("1.nc",)),
            Node(("2.com",)),
            Node(("2.no",)),
            Node(("2.nc",)),
        )

    def test_slots(self, result):
        assert result.slots == (
            Slot("tag", Point(-4, 0), W, (6, 1)),
            Slot("marking.1.com", Point(0.25, 1.5), E, (1.5, 1)),
            Slot("marking.1.no", Point(0.25, -1.5), E, (1.5, 1)),
            Slot("marking.1.nc", Point(-2.25, -1.5), W, (1.5, 1)),
            Slot("marking.2.com", Point(8.25, 1.5), E, (1.5, 1)),
            Slot("marking.2.no", Point(8.25, -1.5), E, (1.5, 1)),
            Slot("marking.2.nc", Point(5.75, -1.5), W, (1.5, 1)),
        )

    def test_link_and_pole_pitch(self, result, s230):
        assert result.elements[-1] == Line(
            Point(-0.5, 0), Point(7.5, 0), Weight.NORMAL, Style.DASHED
        )
        assert len(result.elements) == 2 * len(s230.elements) + 1
        assert result.anchors == s230.anchors
        assert result.pole_pitch == 16


class TestEdgeCases:
    def test_no_link_anchor_adds_no_line(self):
        symbol = bare(elements=(Line(Point(0, -2), Point(0, 2)),))
        assert len(repeat(symbol, 3).elements) == 3

    def test_one_pole_adds_no_link_line(self, s227):
        assert len(repeat(s227, 1).elements) == len(s227.elements)

    def test_a_link_anchor_with_another_id_adds_no_line(self):
        symbol = bare(anchors=(Anchor("top", Point(0, -2), N),))
        assert repeat(symbol, 2).elements == ()

    def test_potential_is_preserved(self):
        symbol = bare(
            nodes=(Node(("in",), Potential.EARTH), Node(("out",))),
            paths=(Path("in", "out", PathKind.CONDUCTOR, through=True),),
        )
        assert repeat(symbol, 2).nodes == (
            Node(("1.in",), Potential.EARTH),
            Node(("1.out",)),
            Node(("2.in",), Potential.EARTH),
            Node(("2.out",)),
        )

    def test_multi_port_node_keeps_all_its_ports_prefixed(self):
        symbol = bare(
            ports=(
                Port("in", Point(0, -2), N),
                Port("in2", Point(1, -2), N),
                Port("out", Point(0, 2), S),
            ),
            nodes=(Node(("in", "in2")),),
        )
        assert repeat(symbol, 2).nodes == (
            Node(("1.in", "1.in2")),
            Node(("1.out",)),
            Node(("2.in", "2.in2")),
            Node(("2.out",)),
        )

    def test_lint_allow_is_carried_over_unchanged(self):
        allow = (Allow("port-spacing", "on purpose"),)
        assert repeat(bare(lint_allow=allow), 3).lint_allow == allow

    def test_value_slot_comes_from_pole_one_only_and_is_not_prefixed(self):
        symbol = bare(
            slots=(
                Slot("tag", Point(-1, 0), W, (2, 1)),
                Slot("value", Point(1, 0), E, (2, 1)),
                Slot("marking.in", Point(0.5, -1), E, (1, 1)),
            )
        )
        assert repeat(symbol, 2).slots == (
            Slot("tag", Point(-1, 0), W, (2, 1)),
            Slot("value", Point(1, 0), E, (2, 1)),
            Slot("marking.1.in", Point(0.5, -1), E, (1, 1)),
            Slot("marking.2.in", Point(4.5, -1), E, (1, 1)),
        )

    def test_an_unknown_slot_id_comes_from_pole_one_only(self):
        symbol = bare(slots=(Slot("note", Point(1, 0), E, (2, 1)),))
        assert repeat(symbol, 3).slots == (Slot("note", Point(1, 0), E, (2, 1)),)

    def test_dotted_ids_from_composition_are_prefixed_whole(self):
        symbol = bare(
            ports=(Port("c.in", Point(0, -2), N), Port("c.out", Point(0, 2), S)),
            paths=(Path("c.in", "c.out", PathKind.CONDUCTOR, through=True),),
            slots=(Slot("marking.c.in", Point(0.5, -1), E, (1, 1)),),
        )
        result = repeat(symbol, 2)
        assert tuple(p.id for p in result.ports) == ("1.c.in", "1.c.out", "2.c.in", "2.c.out")
        assert tuple(s.id for s in result.slots) == ("marking.1.c.in", "marking.2.c.in")

    def test_input_is_not_mutated(self, s227):
        rebuilt = guide_symbol("S00227")  # read again, so it is not the object `repeat` gets
        assert rebuilt is not s227
        repeat(s227, 3)
        assert s227 == rebuilt


class TestPreconditions:
    @pytest.mark.parametrize("n", [0, -1])
    def test_a_pole_count_below_one_is_rejected(self, s227, n):
        with pytest.raises(deal.PreContractError):
            repeat(s227, n)

    def test_a_symbol_without_a_through_path_is_rejected(self):
        with pytest.raises(deal.PreContractError):
            repeat(bare(paths=(Path("in", "out", PathKind.CONDUCTOR),)), 2)

    def test_a_symbol_without_paths_is_rejected(self):
        with pytest.raises(deal.PreContractError):
            repeat(bare(paths=()), 1)


@st.composite
def repeatable_symbols(draw):
    """A symbol with a vertical through path, an extra port at some x <= 0, and a pitch."""
    extra_x = draw(st.integers(min_value=0, max_value=6)) / -2
    pitch = draw(st.sampled_from([None, 4, 8, 12]))
    return bare(
        ports=(
            Port("in", Point(0, -2), N),
            Port("out", Point(0, 2), S),
            Port("aux", Point(extra_x, -2), N),
        ),
        pole_pitch=pitch,
    )


@given(symbol=repeatable_symbols(), n=st.integers(min_value=1, max_value=8))
def test_port_x_extent_grows_by_the_pitch_per_extra_pole(symbol, n):
    pitch = symbol.pole_pitch or 4
    result = repeat(symbol, n)
    xs = [p.position.x for p in symbol.ports]
    result_xs = [p.position.x for p in result.ports]
    assert max(result_xs) - min(result_xs) == max(xs) - min(xs) + (n - 1) * pitch
    ids = [p.id for p in result.ports]
    assert len(ids) == n * len(symbol.ports)
    assert len(set(ids)) == len(ids)
    assert result.pole_pitch == n * pitch
    assert sum(path.through for path in result.paths) == 1
    listed = [port_id for node in nodes_of(result) for port_id in node.ports]
    assert sorted(listed) == sorted(ids)
