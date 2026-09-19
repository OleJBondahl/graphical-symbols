"""Every registered rule has a deliberately broken fixture that makes it fire."""

import pytest
from fixture_pipeline import BROKEN, run_fixture

from graphical_symbols.lint import RULES


def problem_with_fixture(rule_id: str, root=BROKEN) -> str | None:
    """Say what is wrong with a rule's fixture: no directory, or the rule does not fire on it."""
    if not (root / rule_id / "symbols").is_dir():
        return f"rule {rule_id!r} has no fixture directory"
    if not any(f.rule == rule_id for f in run_fixture(rule_id, root)):
        return f"rule {rule_id!r} does not fire on its fixture"
    return None


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_the_rule_fires_on_its_fixture(rule_id):
    assert problem_with_fixture(rule_id) is None


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_the_fixture_of_the_resolver_rules_fires_nothing_else(rule_id):
    assert {f.rule for f in run_fixture(rule_id)} == {rule_id}


def test_a_registry_entry_without_a_fixture_directory_is_reported(tmp_path):
    assert problem_with_fixture("no-such-rule", tmp_path) == (
        "rule 'no-such-rule' has no fixture directory"
    )


def test_a_fixture_on_which_the_rule_does_not_fire_is_reported(tmp_path):
    (tmp_path / "library.toml").write_text(
        (BROKEN / "library.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    good = tmp_path / "part-unknown" / "symbols"
    good.mkdir(parents=True)
    (good / "S00001.toml").write_text(
        (BROKEN / "metadata" / "symbols" / "S00001.toml")
        .read_text(encoding="utf-8")
        .replace('name = ""', 'name = "A clean file"'),
        encoding="utf-8",
    )
    assert problem_with_fixture("part-unknown", tmp_path) == (
        "rule 'part-unknown' does not fire on its fixture"
    )


def test_a_fixture_may_bring_its_own_library_config(tmp_path):
    directory = tmp_path / "metadata" / "symbols"
    directory.mkdir(parents=True)
    (tmp_path / "metadata" / "library.toml").write_text(
        'standard = "ISO 14617"\ntitle = "t"\nnumber_pattern = ".*"\n', encoding="utf-8"
    )
    (directory / "S00001.toml").write_text(
        (BROKEN / "metadata" / "symbols" / "S00001.toml")
        .read_text(encoding="utf-8")
        .replace('name = ""', 'name = "Named"'),
        encoding="utf-8",
    )
    assert [f.location for f in run_fixture("metadata", tmp_path)] == ["/reference/standard"]
