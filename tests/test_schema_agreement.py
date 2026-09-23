"""The JSON Schema and the Python validator accept and reject the same files (fixture-driven)."""

import json
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from damage import HUGE_INTEGERS, ODD_VALUES, damage
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator

from graphical_symbols.load import symbol_from_data, validate

TESTS = Path(__file__).resolve().parent
SCHEMA_PATH = TESTS.parent / "schema" / "symbol.schema.json"
FIXTURES = TESTS / "fixtures"
VALID = sorted((FIXTURES / "schema" / "valid").glob("*.toml"))
INVALID = sorted((FIXTURES / "schema" / "invalid").glob("*.toml"))
GUIDE = sorted((FIXTURES / "guide" / "symbols").glob("*.toml"))
VIOLATES = "# violates: "

SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
JSON_SCHEMA = Draft202012Validator(SCHEMA)


def load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def schema_accepts(data: object) -> bool:
    return JSON_SCHEMA.is_valid(data)


def python_accepts(data: object) -> bool:
    return not validate(data)


def disagreements(
    paths: list[Path], first: Callable[[object], bool], second: Callable[[object], bool]
) -> list[str]:
    """Name every fixture the two validators judge differently."""
    return [path.stem for path in paths if first(load(path)) != second(load(path))]


def test_the_schema_is_a_valid_draft_2020_12_schema():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_the_fixture_set_is_broad_enough():
    assert len(VALID) >= 10
    assert len(INVALID) >= 15
    assert len(GUIDE) == 6


@pytest.mark.parametrize("path", [*VALID, *GUIDE], ids=lambda p: p.stem)
def test_both_validators_accept_a_valid_file(path):
    data = load(path)
    assert validate(data) == ()
    assert schema_accepts(data)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_both_validators_reject_an_invalid_file(path):
    data = load(path)
    assert not schema_accepts(data)
    assert validate(data)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_an_invalid_file_is_rejected_for_the_reason_it_declares(path):
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith(VIOLATES)
    expected = first_line.removeprefix(VIOLATES)
    assert expected in {finding.location or "/" for finding in validate(load(path))}


def test_the_validators_agree_on_every_fixture():
    everything = [*VALID, *INVALID, *GUIDE]
    assert disagreements(everything, python_accepts, schema_accepts) == []


def test_the_comparison_can_fail():
    def accept_everything(_data: object) -> bool:
        return True

    broken = FIXTURES / "schema" / "invalid" / "schema_wrong_number.toml"
    assert disagreements([broken], accept_everything, python_accepts) == ["schema_wrong_number"]
    assert disagreements([broken], accept_everything, schema_accepts) == ["schema_wrong_number"]
    assert disagreements(VALID, accept_everything, python_accepts) == []


def test_the_schema_leaves_lint_territory_to_the_linter():
    assert schema_accepts(
        load(FIXTURES / "schema" / "valid" / "lint_matters_are_not_schema_matters.toml")
    )


# A differential test on top of the fixtures: damage a valid file at a random place and require
# the two validators to agree on the result, whatever it is.

BASES = [load(path) for path in [*VALID, *GUIDE]]
DAMAGE = {
    "base": st.sampled_from(BASES),
    "pick": st.integers(min_value=0),
    "action": st.sampled_from(["replace", "delete", "add"]),
    "key": st.sampled_from(
        ["extra", "line", "r", "weight", "at", "height", "elements", "slots", "port"]
    ),
}


@settings(max_examples=400, deadline=None)
@given(value=ODD_VALUES, **DAMAGE)
def test_the_validators_agree_on_damaged_files(base, pick, action, value, key):
    data = damage(base, pick, action, value, key)
    assert python_accepts(data) == schema_accepts(data), data


@settings(max_examples=400, deadline=None)
@given(value=ODD_VALUES | HUGE_INTEGERS, **DAMAGE)
def test_reading_never_raises_on_damaged_files(base, pick, action, value, key):
    data = damage(base, pick, action, value, key)
    if not validate(data):
        symbol_from_data(data)
