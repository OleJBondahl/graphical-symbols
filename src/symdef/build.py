"""The impure shell: everything that reads or writes files. Pure work stays in the other modules."""

from dataclasses import replace
from pathlib import Path
from typing import Any

from symdef.errors import LibraryError
from symdef.lint.registry import rule_finding
from symdef.load import (
    is_file_stem,
    library_from_bundle,
    parse_config,
    parse_json,
    parse_toml,
    validate_bundle,
)
from symdef.model import Finding, Library, LibraryConfig
from symdef.resolve import resolve_library
from symdef.serialize import GENERATED_DIRS, build_files, package_folder


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


def load_bundle(json_path: Path) -> Library:
    """Read a resolved bundle (`bundle.json`) into a library.

    The library has the bundle's standard for both `standard` and `title`, and no number pattern
    (D7). Symbols are checked like a source file, plus the resolved form (`validate_bundle`).

    Args:
        json_path: The bundle file.

    Returns:
        The library, its symbols keyed by the bundle's keys.

    Raises:
        LibraryError: If the file cannot be read, is not JSON or is not a valid bundle. Every
            finding is a `schema` finding, its message prefixed with the file name.
    """
    text, found = _read(json_path)
    if text is None:
        raise LibraryError(found)
    data, problems = parse_json(text)
    if not problems:
        problems = validate_bundle(data)
    if problems:
        raise LibraryError(_named(json_path.name, problems))
    return library_from_bundle(data)


def _package_key(root: Path) -> str:
    """Return the `package` key of `root/library.toml`, or `""` when it is absent or unreadable.

    `load_library` is where a bad `library.toml` is reported; a build only reads the one key.
    """
    config, _ = _read_config(root / "library.toml")
    return config.package if config else ""


def _check_names(library: Library, package: str) -> None:
    """Refuse a library that would need an unsafe file or directory name, before any file is made.

    A number must be a file stem, and the standard must give a package folder (D8, D35, D45).
    """
    for number in library.symbols:
        if not is_file_stem(number):
            msg = f"symbol number {number!r} cannot be used as a file name"
            raise ValueError(msg)
    if not package_folder(library.standard, package):
        msg = f"the standard {library.standard!r} has no letter or digit to make a package name of"
        raise ValueError(msg)


def write_build(library: Library, root: Path) -> tuple[Path, ...]:
    """Write the build of a library under a data repo: `build/` and `src/<package>/bundle.json`.

    `<package>` is the `package` key of `root/library.toml` when it has one, else made from the
    standard (D8, D45).

    Files are written as bytes, so line endings are LF on every platform, and missing directories
    are created. Nothing is deleted: a file that an earlier build wrote and this one does not
    (a removed symbol) stays, and `stale_build` reports it; removing it is the caller's job.

    Args:
        library: The library to build.
        root: The data repo's directory.

    Returns:
        Every path written, as `root / <relative path>` (so relative if `root` is), in the order
        of their `/`-separated relative paths.

    Raises:
        ValueError: If a symbol number is not a file stem (`is_file_stem`) or the standard has no
            letter or digit to make a package name of; nothing is written.
        OSError: If a path cannot be written; files already written stay.
    """
    package = _package_key(root)
    _check_names(library, package)
    written = []
    for relative, data in build_files(library, package).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(target)
    return tuple(written)


def stale_build(library: Library, root: Path) -> tuple[Path, ...]:
    """Return the files under `root` that differ from what `write_build` would write.

    A file is stale if it is missing or has other bytes, or if it sits anywhere under
    `build/resolved`, `build/svg` or `build/annotated` and the library does not produce it.
    Nothing else under `root` is looked at.

    Args:
        library: The library the build should match.
        root: The data repo's directory.

    Returns:
        The stale paths, as `root / <relative path>` (so relative if `root` is), in the order of
        their `/`-separated relative paths.

    Raises:
        ValueError: If a symbol number is not a file stem (`is_file_stem`) or the standard has no
            letter or digit to make a package name of.
        OSError: If a file cannot be read; it is not treated as stale.
    """
    package = _package_key(root)
    _check_names(library, package)
    files = build_files(library, package)
    stale = {
        relative
        for relative, data in files.items()
        if not (root / relative).is_file() or (root / relative).read_bytes() != data
    }
    for directory in GENERATED_DIRS:
        for path in (root / directory).rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_file() and relative not in files:
                stale.add(relative)
    return tuple(root / relative for relative in sorted(stale))
