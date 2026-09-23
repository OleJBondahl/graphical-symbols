"""The toolkit reports exactly the guide's 34 rules, each with its group, severity and fixture.

The table below is written out by hand from the guide's section 9 on purpose: it is the check on
the registry, so it must not be derived from it.
"""

import pytest
from fixture_pipeline import BROKEN, run_fixture
from test_lint_registry import GUIDE, guide_rules

from graphical_symbols.lint import CHECKS, RULE_IDS, RULES
from graphical_symbols.model import Severity

E, W = Severity.ERROR, Severity.WARNING
THE_RULES = {
    "schema": ("File", E),
    "metadata": ("File", E),
    "id-format": ("File", E),
    "off-drawing-grid": ("Geometry", E),
    "degenerate": ("Geometry", E),
    "text-too-large": ("Geometry", E),
    "port-duplicate-id": ("Ports", E),
    "port-off-wiring-grid": ("Ports", E),
    "port-off-geometry": ("Ports", E),
    "port-on-body-edge": ("Ports", E),
    "port-lane-clear": ("Ports", E),
    "port-spacing": ("Ports", E),
    "port-position-shared": ("Ports", E),
    "lead-off-port": ("Ports", E),
    "node-invalid": ("Connectivity", E),
    "path-invalid": ("Connectivity", E),
    "through-count": ("Connectivity", E),
    "through-axis": ("Connectivity", E),
    "through-missing": ("Connectivity", W),
    "port-isolated": ("Connectivity", W),
    "slot-missing": ("Slots", E),
    "slot-unknown-port": ("Slots", E),
    "slot-overlap-body": ("Slots", E),
    "slot-overlap-slot": ("Slots", E),
    "pitch-overflow": ("Slots", E),
    "anchor-duplicate-id": ("Anchors", E),
    "anchor-off-geometry": ("Anchors", W),
    "part-unknown": ("Composition", E),
    "part-cycle": ("Composition", E),
    "part-anchor": ("Composition", E),
    "part-port-unexported": ("Composition", E),
    "export-unknown": ("Composition", E),
    "allow-unknown": ("Exemptions", E),
    "allow-unused": ("Exemptions", E),
}
# The rules the resolver reports while it flattens, and the two derived from `lint_allow`.
RESOLVER_RULES = {
    "schema",
    "metadata",
    "part-unknown",
    "part-cycle",
    "part-anchor",
    "part-port-unexported",
    "export-unknown",
}
EXEMPTION_RULES = {"allow-unknown", "allow-unused"}


def test_the_hand_written_table_has_34_rules():
    assert len(THE_RULES) == 34


def test_the_registry_holds_exactly_the_34_rules_of_the_guide():
    assert set(RULES) == set(RULE_IDS) == set(THE_RULES)
    assert len(RULES) == 34


def test_the_hand_written_table_is_the_guides_table():
    table = [(rule, group, severity) for rule, (group, severity) in THE_RULES.items()]
    assert table == guide_rules(GUIDE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("rule_id", sorted(THE_RULES))
def test_every_rule_has_its_guide_group_and_severity(rule_id):
    assert (RULES[rule_id].group, RULES[rule_id].severity) == THE_RULES[rule_id]


def test_exactly_three_rules_are_warnings():
    warnings = {rule_id for rule_id, (_, severity) in THE_RULES.items() if severity is W}
    assert warnings == {"through-missing", "port-isolated", "anchor-off-geometry"}
    assert {r.id for r in RULES.values() if r.severity is W} == warnings


def test_the_checks_the_resolver_and_the_exemptions_produce_every_rule_once_between_them():
    assert set(CHECKS).isdisjoint(RESOLVER_RULES | EXEMPTION_RULES)
    assert RESOLVER_RULES.isdisjoint(EXEMPTION_RULES)
    assert set(CHECKS) | RESOLVER_RULES | EXEMPTION_RULES == set(THE_RULES)


def test_only_the_body_edge_lane_and_slot_overlap_rules_depend_on_the_orientation():
    assert {r.id for r in RULES.values() if r.orientation_dependent} == {
        "port-on-body-edge",
        "port-lane-clear",
        "slot-overlap-body",
        "slot-overlap-slot",
    }


@pytest.mark.parametrize("rule_id", sorted(THE_RULES))
def test_every_rule_has_a_broken_fixture_that_makes_it_fire(rule_id):
    directory = BROKEN / rule_id / "symbols"
    assert directory.is_dir()
    assert list(directory.glob("S00001.toml"))
    assert any(f.rule == rule_id for f in run_fixture(rule_id))


def test_no_fixture_directory_is_left_over_for_a_rule_that_does_not_exist():
    assert {p.name for p in BROKEN.iterdir() if p.is_dir()} == set(THE_RULES)
