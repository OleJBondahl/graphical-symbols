"""The registry agrees with the guide's section 9 table, the authoritative list of the 33 rules."""

import re
from pathlib import Path

from graphical_symbols.geometry import Orientation
from graphical_symbols.lint import RULES
from graphical_symbols.lint.registry import (
    GUIDE_INDEX,
    GUIDE_ORDER,
    RULE_IDS,
    finding_key,
    natural_key,
)
from graphical_symbols.model import Finding, Severity

GUIDE = Path(__file__).resolve().parent.parent / "docs" / "SYMBOL_INTERFACE.html"
_ROW = re.compile(
    r"<tr>(?:<td rowspan=\"\d+\">(?P<group>[^<]+)</td>)?<td><code>(?P<rule>[a-z-]+)</code>"
    r"(?P<warning> \(warning\))?</td>"
)


def guide_rules(html: str) -> list[tuple[str, str, Severity]]:
    """Read the rule table of section 9: (rule id, group, severity) in table order."""
    section = html.split('<h2 id="s9">', 1)[1].split('<h2 id="s10">', 1)[0]
    rules = []
    group = ""
    for match in _ROW.finditer(section):
        group = match["group"] or group
        severity = Severity.WARNING if match["warning"] else Severity.ERROR
        rules.append((match["rule"], group, severity))
    return rules


def problems(html: str) -> list[str]:
    """Say where the registry differs from the guide's table."""
    table = guide_rules(html)
    found = []
    if [rule for rule, _, _ in table] != list(GUIDE_ORDER):
        found.append("GUIDE_ORDER differs from the table")
    for rule, group, severity in table:
        if rule in RULES and (RULES[rule].group, RULES[rule].severity) != (group, severity):
            found.append(f"{rule} is registered with another group or severity")
    return found


def test_the_guide_table_has_33_rules():
    assert len(guide_rules(GUIDE.read_text(encoding="utf-8"))) == 33


def test_the_registry_agrees_with_the_guide():
    assert problems(GUIDE.read_text(encoding="utf-8")) == []


def test_the_comparison_can_fail():
    html = GUIDE.read_text(encoding="utf-8")
    swapped = html.replace("<code>degenerate</code>", "<code>XX</code>", 1).replace(
        "<code>off-drawing-grid</code>", "<code>degenerate</code>", 1
    )
    assert "GUIDE_ORDER differs from the table" in problems(swapped)
    regrouped = html.replace('<td rowspan="2">Anchors</td>', '<td rowspan="2">Elsewhere</td>', 1)
    assert "anchor-duplicate-id is registered with another group or severity" in problems(regrouped)
    calmer = html.replace(
        "<code>anchor-off-geometry</code> (warning)", "<code>anchor-off-geometry</code>"
    )
    assert calmer != html
    assert "anchor-off-geometry is registered with another group or severity" in problems(calmer)


def test_rule_ids_and_the_index_derive_from_the_table_order():
    assert frozenset(GUIDE_ORDER) == RULE_IDS
    assert len(GUIDE_ORDER) == len(RULE_IDS) == 33
    assert [GUIDE_INDEX[rule] for rule in GUIDE_ORDER] == list(range(33))


def test_every_registered_rule_is_a_rule_of_the_guide():
    assert set(RULES) <= RULE_IDS


def test_natural_key_orders_numbers_as_numbers():
    locations = ["elements[10]", "elements[2]", "anchors[1]", "elements[1]"]
    assert sorted(locations, key=natural_key) == [
        "anchors[1]",
        "elements[1]",
        "elements[2]",
        "elements[10]",
    ]


def test_finding_key_orders_by_rule_then_orientation_then_natural_location():
    def at(rule, location=None, orientation=None):
        return Finding(rule, Severity.ERROR, "m", location, orientation)

    shuffled = [
        at("id-format", "/parts/10/as"),
        at("id-format", "/parts/2/as"),
        at("slot-overlap-body", "elements[0]", Orientation.R90),
        at("slot-overlap-body", "elements[0]"),
        at("metadata", "/name"),
        at("schema"),
    ]
    assert [(f.rule, f.orientation, f.location) for f in sorted(shuffled, key=finding_key)] == [
        ("schema", None, None),
        ("metadata", None, "/name"),
        ("id-format", None, "/parts/2/as"),
        ("id-format", None, "/parts/10/as"),
        ("slot-overlap-body", None, "elements[0]"),
        ("slot-overlap-body", Orientation.R90, "elements[0]"),
    ]


def test_finding_key_puts_an_unregistered_rule_after_all_registered_ones_by_id():
    def at(rule):
        return Finding(rule, Severity.ERROR, "m")

    shuffled = [at("zzz"), at("allow-unused"), at("aaa"), at("schema")]
    assert [f.rule for f in sorted(shuffled, key=finding_key)] == [
        "schema",
        "allow-unused",
        "aaa",
        "zzz",
    ]
