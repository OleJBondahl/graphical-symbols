"""Every registered rule has a deliberately broken fixture that makes it fire."""

import pytest
from fixture_pipeline import BROKEN, TOLERATED_EXTRA, run_fixture, run_fixture_by_file

from symdef.lint import CHECKS, RULES


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
def test_the_fixture_fires_its_own_rule_and_nothing_else_but_what_it_tolerates(rule_id):
    fired = {f.rule for f in run_fixture(rule_id)}
    assert fired - TOLERATED_EXTRA.get(rule_id, frozenset()) == {rule_id}


def case_files(rule_id):
    """Return the stems of a fixture's cases: `S00001` to `S00009`; `S0001x` are helper files."""
    return sorted(p.stem for p in (BROKEN / rule_id / "symbols").glob("S0000[1-9].toml"))


@pytest.mark.parametrize(
    ("rule_id", "stem"),
    [(rule_id, stem) for rule_id in sorted(RULES) for stem in case_files(rule_id)],
)
def test_every_case_file_of_a_fixture_fires_the_rule_on_its_own(rule_id, stem):
    assert rule_id in {f.rule for f in run_fixture_by_file(rule_id)[stem]}


def test_a_fixture_has_case_files():
    assert all(case_files(rule_id) for rule_id in RULES)


def test_the_tolerated_extras_name_registered_rules_only():
    assert set(TOLERATED_EXTRA) <= set(RULES)
    assert all(extra <= set(RULES) for extra in TOLERATED_EXTRA.values())


# The case file whose violation a `lint_allow` entry can remove: `id-format`'s first case is a bad
# part id, which the resolver reports and no exemption reaches.
EXEMPTABLE_CASE = {"id-format": "S00002"}


def exempted_fixture(rule_id, root):
    """Copy the fixture's case file to `root` with a `lint_allow` entry for every rule it fires."""
    stem = EXEMPTABLE_CASE.get(rule_id, "S00001")
    rules = sorted({rule_id, *TOLERATED_EXTRA.get(rule_id, ())})
    entries = "".join(f'  {{ rule = "{r}", reason = "a test" }},\n' for r in rules)
    source = (BROKEN / rule_id / "symbols" / f"{stem}.toml").read_text(encoding="utf-8")
    head, reference, rest = source.partition("\nreference = ")
    reference_line, _, rest = rest.partition("\n")
    (root / rule_id / "symbols").mkdir(parents=True)
    (root / "library.toml").write_text(
        (BROKEN / "library.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    exempted = f"{head}{reference}{reference_line}\nlint_allow = [\n{entries}]\n{rest}"
    (root / rule_id / "symbols" / f"{stem}.toml").write_text(exempted, encoding="utf-8")
    return stem


@pytest.mark.parametrize("rule_id", sorted(CHECKS))
def test_a_matching_lint_allow_lints_the_fixture_clean(rule_id, tmp_path):
    exempted_fixture(rule_id, tmp_path)
    assert run_fixture(rule_id, tmp_path) == ()


@pytest.mark.parametrize("rule_id", sorted(CHECKS))
def test_the_fixture_without_the_lint_allow_fires_again(rule_id, tmp_path):
    stem = exempted_fixture(rule_id, tmp_path)
    (tmp_path / rule_id / "symbols" / f"{stem}.toml").write_bytes(
        (BROKEN / rule_id / "symbols" / f"{stem}.toml").read_bytes()
    )
    assert rule_id in {f.rule for f in run_fixture(rule_id, tmp_path)}


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


def test_run_fixture_reports_the_resolvers_and_the_linters_findings_per_file(tmp_path):
    (tmp_path / "library.toml").write_text(
        (BROKEN / "library.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    directory = tmp_path / "mixed" / "symbols"
    directory.mkdir(parents=True)
    (directory / "S00001.toml").write_bytes(
        (BROKEN / "part-unknown" / "symbols" / "S00001.toml").read_bytes()
    )
    (directory / "S00002.toml").write_bytes(
        (BROKEN / "off-drawing-grid" / "symbols" / "S00001.toml")
        .read_bytes()
        .replace(b"S00001", b"S00002")
    )
    per_file = run_fixture_by_file("mixed", tmp_path)
    assert {stem: [f.rule for f in found] for stem, found in per_file.items()} == {
        "S00001": ["part-unknown"],
        "S00002": ["off-drawing-grid"],
    }
    assert [f.rule for f in run_fixture("mixed", tmp_path)] == ["part-unknown", "off-drawing-grid"]


def test_the_strict_default_can_fail(tmp_path):
    """A fixture that also breaks another rule is caught unless that rule is tolerated."""
    (tmp_path / "library.toml").write_text(
        (BROKEN / "library.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    directory = tmp_path / "text-too-large" / "symbols"
    directory.mkdir(parents=True)
    source = (BROKEN / "text-too-large" / "symbols" / "S00001.toml").read_text(encoding="utf-8")
    (directory / "S00001.toml").write_text(source.replace("[0, 0]", "[0.1, 0]"), encoding="utf-8")
    assert {f.rule for f in run_fixture("text-too-large", tmp_path)} == {
        "text-too-large",
        "off-drawing-grid",
    }
