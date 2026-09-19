"""The impure shell: everything that reads or writes files. Pure work stays in the other modules."""

from dataclasses import replace
from pathlib import Path
from typing import Any

from graphical_symbols.errors import LibraryError
from graphical_symbols.lint.registry import rule_finding
from graphical_symbols.load import parse_config, parse_toml
from graphical_symbols.model import Finding, Library, LibraryConfig
from graphical_symbols.resolve import resolve_library


def _named(name: str, findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    """Prefix each message with the file it is about, since a finding has no file of its own."""
    return tuple(replace(f, message=f"{name}: {f.message}") for f in findings)


def _read(path: Path) -> tuple[str | None, tuple[Finding, ...]]:
    """Read a UTF-8 text file; one that cannot be read is a `schema` finding located at its name."""
    try:
        return path.read_text(encoding="utf-8"), ()
    except (OSError, UnicodeDecodeError) as error:
        return None, _named(path.name, (rule_finding("schema", str(error), path.name),))


def _read_config(path: Path) -> tuple[LibraryConfig | None, tuple[Finding, ...]]:
    """Read `library.toml`."""
    text, found = _read(path)
    if text is None:
        return None, found
    config, problems = parse_config(text)
    return config, _named(path.name, problems)


def _read_symbol(path: Path) -> tuple[dict[str, Any] | None, tuple[Finding, ...]]:
    """Read one symbol file's TOML."""
    text, found = _read(path)
    if text is None:
        return None, found
    data, problems = parse_toml(text)
    return data, _named(path.name, problems)


def load_library(root: Path) -> Library:
    """Read `library.toml` and `symbols/*.toml` under `root`, validate, resolve and flatten them.

    Args:
        root: The data repo's directory.

    Returns:
        The library, its symbols keyed by reference number.

    Raises:
        LibraryError: If a file cannot be read or fails any check. `findings` holds every
            finding, `library.toml` first and then the symbol files in name order, each message
            prefixed with its file name.
    """
    config, problems = _read_config(root / "library.toml")
    directory = root / "symbols"
    if not directory.is_dir():
        missing = rule_finding("schema", "the directory does not exist", directory.name)
        raise LibraryError((*problems, *_named(directory.name, (missing,))))
    per_file: dict[str, tuple[Finding, ...]] = {}
    sources: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.toml"), key=lambda p: p.stem):
        data, found = _read_symbol(path)
        if data is None:
            per_file[path.stem] = found
        else:
            sources[path.stem] = data
    if config is None:
        raise LibraryError((*problems, *(f for stem in sorted(per_file) for f in per_file[stem])))
    resolution = resolve_library(config, sources)
    per_file |= {stem: _named(f"{stem}.toml", found) for stem, found in resolution.findings.items()}
    problems += tuple(f for stem in sorted(per_file) for f in per_file[stem])
    if problems:
        raise LibraryError(problems)
    return Library(config.standard, config.title, config.number_pattern, resolution.symbols)
