"""The `symdef` command: `init`, `build` and `check` on a folder (D48). Impure: prints and exits."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from symdef.errors import LibraryError
from symdef.model import Finding
from symdef.project import build, check, init


def _report(findings: Sequence[Finding]) -> None:
    """Print one line per distinct finding (lint repeats a finding once per orientation)."""
    lines = (
        f"{f.severity.value} {f.rule}{f' [{f.location}]' if f.location else ''}: {f.message}\n"
        for f in findings
    )
    sys.stdout.write("".join(dict.fromkeys(lines)))


def _init(root: Path) -> int:
    try:
        written = init(root)
    except FileExistsError as error:
        sys.stderr.write(f"symdef: {error}\n")
        return 1
    sys.stdout.write("".join(f"wrote {p}\n" for p in written))
    return 0


def _build(root: Path) -> int:
    try:
        written = build(root)
    except LibraryError as error:
        _report(error.findings)
        return 1
    sys.stdout.write(f"wrote {len(written)} files\n")
    return 0


def _check(root: Path) -> int:
    findings = check(root)
    _report(findings)
    return 1 if findings else 0


VERBS = {"init": _init, "build": _build, "check": _check}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return its exit code: 0 done, 1 problems found, 2 bad usage."""
    parser = argparse.ArgumentParser(prog="symdef", description="Build and check a symbol set.")
    parser.add_argument("verb", choices=sorted(VERBS))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    return VERBS[args.verb](args.directory)
