"""Exemptions group: applying `lint_allow`, `allow-unknown` and `allow-unused`."""

import pytest

from symdef.lint.exemptions import allow_unknown, allow_unused, exempt
from symdef.lint.registry import RESOLVER_RULES
from symdef.model import Allow, Finding, Severity

# The rules only the resolver reports: `lint` never runs them, so `lint_allow` cannot cover them.
RESOLVER_ONLY = [
    "schema",
    "metadata",
    "part-unknown",
    "part-cycle",
    "part-anchor",
    "part-port-unexported",
    "export-unknown",
]


def found(rule, severity=Severity.ERROR, location=None):
    return Finding(rule, severity, "m", location)


class TestExempt:
    def test_no_exemptions_keep_everything(self):
        findings = (found("degenerate"), found("text-too-large"))
        assert exempt(findings, ()) == findings

    def test_an_exempted_rule_loses_its_findings_of_both_severities(self):
        findings = (
            found("degenerate"),
            found("degenerate", Severity.WARNING),
            found("anchor-off-geometry", Severity.WARNING),
            found("text-too-large"),
        )
        allow = (Allow("degenerate", "why"), Allow("anchor-off-geometry", "why"))
        assert exempt(findings, allow) == (found("text-too-large"),)

    def test_an_exemption_covers_every_orientation_and_location(self):
        findings = (found("degenerate", location="elements[0]"), found("degenerate"))
        assert exempt(findings, (Allow("degenerate", "why"),)) == ()

    def test_an_exemption_of_another_rule_removes_nothing(self):
        findings = (found("degenerate"),)
        assert exempt(findings, (Allow("text-too-large", "why"),)) == findings


class TestAllowUnknown:
    def test_known_rules_with_reasons_are_clean(self):
        allow = (Allow("degenerate", "because"), Allow("slot-missing", "any reason"))
        assert allow_unknown(allow) == ()

    def test_an_unknown_rule_fires_at_the_entry(self):
        (finding,) = allow_unknown((Allow("degenerate", "ok"), Allow("no-such-rule", "why")))
        assert (finding.rule, finding.severity, finding.location) == (
            "allow-unknown",
            Severity.ERROR,
            "lint_allow[1]",
        )
        assert "'no-such-rule'" in finding.message

    def test_an_empty_or_blank_reason_fires_at_the_entry(self):
        found_ = allow_unknown((Allow("degenerate", ""), Allow("degenerate", " \t\n")))
        assert [(f.rule, f.location) for f in found_] == [
            ("allow-unknown", "lint_allow[0]"),
            ("allow-unknown", "lint_allow[1]"),
        ]
        assert "reason" in found_[0].message

    def test_an_unknown_rule_and_an_empty_reason_are_two_findings(self):
        assert len(allow_unknown((Allow("no-such-rule", ""),))) == 2

    def test_a_rule_of_the_guide_is_known_even_if_the_toolkit_lacks_it_so_far(self):
        assert allow_unknown((Allow("pitch-overflow", "r"), Allow("schema", "r"))) == ()


class TestAllowUnused:
    def test_an_exemption_of_a_rule_that_fired_is_used(self):
        assert allow_unused((Allow("degenerate", "why"),), frozenset({"degenerate"})) == ()

    def test_an_exemption_of_a_rule_that_did_not_fire_fires_at_the_entry(self):
        allow = (Allow("degenerate", "why"), Allow("text-too-large", "why"))
        (finding,) = allow_unused(allow, frozenset({"degenerate"}))
        assert (finding.rule, finding.severity, finding.location) == (
            "allow-unused",
            Severity.ERROR,
            "lint_allow[1]",
        )
        assert "'text-too-large'" in finding.message

    def test_an_unknown_rule_is_allow_unknowns_business_not_this(self):
        assert allow_unused((Allow("no-such-rule", "why"),), frozenset()) == ()

    def test_duplicate_entries_are_each_checked_on_their_own(self):
        allow = (Allow("degenerate", "one"), Allow("degenerate", "two"))
        assert allow_unused(allow, frozenset({"degenerate"})) == ()
        assert [f.location for f in allow_unused(allow, frozenset())] == [
            "lint_allow[0]",
            "lint_allow[1]",
        ]

    def test_an_empty_reason_still_counts_as_use(self):
        assert allow_unused((Allow("degenerate", ""),), frozenset({"degenerate"})) == ()

    @pytest.mark.parametrize("rule", RESOLVER_ONLY)
    def test_a_rule_only_the_resolver_reports_is_inert_not_unused(self, rule):
        assert allow_unused((Allow(rule, "why"),), frozenset()) == ()

    def test_the_resolver_only_rules_are_registered_as_such(self):
        assert frozenset(RESOLVER_ONLY) == RESOLVER_RULES

    def test_id_format_is_also_a_lint_rule_so_it_is_judged_like_any_other(self):
        assert [f.location for f in allow_unused((Allow("id-format", "why"),), frozenset())] == [
            "lint_allow[0]"
        ]
