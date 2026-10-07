"""The newcomer's verbs, `init`, `build` and `check`, also run as commands (D48). Impure."""

from pathlib import Path

from symdef.errors import LibraryError
from symdef.files import (
    load_bundle,
    load_library,
    package_key,
    stale_build,
    write_build,
)
from symdef.lint import lint
from symdef.model import Finding, Library, Severity
from symdef.repeat import repeat
from symdef.serialize import package_folder, symbol_to_data
from symdef.starter import starter_files


def init(root: Path) -> tuple[Path, ...]:
    """Write the starter set under `root`: `library.toml`, one symbol and `.gitattributes`.

    Raises:
        FileExistsError: If any of the files exists; nothing is written.
    """
    targets = {root / relative: text for relative, text in starter_files().items()}
    for target in targets:
        if target.exists():
            msg = f"{target} exists; init writes into an empty folder"
            raise FileExistsError(msg)
    for target, text in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    return tuple(targets)


def _lint_findings(library: Library, label: str = "") -> tuple[Finding, ...]:
    """Lint every symbol with the set's required slots; each message names its symbol."""
    found = []
    for symbol in library:
        number = symbol.reference.number
        found.extend(_named(f"{number}{label}", lint(symbol, library.required_slots)))
    return tuple(found)


def _named(name: str, findings: tuple[Finding, ...]) -> list[Finding]:
    """Prefix each message with the name of what it is about."""
    return [
        Finding(f.rule, f.severity, f"{name}: {f.message}", f.location, f.orientation)
        for f in findings
    ]


def build(root: Path) -> tuple[Path, ...]:
    """Load and lint the set under `root`, then write `build/` and the bundle.

    Returns:
        Every path written.

    Raises:
        LibraryError: If a file fails to load or lint reports an error; nothing is written.
    """
    library = load_library(root)
    errors = tuple(f for f in _lint_findings(library) if f.severity is Severity.ERROR)
    if errors:
        raise LibraryError(errors)
    return write_build(library, root)


def _through_repeats(library: Library) -> tuple[Finding, ...]:
    """Gate 3: every symbol with a through path also lints clean as `repeat(symbol, 3)`."""
    found = []
    for symbol in library:
        if any(path.through for path in symbol.paths):
            repeated = repeat(symbol, 3)
            number = symbol.reference.number
            found.extend(
                _named(f"{number} repeated 3 times", lint(repeated, library.required_slots))
            )
    return tuple(found)


def _stale(library: Library, root: Path) -> tuple[Finding, ...]:
    """Gate 4: the build matches the source."""
    return tuple(
        Finding(
            "stale-build",
            Severity.ERROR,
            f"{path.relative_to(root).as_posix()} is stale; run `symdef build`",
        )
        for path in stale_build(library, root)
    )


def _bundle(library: Library, root: Path) -> tuple[Finding, ...]:
    """Gate 6: the written bundle holds the source's symbols, and they lint clean."""
    folder = package_folder(library.standard, package_key(root))
    path = root / "src" / folder / "bundle.json"
    if not path.is_file():
        return ()  # `_stale` already reports it missing
    try:
        bundle = load_bundle(path)
    except LibraryError as error:
        return error.findings
    found = []
    if sorted(bundle.symbols) != sorted(library.symbols):
        found.append(
            Finding("bundle-differs", Severity.ERROR, "the bundle's numbers differ from the source")
        )
    for number, symbol in library.symbols.items():
        other = bundle.symbols.get(number)
        if other is not None and symbol_to_data(other) != symbol_to_data(symbol):
            found.append(
                Finding(
                    "bundle-differs",
                    Severity.ERROR,
                    f"{number}: the bundle differs from the source",
                )
            )
    return (
        *found,
        *_lint_findings(
            Library(
                bundle.standard,
                bundle.title,
                bundle.number_pattern,
                bundle.symbols,
                library.vocabulary,
                library.required_slots,
            ),
            " in the bundle",
        ),
    )


def check(root: Path) -> tuple[Finding, ...]:
    """Run the gates every symbol set needs and return their findings; empty means green.

    Files load and resolve (a number equals its file stem and fits `number_pattern` there); every
    symbol lints clean; a symbol with a through path lints clean repeated 3 times; the build is not
    stale; the bundle holds the source's symbols and lints clean.
    """
    try:
        library = load_library(root)
    except LibraryError as error:
        return error.findings
    return (
        *_lint_findings(library),
        *_through_repeats(library),
        *_stale(library, root),
        *_bundle(library, root),
    )
