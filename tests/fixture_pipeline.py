"""Run a broken fixture through the toolkit's pipeline and return every finding it produces.

Imported by the tests as `from fixture_pipeline import run_fixture`: pytest puts this directory
on `sys.path` because `tests/` has no `__init__.py`.
"""

import tomllib
from pathlib import Path

from graphical_symbols.lint import lint
from graphical_symbols.load import parse_config
from graphical_symbols.model import Finding
from graphical_symbols.resolve import resolve_library

BROKEN = Path(__file__).resolve().parent / "fixtures" / "broken"

# The rules a fixture may fire besides its own; every other fixture must fire its own rule and
# nothing else. Add an entry only when the broken input cannot be built without also breaking
# another rule, and say why.
TOLERATED_EXTRA: dict[str, frozenset[str]] = {}


def run_fixture_by_file(rule_id: str, root: Path = BROKEN) -> dict[str, tuple[Finding, ...]]:
    """Load `<root>/<rule_id>/`, resolve and lint it, and return the findings per file.

    The library config is the fixture's own `library.toml` if it has one, else the one in `<root>`.
    Per file, the resolver's findings come first, then the linter's for the flattened symbol. The
    key is the file stem, or the symbol's number when `metadata` moved it.

    Raises:
        FileNotFoundError: If the fixture directory or its config does not exist.
    """
    directory = root / rule_id
    if not (directory / "symbols").is_dir():
        msg = f"no fixture directory {directory / 'symbols'}"
        raise FileNotFoundError(msg)
    config_path = directory / "library.toml"
    if not config_path.exists():
        config_path = root / "library.toml"
    config, config_findings = parse_config(config_path.read_text(encoding="utf-8"))
    assert config is not None, config_findings
    sources = {
        path.stem: tomllib.loads(path.read_text(encoding="utf-8"))
        for path in sorted((directory / "symbols").glob("*.toml"))
    }
    resolution = resolve_library(config, sources)
    return {
        stem: (*resolution.findings.get(stem, ()), *lint(resolution.symbols[stem]))
        if stem in resolution.symbols
        else resolution.findings[stem]
        for stem in sorted(set(resolution.findings) | set(resolution.symbols))
    }


def run_fixture(rule_id: str, root: Path = BROKEN) -> tuple[Finding, ...]:
    """Return every finding of the fixture `<root>/<rule_id>/`, files in name order."""
    per_file = run_fixture_by_file(rule_id, root)
    return tuple(f for stem in sorted(per_file) for f in per_file[stem])
