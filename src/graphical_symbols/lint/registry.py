"""The rule registry: the id, severity and guide group of every rule the toolkit reports.

Adding a lint rule takes one function that returns the rule's findings, one `Rule` row in `RULES`
below and one entry in `CHECKS` in `lint/__init__.py`. A rule that depends on the orientation is
marked `orientation_dependent`; the driver then calls it once per orientation.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

import deal

from graphical_symbols.model import Finding, Severity, Symbol

_QUOTE_LIMIT = 60

# The 33 rule ids in the order of the guide's section 9 table: the order findings are sorted in.
GUIDE_ORDER: tuple[str, ...] = (
    "schema",
    "metadata",
    "id-format",
    "off-drawing-grid",
    "degenerate",
    "text-too-large",
    "port-duplicate-id",
    "port-off-wiring-grid",
    "port-off-geometry",
    "port-on-body-edge",
    "port-lane-clear",
    "port-spacing",
    "port-position-shared",
    "node-invalid",
    "path-invalid",
    "through-count",
    "through-axis",
    "through-missing",
    "port-isolated",
    "slot-missing",
    "slot-unknown-port",
    "slot-overlap-body",
    "slot-overlap-slot",
    "pitch-overflow",
    "anchor-duplicate-id",
    "anchor-off-geometry",
    "part-unknown",
    "part-cycle",
    "part-anchor",
    "part-port-unexported",
    "export-unknown",
    "allow-unknown",
    "allow-unused",
)
RULE_IDS: frozenset[str] = frozenset(GUIDE_ORDER)
GUIDE_INDEX: dict[str, int] = {rule_id: index for index, rule_id in enumerate(GUIDE_ORDER)}

Check = Callable[[Symbol], tuple[Finding, ...]]


@dataclass(frozen=True, slots=True)
class Rule:
    """A lint rule as the guide's section 9 table lists it.

    `orientation_dependent` rules are checked on the symbol in each of the 8 orientations; every
    other rule is checked once on the symbol as given.
    """

    id: str
    severity: Severity
    group: str
    orientation_dependent: bool = False


# All 33 rules of the guide's section 9 table, with their group and severity.
RULES: dict[str, Rule] = {
    rule.id: rule
    for rule in (
        Rule("schema", Severity.ERROR, "File"),
        Rule("metadata", Severity.ERROR, "File"),
        Rule("id-format", Severity.ERROR, "File"),
        Rule("off-drawing-grid", Severity.ERROR, "Geometry"),
        Rule("degenerate", Severity.ERROR, "Geometry"),
        Rule("text-too-large", Severity.ERROR, "Geometry"),
        Rule("port-duplicate-id", Severity.ERROR, "Ports"),
        Rule("port-off-wiring-grid", Severity.ERROR, "Ports"),
        Rule("port-off-geometry", Severity.ERROR, "Ports"),
        Rule("port-on-body-edge", Severity.ERROR, "Ports", orientation_dependent=True),
        Rule("port-lane-clear", Severity.ERROR, "Ports", orientation_dependent=True),
        Rule("port-spacing", Severity.ERROR, "Ports"),
        Rule("port-position-shared", Severity.ERROR, "Ports"),
        Rule("node-invalid", Severity.ERROR, "Connectivity"),
        Rule("path-invalid", Severity.ERROR, "Connectivity"),
        Rule("through-count", Severity.ERROR, "Connectivity"),
        Rule("through-axis", Severity.ERROR, "Connectivity"),
        Rule("through-missing", Severity.WARNING, "Connectivity"),
        Rule("port-isolated", Severity.WARNING, "Connectivity"),
        Rule("slot-missing", Severity.ERROR, "Slots"),
        Rule("slot-unknown-port", Severity.ERROR, "Slots"),
        Rule("slot-overlap-body", Severity.ERROR, "Slots", orientation_dependent=True),
        Rule("slot-overlap-slot", Severity.ERROR, "Slots", orientation_dependent=True),
        Rule("pitch-overflow", Severity.ERROR, "Slots"),
        Rule("anchor-duplicate-id", Severity.ERROR, "Anchors"),
        Rule("anchor-off-geometry", Severity.WARNING, "Anchors"),
        Rule("part-unknown", Severity.ERROR, "Composition"),
        Rule("part-cycle", Severity.ERROR, "Composition"),
        Rule("part-anchor", Severity.ERROR, "Composition"),
        Rule("part-port-unexported", Severity.ERROR, "Composition"),
        Rule("export-unknown", Severity.ERROR, "Composition"),
        Rule("allow-unknown", Severity.ERROR, "Exemptions"),
        Rule("allow-unused", Severity.ERROR, "Exemptions"),
    )
}


@deal.pure
def rule_finding(rule: str, message: str, location: str | None = None) -> Finding:
    """Make a finding of a registered rule, with the severity the registry gives it."""
    return Finding(rule, RULES[rule].severity, message, location)


@deal.pure
def quote(text: str) -> str:
    """Quote text that comes from a file for a message, capped so the message stays readable."""
    return repr(text if len(text) <= _QUOTE_LIMIT else text[:_QUOTE_LIMIT] + "...")


@deal.pure
def natural_key(text: str) -> str:
    """Return a sort key that puts numbers in natural order: `elements[2]` before `[10]`."""
    return re.sub(r"\d+", lambda m: f"{len(m.group()):04d}{m.group()}", text)
