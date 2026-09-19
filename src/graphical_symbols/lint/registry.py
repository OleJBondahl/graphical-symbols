"""The rule registry: the id, severity and guide group of every rule the toolkit reports."""

from dataclasses import dataclass

import deal

from graphical_symbols.model import Finding, Severity

_QUOTE_LIMIT = 60


@dataclass(frozen=True, slots=True)
class Rule:
    """A lint rule as the guide's section 9 table lists it."""

    id: str
    severity: Severity
    group: str


RULES: dict[str, Rule] = {
    rule.id: rule
    for rule in (
        Rule("schema", Severity.ERROR, "File"),
        Rule("metadata", Severity.ERROR, "File"),
        Rule("id-format", Severity.ERROR, "File"),
        Rule("part-unknown", Severity.ERROR, "Composition"),
        Rule("part-cycle", Severity.ERROR, "Composition"),
        Rule("part-anchor", Severity.ERROR, "Composition"),
        Rule("part-port-unexported", Severity.ERROR, "Composition"),
        Rule("export-unknown", Severity.ERROR, "Composition"),
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
