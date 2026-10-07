"""Connectivity group: the six rules on nodes, paths and the through path."""

import math
from pathlib import Path

import pytest
from build_symbol import plain_symbol
from fixture_pipeline import run_fixture, run_fixture_by_file
from hypothesis import given, settings
from hypothesis import strategies as st

from symdef.build import load_library
from symdef.geometry import Direction, Orientation, Point
from symdef.lint import CHECKS, RULES, lint
from symdef.lint.connectivity import (
    node_invalid,
    path_invalid,
    port_isolated,
    through_axis,
    through_count,
    through_missing,
)
from symdef.model import (
    Node,
    Port,
    Severity,
    SymbolKind,
)
from symdef.model import (
    Path as SymbolPath,
)
from symdef.orient import orient

P = Point
N, E, S, W = Direction.N, Direction.E, Direction.S, Direction.W
GUIDE = Path(__file__).resolve().parent / "fixtures" / "guide"
CONNECTIVITY_RULES = (
    "node-invalid",
    "path-invalid",
    "through-count",
    "through-axis",
    "through-missing",
    "port-isolated",
)
WARNINGS = {"through-missing", "port-isolated"}


def port(id_, x, y, direction):
    return Port(id_, P(x, y), direction)


def path(a, b, *, through=False, kind="conductor"):
    return SymbolPath(a, b, kind, through)


def where(findings):
    return [(f.rule, f.location) for f in findings]


IN_OUT = (port("in", 0, -2, N), port("out", 0, 2, S))


@pytest.fixture(scope="module")
def library():
    return load_library(GUIDE)


class TestRegistration:
    @pytest.mark.parametrize("rule_id", CONNECTIVITY_RULES)
    def test_every_connectivity_rule_is_registered_with_a_check(self, rule_id):
        rule = RULES[rule_id]
        expected = Severity.WARNING if rule_id in WARNINGS else Severity.ERROR
        assert (rule.group, rule.severity) == ("Connectivity", expected)
        assert rule_id in CHECKS

    def test_none_of_them_depends_on_the_orientation(self):
        assert not any(RULES[r].orientation_dependent for r in CONNECTIVITY_RULES)


class TestNodeInvalid:
    def test_no_nodes_and_good_nodes_are_clean(self):
        assert node_invalid(plain_symbol(ports=IN_OUT)) == ()
        assert node_invalid(plain_symbol(ports=IN_OUT, nodes=(Node(("in", "out")),))) == ()

    def test_an_unknown_port_fires_at_the_node_and_names_it(self):
        symbol = plain_symbol(ports=IN_OUT, nodes=(Node(("in",)), Node(("ghost",))))
        (found,) = node_invalid(symbol)
        assert (found.rule, found.severity, found.location) == (
            "node-invalid",
            Severity.ERROR,
            "nodes[1]",
        )
        assert found.orientation is None
        assert "'ghost'" in found.message

    def test_a_port_in_two_nodes_fires_at_the_later_node(self):
        symbol = plain_symbol(ports=IN_OUT, nodes=(Node(("in", "out")), Node(("out",))))
        (found,) = node_invalid(symbol)
        assert found.location == "nodes[1]"
        assert "'out'" in found.message
        assert "nodes[0]" in found.message

    def test_a_port_listed_twice_in_one_node_counts_as_listed_twice(self):
        symbol = plain_symbol(ports=IN_OUT, nodes=(Node(("in", "in")),))
        (found,) = node_invalid(symbol)
        assert found.location == "nodes[0]"

    def test_every_offence_gets_its_own_finding(self):
        symbol = plain_symbol(
            ports=IN_OUT, nodes=(Node(("in", "x")), Node(("in", "y")), Node(("out", "out")))
        )
        assert where(node_invalid(symbol)) == [
            ("node-invalid", f"nodes[{i}]") for i in (0, 1, 1, 2)
        ]

    def test_an_unknown_port_listed_twice_is_reported_as_unknown_each_time(self):
        symbol = plain_symbol(ports=IN_OUT, nodes=(Node(("x", "x")),))
        assert len(node_invalid(symbol)) == 2

    def test_a_potential_or_an_empty_node_is_not_invalid_on_its_own(self):
        symbol = plain_symbol(ports=IN_OUT, nodes=(Node(("in",), "earth"), Node(())))
        assert node_invalid(symbol) == ()


class TestPathInvalid:
    def test_good_paths_are_clean(self):
        assert path_invalid(plain_symbol(ports=IN_OUT, paths=(path("in", "out"),))) == ()

    def test_an_unknown_port_fires_at_the_path_and_names_it(self):
        symbol = plain_symbol(ports=IN_OUT, paths=(path("in", "ghost"),))
        (found,) = path_invalid(symbol)
        assert (found.rule, found.severity, found.location) == (
            "path-invalid",
            Severity.ERROR,
            "paths[0]",
        )
        assert "'ghost'" in found.message

    def test_both_ports_unknown_is_one_finding_naming_both(self):
        (found,) = path_invalid(plain_symbol(ports=IN_OUT, paths=(path("x", "y"),)))
        assert "'x'" in found.message
        assert "'y'" in found.message

    def test_two_ports_of_one_declared_node_fire(self):
        symbol = plain_symbol(
            ports=IN_OUT, nodes=(Node(("in", "out")),), paths=(path("in", "out"),)
        )
        (found,) = path_invalid(symbol)
        assert found.location == "paths[0]"
        assert "one node" in found.message

    def test_a_path_from_a_port_to_itself_joins_two_ports_of_one_node(self):
        (found,) = path_invalid(plain_symbol(ports=IN_OUT, paths=(path("in", "in"),)))
        assert "one node" in found.message

    def test_a_second_path_between_the_same_nodes_fires_at_the_later_path(self):
        symbol = plain_symbol(
            ports=IN_OUT, paths=(path("in", "out"), path("out", "in", kind="diode"))
        )
        (found,) = path_invalid(symbol)
        assert found.location == "paths[1]"
        assert "paths[0]" in found.message

    def test_implicit_single_port_nodes_count_as_nodes(self):
        symbol = plain_symbol(
            ports=(*IN_OUT, port("c", 2, 0, E)), paths=(path("in", "out"), path("in", "c"))
        )
        assert path_invalid(symbol) == ()

    def test_paths_between_different_ports_of_the_same_two_nodes_are_duplicates(self):
        symbol = plain_symbol(
            ports=(port("a", 0, 0, N), port("b", 0, 0, S), port("c", 2, 0, E), port("d", 2, 0, W)),
            nodes=(Node(("a", "b")), Node(("c", "d"))),
            paths=(path("a", "c"), path("b", "d")),
        )
        assert where(path_invalid(symbol)) == [("path-invalid", "paths[1]")]

    def test_a_port_in_two_nodes_uses_the_first_node_and_nothing_raises(self):
        symbol = plain_symbol(
            ports=IN_OUT,
            nodes=(Node(("in",)), Node(("out", "in"))),
            paths=(path("in", "out"), path("in", "out")),
        )
        assert where(path_invalid(symbol)) == [("path-invalid", "paths[1]")]

    def test_a_path_that_joins_one_node_is_not_also_a_duplicate(self):
        symbol = plain_symbol(
            ports=IN_OUT,
            nodes=(Node(("in", "out")),),
            paths=(path("in", "out"), path("in", "out")),
        )
        assert where(path_invalid(symbol)) == [
            ("path-invalid", "paths[0]"),
            ("path-invalid", "paths[1]"),
        ]

    def test_two_ports_with_one_id_are_one_node(self):
        symbol = plain_symbol(
            ports=(port("a", 0, 0, N), port("a", 1, 0, N)), paths=(path("a", "a"),)
        )
        assert where(path_invalid(symbol)) == [("path-invalid", "paths[0]")]


class TestThroughCount:
    def test_zero_or_one_through_path_is_clean(self):
        assert through_count(plain_symbol(ports=IN_OUT, paths=(path("in", "out"),))) == ()
        assert (
            through_count(plain_symbol(ports=IN_OUT, paths=(path("in", "out", through=True),)))
            == ()
        )

    def test_a_second_through_path_fires_at_it_and_names_the_first(self):
        symbol = plain_symbol(
            ports=IN_OUT,
            paths=(path("in", "out", through=True), path("out", "in", through=True)),
        )
        (found,) = through_count(symbol)
        assert (found.rule, found.severity, found.location) == (
            "through-count",
            Severity.ERROR,
            "paths[1]",
        )
        assert "paths[0]" in found.message

    def test_three_through_paths_give_two_findings_and_ignore_the_others(self):
        symbol = plain_symbol(
            ports=IN_OUT,
            paths=(
                path("in", "out", through=True),
                path("in", "out"),
                path("in", "out", through=True),
                path("in", "out", through=True),
            ),
        )
        assert where(through_count(symbol)) == [
            ("through-count", "paths[2]"),
            ("through-count", "paths[3]"),
        ]


def through_symbol(from_at, to_at, from_dir=N, to_dir=S):
    return plain_symbol(
        ports=(Port("in", P(*from_at), from_dir), Port("out", P(*to_at), to_dir)),
        paths=(path("in", "out", through=True),),
    )


class TestThroughAxis:
    @pytest.mark.parametrize("a", [1, 2, 3, 10, 100])
    def test_ports_at_zero_minus_a_north_and_zero_a_south_are_clean(self, a):
        assert through_axis(through_symbol((0, -a), (0, a))) == ()

    def test_no_through_path_is_clean(self):
        assert through_axis(plain_symbol(ports=IN_OUT, paths=(path("in", "out"),))) == ()

    def test_the_finding_is_at_the_through_path(self):
        (found,) = through_axis(through_symbol((1, -2), (0, 2)))
        assert (found.rule, found.severity, found.location) == (
            "through-axis",
            Severity.ERROR,
            "paths[0]",
        )
        assert found.orientation is None

    @pytest.mark.parametrize(
        ("from_at", "to_at"),
        [
            ((1, -2), (0, 2)),  # from off the axis
            ((0, -2), (1, 2)),  # to off the axis
            ((0, -2), (0, 3)),  # unequal a
            ((0, -2), (0, 1)),
            ((0, 2), (0, -2)),  # swapped: from is the S end
            ((-2, 0), (2, 0)),  # horizontal
            ((0, -0.5), (0, 0.5)),  # a is not a whole number
            ((0, -1.5), (0, 1.5)),
            ((0, 0), (0, 0)),  # a = 0
            ((0, 2), (0, 2)),
        ],
    )
    def test_anything_else_fires(self, from_at, to_at):
        assert where(through_axis(through_symbol(from_at, to_at))) == [("through-axis", "paths[0]")]

    def test_a_from_port_that_does_not_point_north_fires(self):
        assert through_axis(through_symbol((0, -2), (0, 2), from_dir=E))
        assert through_axis(through_symbol((0, -2), (0, 2), from_dir=S))

    def test_a_to_port_that_does_not_point_south_fires(self):
        assert through_axis(through_symbol((0, -2), (0, 2), to_dir=N))
        assert through_axis(through_symbol((0, -2), (0, 2), to_dir=W))

    def test_a_negative_zero_is_on_the_axis(self):
        assert through_axis(through_symbol((-0.0, -2), (0.0, 2))) == ()

    def test_the_comparison_is_exact(self):
        assert through_axis(through_symbol((1e-12, -2), (0, 2)))
        assert through_axis(through_symbol((0, -2.0000000001), (0, 2)))

    def test_an_unknown_port_is_not_reported_here(self):
        symbol = plain_symbol(
            ports=(port("in", 0, -2, N),), paths=(path("in", "ghost", through=True),)
        )
        assert through_axis(symbol) == ()
        symbol = plain_symbol(ports=(), paths=(path("x", "y", through=True),))
        assert through_axis(symbol) == ()

    def test_every_through_path_is_checked_whatever_through_count_says(self):
        symbol = plain_symbol(
            ports=(*IN_OUT, port("a", 1, -2, N), port("b", 1, 2, S)),
            paths=(
                path("in", "out", through=True),
                path("a", "b", through=True),
                path("a", "out", through=True),
            ),
        )
        assert where(through_axis(symbol)) == [
            ("through-axis", "paths[1]"),
            ("through-axis", "paths[2]"),
        ]

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 1e300])
    def test_non_finite_and_huge_values_do_not_raise(self, bad):
        found = through_axis(through_symbol((0, -bad), (0, bad)))
        assert all(f.rule == "through-axis" for f in found)

    def test_the_first_port_with_an_id_is_used(self):
        symbol = plain_symbol(
            ports=(port("in", 0, -2, N), port("out", 0, 2, S), port("in", 5, 5, W)),
            paths=(path("in", "out", through=True),),
        )
        assert through_axis(symbol) == ()


def node_symbol(kind=SymbolKind.SYMBOL, **changes):
    return plain_symbol(kind=kind, ports=IN_OUT, **changes)


class TestThroughMissing:
    def test_a_symbol_with_two_nodes_and_no_through_path_warns(self):
        (found,) = through_missing(node_symbol(paths=(path("in", "out"),)))
        assert (found.rule, found.severity, found.location) == (
            "through-missing",
            Severity.WARNING,
            None,
        )

    def test_implicit_single_port_nodes_count(self):
        assert through_missing(node_symbol())

    def test_a_through_path_silences_it(self):
        assert through_missing(node_symbol(paths=(path("in", "out", through=True),))) == ()

    def test_any_potential_silences_it(self):
        symbol = node_symbol(nodes=(Node(("in",), "protective_earth"),))
        assert through_missing(symbol) == ()

    def test_one_node_is_not_enough(self):
        assert through_missing(node_symbol(nodes=(Node(("in", "out")),))) == ()
        assert through_missing(plain_symbol(kind=SymbolKind.SYMBOL, ports=IN_OUT[:1])) == ()
        assert through_missing(plain_symbol(kind=SymbolKind.SYMBOL)) == ()

    def test_two_nodes_are_enough(self):
        assert through_missing(node_symbol(nodes=(Node(("in",)), Node(("out",)))))

    @pytest.mark.parametrize("kind", [SymbolKind.ELEMENT, SymbolKind.QUALIFIER])
    def test_other_kinds_are_exempt(self, kind):
        assert through_missing(node_symbol(kind=kind)) == ()

    def test_a_non_through_path_does_not_count(self):
        assert through_missing(node_symbol(paths=(path("in", "out", through=False),)))


def isolated_symbol(**changes):
    return plain_symbol(ports=(port("a", 0, 0, N), port("b", 0, 1, S)), **changes)


class TestPortIsolated:
    def test_ports_in_a_path_are_clean(self):
        assert port_isolated(isolated_symbol(paths=(path("a", "b"),))) == ()

    def test_a_port_in_no_path_warns_at_the_port(self):
        (found,) = port_isolated(isolated_symbol(paths=(path("a", "a"),)))
        assert (found.rule, found.severity, found.location) == (
            "port-isolated",
            Severity.WARNING,
            "ports[1]",
        )
        assert "'b'" in found.message

    def test_a_symbol_with_ports_and_no_paths_warns_once_per_port(self):
        assert where(port_isolated(isolated_symbol())) == [
            ("port-isolated", "ports[0]"),
            ("port-isolated", "ports[1]"),
        ]

    def test_a_multi_port_node_silences_both_its_ports(self):
        assert port_isolated(isolated_symbol(nodes=(Node(("a", "b")),))) == ()

    def test_a_declared_one_port_node_is_not_a_multi_port_node(self):
        assert len(port_isolated(isolated_symbol(nodes=(Node(("a",)), Node(("b",)))))) == 2

    def test_a_potential_on_its_node_silences_it(self):
        symbol = isolated_symbol(nodes=(Node(("a",), "earth"),))
        assert where(port_isolated(symbol)) == [("port-isolated", "ports[1]")]

    def test_a_node_listed_twice_ports_is_a_single_port_node(self):
        symbol = isolated_symbol(nodes=(Node(("a", "a")),))
        assert where(port_isolated(symbol)) == [
            ("port-isolated", "ports[0]"),
            ("port-isolated", "ports[1]"),
        ]

    def test_an_unknown_port_in_a_node_does_not_make_it_multi_port(self):
        symbol = isolated_symbol(nodes=(Node(("a", "ghost")),))
        assert "ports[0]" in [f.location for f in port_isolated(symbol)]

    def test_a_port_in_two_nodes_takes_the_potential_of_the_first(self):
        symbol = isolated_symbol(
            nodes=(Node(("a",)), Node(("a",), "earth")), paths=(path("b", "b"),)
        )
        assert where(port_isolated(symbol)) == [("port-isolated", "ports[0]")]
        symbol = isolated_symbol(
            nodes=(Node(("a",), "earth"), Node(("a",))), paths=(path("b", "b"),)
        )
        assert port_isolated(symbol) == ()

    def test_every_kind_is_checked(self):
        for kind in SymbolKind:
            assert port_isolated(isolated_symbol(kind=kind))

    def test_a_path_that_names_it_at_either_end_counts(self):
        assert port_isolated(isolated_symbol(paths=(path("a", "b"),))) == ()
        assert port_isolated(isolated_symbol(paths=(path("b", "a"),))) == ()

    def test_a_symbol_without_ports_is_clean(self):
        assert port_isolated(plain_symbol()) == ()


class TestFixtures:
    @pytest.mark.parametrize("rule_id", CONNECTIVITY_RULES)
    def test_the_fixture_findings_of_the_rule_have_the_registrys_severity(self, rule_id):
        own = [f for f in run_fixture(rule_id) if f.rule == rule_id]
        assert own
        assert {f.severity for f in own} == {RULES[rule_id].severity}

    def test_the_two_through_paths_of_the_count_fixture_break_path_invalid_too(self):
        assert {f.rule for f in run_fixture("through-count")} == {"through-count", "path-invalid"}

    def test_the_through_axis_fixture_has_a_case_for_each_way_to_be_off(self):
        found = run_fixture_by_file("through-axis")
        assert set(found) == {"S00001", "S00002", "S00003"}
        assert all(any(f.rule == "through-axis" for f in fs) for fs in found.values())


class TestInEveryOrientation:
    @given(
        st.sampled_from(list(Orientation)),
        st.sampled_from([(), (Node(("in",)),), (Node(("in", "out")),), (Node(("out",), "earth"),)]),
        st.sampled_from([(), (path("in", "out"),), (path("in", "out", through=True),)]),
    )
    @settings(max_examples=60, deadline=None)
    def test_the_five_invariant_rules_do_not_change_when_the_symbol_is_oriented(
        self, orientation, nodes, paths
    ):
        symbol = node_symbol(nodes=nodes, paths=paths)
        turned = orient(symbol, orientation)
        for rule_id in (
            "node-invalid",
            "path-invalid",
            "through-count",
            "through-missing",
            "port-isolated",
        ):
            assert where(CHECKS[rule_id](turned)) == where(CHECKS[rule_id](symbol)), rule_id

    def test_through_axis_is_a_base_orientation_rule(self):
        symbol = through_symbol((0, -2), (0, 2))
        assert through_axis(symbol) == ()
        assert through_axis(orient(symbol, Orientation.R90))


class TestGuideExamples:
    @pytest.mark.parametrize("number", ["S00227", "S00230", "S00305", "S00171", "S00016"])
    def test_the_guide_examples_trip_no_connectivity_rule(self, library, number):
        assert [f for f in lint(library.get(number)) if f.rule in CONNECTIVITY_RULES] == []

    def test_the_change_over_contact_has_a_through_path_and_a_second_path(self, library):
        symbol = library.get("S00230")
        assert sum(p.through for p in symbol.paths) == 1
        assert len(symbol.paths) == 2
