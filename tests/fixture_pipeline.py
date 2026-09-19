"""Run a broken fixture through the toolkit's pipeline and return every finding it produces.

Imported by the tests as `from fixture_pipeline import run_fixture`: pytest puts this directory
on `sys.path` because `tests/` has no `__init__.py`.
"""

import tomllib
from pathlib import Path

from graphical_symbols.load import parse_config
from graphical_symbols.model import Finding
from graphical_symbols.resolve import resolve_library

BROKEN = Path(__file__).resolve().parent / "fixtures" / "broken"


def run_fixture(rule_id: str, root: Path = BROKEN) -> tuple[Finding, ...]:
    """Load `<root>/<rule_id>/`, resolve it and return all findings, files in name order.

    The library config is the fixture's own `library.toml` if it has one, else the one in `<root>`.
    Once the linter exists it also lints every resolved symbol here.

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
    return tuple(f for stem in sorted(resolution.findings) for f in resolution.findings[stem])
