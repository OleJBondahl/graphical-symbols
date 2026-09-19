"""File-group helpers: the id pattern, the registry, and the `metadata` checks."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from graphical_symbols.lint import RULES, Rule
from graphical_symbols.lint.file import is_valid_id, metadata_findings, part_id_findings
from graphical_symbols.lint.registry import quote, rule_finding
from graphical_symbols.model import LibraryConfig, Severity

CONFIG = LibraryConfig("IEC 60617", "IEC 60617 symbols", r"^S\d{5}$")


def file_data(**changes):
    data = {
        "name": "Thing",
        "reference": {"standard": "IEC 60617", "number": "S00001"},
    }
    return data | changes


class TestIsValidId:
    @pytest.mark.parametrize("text", ["in", "a", "pri_in", "x2", "a_b_c9"])
    def test_accepts(self, text):
        assert is_valid_id(text)

    @pytest.mark.parametrize("text", ["", "In", "1in", "_in", "a.b", "a-b", "a b", "in\n", "é"])
    def test_rejects(self, text):
        assert not is_valid_id(text)

    @given(st.text())
    def test_total_and_agrees_with_the_guide_pattern(self, text):
        expected = (
            bool(text)
            and "a" <= text[0] <= "z"
            and all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in text)
        )
        assert is_valid_id(text) is expected


class TestRegistry:
    def test_registers_the_eight_rules_of_the_resolver_with_their_guide_group(self):
        assert {r.id: r.group for r in RULES.values()} == {
            "schema": "File",
            "metadata": "File",
            "id-format": "File",
            "part-unknown": "Composition",
            "part-cycle": "Composition",
            "part-anchor": "Composition",
            "part-port-unexported": "Composition",
            "export-unknown": "Composition",
        }
        assert all(r.severity is Severity.ERROR for r in RULES.values())

    def test_keys_are_rule_ids(self):
        assert all(key == rule.id for key, rule in RULES.items())
        assert isinstance(RULES["schema"], Rule)

    def test_rule_finding_takes_severity_from_the_registry(self):
        finding = rule_finding("part-anchor", "m", "/parts/0")
        assert (finding.rule, finding.severity, finding.message, finding.location) == (
            "part-anchor",
            Severity.ERROR,
            "m",
            "/parts/0",
        )
        assert rule_finding("schema", "m").location is None

    def test_quote_caps_long_text(self):
        assert quote("abc") == "'abc'"
        assert quote("x" * 100) == repr("x" * 60 + "...")


class TestMetadataFindings:
    def test_clean(self):
        assert metadata_findings("S00001", file_data(), CONFIG) == ()

    def test_empty_name(self):
        (found,) = metadata_findings("S00001", file_data(name=""), CONFIG)
        assert (found.rule, found.location) == ("metadata", "/name")

    def test_blank_name(self):
        (found,) = metadata_findings("S00001", file_data(name="  "), CONFIG)
        assert (found.rule, found.location) == ("metadata", "/name")

    def test_other_standard(self):
        data = file_data(reference={"standard": "ISO 14617", "number": "S00001"})
        (found,) = metadata_findings("S00001", data, CONFIG)
        assert (found.rule, found.location) == ("metadata", "/reference/standard")

    def test_number_not_matching_the_pattern(self):
        data = file_data(reference={"standard": "IEC 60617", "number": "X1"})
        (found,) = metadata_findings("X1", data, CONFIG)
        assert (found.rule, found.location) == ("metadata", "/reference/number")
        assert "does not match" in found.message

    def test_number_differing_from_the_stem(self):
        (found,) = metadata_findings("S00002", file_data(), CONFIG)
        assert (found.rule, found.location) == ("metadata", "/reference/number")
        assert "differs from the file name" in found.message

    def test_a_pattern_that_does_not_compile_matches_nothing(self):
        config = LibraryConfig("IEC 60617", "t", "(")
        (found,) = metadata_findings("S00001", file_data(), config)
        assert "does not match" in found.message

    def test_all_four_problems_are_reported_together(self):
        data = file_data(name="", reference={"standard": "X", "number": "y"})
        assert [f.location for f in metadata_findings("z", data, CONFIG)] == [
            "/name",
            "/reference/standard",
            "/reference/number",
            "/reference/number",
        ]


class TestPartIdFindings:
    def test_clean_and_no_parts(self):
        assert part_id_findings({}) == ()
        assert part_id_findings({"parts": [{"as": "a", "use": "S1"}]}) == ()

    def test_bad_ids_by_position(self):
        data = {"parts": [{"as": "ok", "use": "S1"}, {"as": "Bad", "use": "S1"}, {"as": "a.b"}]}
        assert [(f.rule, f.location) for f in part_id_findings(data)] == [
            ("id-format", "/parts/1/as"),
            ("id-format", "/parts/2/as"),
        ]
