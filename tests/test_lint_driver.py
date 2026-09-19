"""The `lint(symbol)` driver: running the rules, ordering, exemptions, orientations, totality."""

import math
from pathlib import Path

import pytest
from build_symbol import plain_symbol
from hypothesis import given, settings
from hypothesis import strategies as st

import graphical_symbols
from graphical_symbols import lint as exported_lint
from graphical_symbols.build import load_library
from graphical_symbols.geometry import (
    Arc,
    Circle,
    Direction,
    Fill,
    Line,
    Orientation,
    Point,
    Polyline,
    Text,
)
from graphical_symbols.lint import CHECKS, RULES, lint, ordered, run_checks
from graphical_symbols.lint.registry import RULE_IDS, Rule
from graphical_symbols.model import (
    Allow,
    Anchor,
    Finding,
    Node,
    PathKind,
    Port,
    Potential,
    Severity,
    Slot,
    Symbol,
    SymbolKind,
)
from graphical_symbols.model import Path as SymbolPath
from graphical_symbols.orient import orient

P = Point
GUIDE = Path(__file__).resolve().parent / "fixtures" / "guide"
# The rules that are computed while linting, not by a check, or by the resolver.
RESOLVER_RULES = {
    "schema",
    "metadata",
    "part-unknown",
    "part-cycle",
    "part-anchor",
    "part-port-unexported",
    "export-unknown",
}
DRIVER_RULES = {"allow-unknown", "allow-unused"}
THIS_TASK = {
    "id-format",
    "off-drawing-grid",
    "degenerate",
    "text-too-large",
    "anchor-duplicate-id",
    "anchor-off-geometry",
    "allow-unknown",
    "allow-unused",
}


class TestRegistration:
    def test_lint_is_the_packages_function(self):
        assert exported_lint is lint
        assert graphical_symbols.__all__.count("lint") == 1

    def test_the_guide_names_33_rules(self):
        assert len(RULE_IDS) == 33

    def test_every_check_belongs_to_a_registered_rule(self):
        assert set(CHECKS) <= set(RULES)

    def test_every_registered_rule_has_exactly_one_producer(self):
        checked = set(CHECKS)
        assert checked.isdisjoint(RESOLVER_RULES | DRIVER_RULES)
        assert set(RULES) == checked | RESOLVER_RULES | DRIVER_RULES

    def test_the_rules_of_this_task_are_registered(self):
        assert set(RULES) >= THIS_TASK

    def test_only_three_rules_are_warnings(self):
        warnings = {r.id for r in RULES.values() if r.severity is Severity.WARNING}
        assert warnings == {"anchor-off-geometry", "through-missing", "port-isolated"}

    def test_none_of_this_tasks_rules_depends_on_the_orientation(self):
        assert not any(RULES[rule_id].orientation_dependent for rule_id in THIS_TASK)


class TestLint:
    def test_a_clean_symbol_has_no_findings(self):
        assert lint(plain_symbol()) == ()

    def test_findings_of_all_the_rules_of_this_task(self):
        symbol = plain_symbol(
            elements=(
                Line(P(0, 0), P(0.1, 1)),
                Line(P(1, 1), P(1, 1)),
                Text("M", P(0, 0), 2),
            ),
            ports=(Port("In", P(0, 0), Direction.N),),
            anchors=(
                Anchor("a", P(0, 0), Direction.W),
                Anchor("a", P(5, 5), Direction.W),
                Anchor("B", P(0, 0), Direction.W),
            ),
            lint_allow=(Allow("nope", "x"), Allow("through-count", "x")),
        )
        found = [f for f in lint(symbol) if f.rule in THIS_TASK]  # the ports rules fire too
        assert [(f.rule, f.location) for f in found] == [
            ("id-format", "anchors[2]"),
            ("id-format", "ports[0]"),
            ("off-drawing-grid", "elements[0]"),
            ("degenerate", "elements[1]"),
            ("text-too-large", "elements[2]"),
            ("anchor-duplicate-id", "anchors[1]"),
            ("anchor-off-geometry", "anchors[1]"),
            ("allow-unknown", "lint_allow[0]"),
            ("allow-unused", "lint_allow[1]"),
        ]

    def test_findings_of_rules_that_do_not_depend_on_the_orientation_have_none(self):
        symbol = plain_symbol(elements=(Circle(P(0, 0), 0.3),))
        assert [f.orientation for f in lint(symbol)] == [None]

    def test_severity_comes_from_the_registry(self):
        symbol = plain_symbol(anchors=(Anchor("a", P(3, 3), Direction.W),))
        (finding,) = lint(symbol)
        assert finding.severity is Severity.WARNING

    def test_locations_sort_as_numbers(self):
        elements = tuple(Circle(P(0, 0), 0.3 + i) for i in range(12))
        found = lint(plain_symbol(elements=elements))
        assert [f.location for f in found] == [f"elements[{i}]" for i in range(12)]

    def test_linting_is_deterministic(self):
        symbol = plain_symbol(elements=(Circle(P(0, 0), 0.3), Circle(P(0, 0), 0)))
        assert lint(symbol) == lint(symbol)


class TestExemptions:
    violation = plain_symbol(elements=(Line(P(0, 0), P(0, 1)), Circle(P(0, 0), 0.3)))

    def test_the_violation_fires_without_an_exemption(self):
        assert [f.rule for f in lint(self.violation)] == ["off-drawing-grid"]

    def test_a_matching_exemption_lints_clean(self):
        exempted = plain_symbol(
            elements=self.violation.elements,
            lint_allow=(Allow("off-drawing-grid", "a deliberate stroke"),),
        )
        assert lint(exempted) == ()

    def test_removing_the_exemption_makes_it_fire_again(self):
        exempted = plain_symbol(
            elements=self.violation.elements,
            lint_allow=(Allow("off-drawing-grid", "a deliberate stroke"),),
        )
        assert lint(exempted) == ()
        assert [f.rule for f in lint(plain_symbol(elements=exempted.elements))] == [
            "off-drawing-grid"
        ]

    def test_a_warning_is_exempted_like_an_error(self):
        symbol = plain_symbol(
            anchors=(Anchor("a", P(3, 3), Direction.W),),
            lint_allow=(Allow("anchor-off-geometry", "the anchor sits in the air"),),
        )
        assert lint(symbol) == ()

    def test_an_exemption_of_another_rule_is_unused_and_the_finding_stays(self):
        symbol = plain_symbol(
            elements=self.violation.elements, lint_allow=(Allow("degenerate", "wrong rule"),)
        )
        assert [(f.rule, f.location) for f in lint(symbol)] == [
            ("off-drawing-grid", "elements[1]"),
            ("allow-unused", "lint_allow[0]"),
        ]

    def test_an_exemption_with_nothing_to_exempt_is_unused(self):
        symbol = plain_symbol(lint_allow=(Allow("degenerate", "nothing here"),))
        assert [f.rule for f in lint(symbol)] == ["allow-unused"]

    @pytest.mark.parametrize("rule", sorted(RESOLVER_RULES))
    def test_an_exemption_of_a_resolver_rule_adds_no_second_error(self, rule):
        # The resolver never reads `lint_allow`, so the exemption is inert; `lint` does not add an
        # `allow-unused` for a rule it cannot run.
        symbol = plain_symbol(lint_allow=(Allow(rule, "the resolver reports it"),))
        assert lint(symbol) == ()

    def test_an_unknown_rule_is_unknown_and_not_also_unused(self):
        symbol = plain_symbol(lint_allow=(Allow("no-such-rule", "why"),))
        assert [f.rule for f in lint(symbol)] == ["allow-unknown"]

    def test_an_empty_reason_still_exempts_but_is_reported(self):
        symbol = plain_symbol(
            elements=self.violation.elements, lint_allow=(Allow("off-drawing-grid", " "),)
        )
        assert [(f.rule, f.location) for f in lint(symbol)] == [("allow-unknown", "lint_allow[0]")]

    def test_the_exemption_findings_cannot_themselves_be_exempted(self):
        symbol = plain_symbol(lint_allow=(Allow("allow-unused", "x"), Allow("allow-unknown", "y")))
        assert [(f.rule, f.location) for f in lint(symbol)] == [
            ("allow-unused", "lint_allow[0]"),
            ("allow-unused", "lint_allow[1]"),
        ]

    def test_a_rule_that_does_not_apply_to_the_kind_is_known_but_unused(self):
        symbol = plain_symbol(
            lint_allow=(Allow("slot-missing", "an element has no slots to miss"),)
        )
        assert [f.rule for f in lint(symbol)] == ["allow-unused"]

    def test_duplicate_exemptions_are_checked_independently(self):
        symbol = plain_symbol(
            elements=self.violation.elements,
            lint_allow=(Allow("off-drawing-grid", "one"), Allow("off-drawing-grid", "two")),
        )
        assert lint(symbol) == ()


def first_end_points_west(symbol: Symbol) -> tuple[Finding, ...]:
    """A synthetic check that is true only in some orientations."""
    match symbol.elements[0]:
        case Line(end=end) if end.x < 0:
            return (Finding("slot-overlap-body", Severity.ERROR, "west", "elements[0]"),)
    return ()


def always(symbol: Symbol) -> tuple[Finding, ...]:
    return (Finding("through-axis", Severity.ERROR, f"{len(symbol.elements)}", None),)


SYNTHETIC_RULES = {
    "slot-overlap-body": Rule(
        "slot-overlap-body", Severity.ERROR, "Slots", orientation_dependent=True
    ),
    "through-axis": Rule("through-axis", Severity.ERROR, "Connectivity"),
}
SYNTHETIC_CHECKS = {"slot-overlap-body": first_end_points_west, "through-axis": always}


class TestRunChecks:
    def test_an_orientation_dependent_rule_runs_on_each_orientation_and_is_stamped(self):
        found = run_checks(plain_symbol(), SYNTHETIC_RULES, SYNTHETIC_CHECKS)
        west = [f for f in found if f.rule == "slot-overlap-body"]
        assert [f.orientation for f in west] == [Orientation.R90, Orientation.MR90]

    def test_a_rule_that_does_not_depend_on_it_runs_once_unstamped(self):
        found = run_checks(plain_symbol(), SYNTHETIC_RULES, SYNTHETIC_CHECKS)
        assert [f for f in found if f.rule == "through-axis"] == [
            Finding("through-axis", Severity.ERROR, "1", None, None)
        ]

    def test_a_rule_without_a_check_is_skipped(self):
        assert run_checks(plain_symbol(), SYNTHETIC_RULES, {}) == ()

    def test_findings_are_ordered_by_rule_then_orientation_then_location(self):
        shuffled = (
            Finding("allow-unused", Severity.ERROR, "m", "lint_allow[0]"),
            Finding("slot-overlap-body", Severity.ERROR, "m", "elements[0]", Orientation.MR90),
            Finding("slot-overlap-body", Severity.ERROR, "m", "elements[10]", Orientation.R90),
            Finding("slot-overlap-body", Severity.ERROR, "m", "elements[2]", Orientation.R90),
            Finding("slot-overlap-body", Severity.ERROR, "m", "elements[9]", None),
            Finding("through-axis", Severity.ERROR, "m", None),
            Finding("degenerate", Severity.ERROR, "m", "elements[0]"),
            Finding("schema", Severity.ERROR, "m", None),
        )
        assert [(f.rule, f.orientation, f.location) for f in ordered(shuffled)] == [
            ("schema", None, None),
            ("degenerate", None, "elements[0]"),
            ("through-axis", None, None),
            ("slot-overlap-body", None, "elements[9]"),
            ("slot-overlap-body", Orientation.R90, "elements[2]"),
            ("slot-overlap-body", Orientation.R90, "elements[10]"),
            ("slot-overlap-body", Orientation.MR90, "elements[0]"),
            ("allow-unused", None, "lint_allow[0]"),
        ]

    def test_ordering_keeps_generation_order_for_equal_keys(self):
        first = Finding("degenerate", Severity.ERROR, "b", "elements[0]")
        second = Finding("degenerate", Severity.ERROR, "a", "elements[0]")
        assert ordered((first, second)) == (first, second)


finite = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6)
odd = st.sampled_from([0, 0.125, 1, -1, 0.1, math.nan, math.inf, -math.inf, 1e300, 1e-300, -0.0])
grid = st.integers(-8, 8).map(lambda n: n / 2)
numbers = st.one_of(finite, odd, grid)
points = st.builds(Point, numbers, numbers)
grid_points = st.builds(Point, grid, grid)
directions = st.sampled_from(list(Direction))
elements = st.one_of(
    st.builds(Line, points, points),
    st.builds(Line, grid_points, grid_points),
    st.builds(
        Polyline,
        st.lists(points, max_size=4).map(tuple),
        st.booleans(),
        st.sampled_from(list(Fill)),
    ),
    st.builds(Circle, points, numbers, st.sampled_from(list(Fill))),
    st.builds(Arc, points, numbers, numbers, numbers),
    st.builds(Text, st.text(max_size=3), points, numbers),
)
# Few port ids, so that nodes, paths and marking slots often name ports that exist.
port_ids = st.sampled_from(["a", "b", "1.a", "in", "out", "", "ghost"])
ids = st.one_of(port_ids, st.text(alphabet="abAB1._ ", max_size=3))
slot_ids = st.one_of(
    st.sampled_from(
        ["tag", "value", "marking.a", "marking.b", "marking.1.a", "marking.in", "marking.out"]
    ),
    st.sampled_from(["marking.", "marking.ghost", "other"]),
    ids,
)
slots = st.builds(
    Slot,
    slot_ids,
    st.one_of(points, grid_points),
    directions,
    st.tuples(st.one_of(numbers, grid), st.one_of(numbers, grid)),
)
nodes = st.builds(
    Node,
    st.lists(port_ids, max_size=3).map(tuple),
    st.one_of(st.none(), st.sampled_from(list(Potential))),
)
paths = st.builds(SymbolPath, port_ids, port_ids, st.sampled_from(list(PathKind)), st.booleans())
pole_pitches = st.one_of(
    st.none(), st.sampled_from([0, 4, 8, -4, 6, 12]), st.integers(-20, 20), numbers
)
lint_allows = st.lists(
    st.builds(Allow, st.sampled_from([*sorted(RULE_IDS), "x"]), st.text(max_size=2)), max_size=3
).map(tuple)
kinds = st.sampled_from(list(SymbolKind))

garbage_symbols = st.builds(
    plain_symbol,
    kind=kinds,
    elements=st.lists(elements, max_size=5).map(tuple),
    ports=st.lists(st.builds(Port, ids, points, directions), max_size=3).map(tuple),
    nodes=st.lists(nodes, max_size=3).map(tuple),
    paths=st.lists(paths, max_size=3).map(tuple),
    anchors=st.lists(st.builds(Anchor, ids, points, directions), max_size=3).map(tuple),
    slots=st.lists(slots, max_size=3).map(tuple),
    pole_pitch=pole_pitches,
    lint_allow=lint_allows,
)
# Symbols shaped like real ones, so the rules that need exact coincidences get exercised: two ports
# on the through axis (or nearly), paths and nodes over them, and the usual slots.
through_symbols = st.builds(
    plain_symbol,
    kind=kinds,
    elements=st.lists(
        st.one_of(elements, st.builds(Line, grid_points, grid_points)), max_size=4
    ).map(tuple),
    ports=st.builds(
        lambda a, dx, top, bottom: (
            Port("in", Point(dx, -a), top),
            Port("out", Point(0, a), bottom),
        ),
        st.sampled_from([0, 1, 2, 3, 0.5, -1, math.nan, math.inf]),
        st.sampled_from([0, 0, 0, 1, -0.0]),
        st.sampled_from([Direction.N, Direction.N, Direction.E]),
        st.sampled_from([Direction.S, Direction.S, Direction.W]),
    ),
    nodes=st.lists(
        st.builds(
            Node,
            st.lists(st.sampled_from(["in", "out", "ghost"]), max_size=2).map(tuple),
            st.one_of(st.none(), st.sampled_from(list(Potential))),
        ),
        max_size=2,
    ).map(tuple),
    paths=st.lists(
        st.builds(
            SymbolPath,
            st.sampled_from(["in", "out", "ghost"]),
            st.sampled_from(["in", "out", "ghost"]),
            st.sampled_from(list(PathKind)),
            st.booleans(),
        ),
        max_size=3,
    ).map(tuple),
    slots=st.lists(slots, max_size=4).map(tuple),
    pole_pitch=pole_pitches,
    lint_allow=lint_allows,
)
symbols = st.one_of(garbage_symbols, through_symbols)
NEW_RULES = sorted(r.id for r in RULES.values() if r.group in {"Connectivity", "Slots"})


def rules_fired_by(strategy, examples=600):
    """Return the rules whose check fires, in the base orientation, on some generated symbol."""
    fired: set[str] = set()

    @given(strategy)
    @settings(max_examples=examples, deadline=None, database=None, derandomize=True)
    def collect(symbol):
        fired.update(rule_id for rule_id, check in CHECKS.items() if check(symbol))

    collect()
    return fired


class TestTotality:
    @given(symbols)
    @settings(max_examples=300, deadline=None)
    def test_lint_never_raises_and_is_deterministic(self, symbol):
        found = lint(symbol)
        assert found == lint(symbol)
        assert all(isinstance(f, Finding) for f in found)
        assert list(found) == list(ordered(found))

    @given(symbols, st.sampled_from(list(Orientation)))
    @settings(max_examples=300, deadline=None)
    def test_no_rule_of_any_group_raises_on_the_symbol_in_any_orientation(
        self, symbol, orientation
    ):
        turned = orient(symbol, orientation)
        for rule_id, check in CHECKS.items():
            assert all(f.rule == rule_id for f in check(turned))

    def test_the_strategy_reaches_every_connectivity_and_slots_rule(self):
        assert len(NEW_RULES) == 11
        assert set(NEW_RULES) <= rules_fired_by(symbols)

    def test_the_reach_check_can_fail(self):
        assert not set(NEW_RULES) & rules_fired_by(st.just(plain_symbol()), examples=5)


@pytest.fixture(scope="module")
def library():
    return load_library(GUIDE)


class TestGuideExamples:
    @pytest.mark.parametrize("number", ["S00227", "S00230", "S00305", "S00171"])
    def test_the_atomic_examples_and_the_qualifier_trip_none_of_the_rules_of_this_task(
        self, library, number
    ):
        found = lint(library.get(number))
        assert [f for f in found if f.rule in THIS_TASK] == []

    def test_the_connection_point_trips_none_of_them_except_for_exemptions_of_later_rules(
        self, library
    ):
        found = lint(library.get("S00016"))
        assert [f.rule for f in found if f.rule in THIS_TASK - DRIVER_RULES] == []
        assert {f.rule for f in found if f.rule in DRIVER_RULES} <= {"allow-unused"}
