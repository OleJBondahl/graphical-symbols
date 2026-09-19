"""Exemptions-group rules: applying `lint_allow`, `allow-unknown` and `allow-unused`."""

import deal

from graphical_symbols.lint.registry import RULE_IDS, quote, rule_finding
from graphical_symbols.model import Allow, Finding


@deal.pure
def exempt(findings: tuple[Finding, ...], allow: tuple[Allow, ...]) -> tuple[Finding, ...]:
    """Drop the findings of every exempted rule, of both severities, in every orientation."""
    exempted = {entry.rule for entry in allow}
    return tuple(f for f in findings if f.rule not in exempted)


@deal.pure
def allow_unknown(allow: tuple[Allow, ...]) -> tuple[Finding, ...]:
    """Report each exemption that names a rule the guide does not have, or gives no reason.

    Any of the guide's 33 rules is known, also one this toolkit does not implement yet. An entry
    with both faults gets two findings.
    """
    return tuple(
        rule_finding("allow-unknown", message, f"lint_allow[{index}]")
        for index, entry in enumerate(allow)
        for message in (
            *(
                (f"the rule {quote(entry.rule)} does not exist",)
                if entry.rule not in RULE_IDS
                else ()
            ),
            *(("the reason is empty",) if not entry.reason.strip() else ()),
        )
    )


@deal.pure
def allow_unused(allow: tuple[Allow, ...], fired: frozenset[str]) -> tuple[Finding, ...]:
    """Report each exemption of a known rule that did not fire, in any orientation.

    Args:
        allow: The symbol's exemptions; each is judged on its own, also when a rule is named twice.
        fired: The rules that had findings before any exemption was applied.
    """
    return tuple(
        rule_finding(
            "allow-unused",
            f"the rule {quote(entry.rule)} would not have fired, so the exemption is not needed",
            f"lint_allow[{index}]",
        )
        for index, entry in enumerate(allow)
        if entry.rule in RULE_IDS and entry.rule not in fired
    )
