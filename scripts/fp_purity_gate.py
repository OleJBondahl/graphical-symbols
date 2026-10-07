"""Fail when a pure module does file or console I/O, reads the clock or randomness, or writes state.

Pure modules are every `.py` file under `src/symdef/`, subpackages included, except
`IMPURE_MODULES` (paths relative to the package). The check uses the standard library's `ast`
and covers the whole file, so a call inside a function counts. It fails on:
- a call to `print`, `input` or `open`, or to a method of a path (`read_text`, `write_text`,
  `write_bytes`, `read_bytes`, `mkdir`, `unlink`, ...), `os.*`, `sys.stdout`/`sys.stderr` writes;
- an import of `time`, `datetime`, `random`, `secrets`, `os`, `io`, `shutil`, `subprocess`,
  `socket`, `tempfile` or `logging`, which are how a pure module would reach the clock,
  randomness, files or the console;
- a `global` or `nonlocal` statement, and an assignment, augmented assignment or `del` that targets
  a module-level name from inside a function, or an attribute or item of a module-level name
  (`CACHE[key] = v`, `STATE.x = 1`, `ITEMS.append(...)` as a statement on a module-level name).

Usage:
    uv run python scripts/fp_purity_gate.py
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "src" / "symdef"
# Paths relative to the package. Each reads or writes files or the console: `files.py` is the
# shell around `library.toml` and the build, `project.py` the three verbs on a folder, `cli.py`
# prints and exits, `__main__.py` runs `cli`, and `__init__.py` is the re-export list.
IMPURE_MODULES = frozenset({"files.py", "project.py", "cli.py", "__main__.py", "__init__.py"})

BANNED_CALLS = frozenset({"print", "input", "open", "exec", "eval", "__import__"})
BANNED_IMPORTS = frozenset(
    {
        "time",
        "datetime",
        "random",
        "secrets",
        "os",
        "io",
        "shutil",
        "subprocess",
        "socket",
        "tempfile",
        "logging",
        "sys",
        "pathlib",
    }
)
MUTATORS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "add",
        "update",
        "pop",
        "remove",
        "clear",
        "discard",
        "setdefault",
    }
)


def _root_name(node: ast.expr) -> str | None:
    """Return the name at the base of an attribute or subscript chain, or None."""
    while isinstance(node, ast.Attribute | ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _module_names(tree: ast.Module) -> frozenset[str]:
    """Return the names a module assigns at its top level."""
    names: set[str] = set()
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign | ast.AugAssign):
            targets = [node.target]
        names.update(n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name))
    return frozenset(names)


def _imports(node: ast.stmt) -> list[str]:
    """Return the top-level module names an import statement brings in."""
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module.split(".")[0]]
    return []


def _state_writes(node: ast.AST, state: frozenset[str]) -> str | None:
    """Return what a statement or call writes into module state, or None."""
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AugAssign | ast.AnnAssign):
        targets = [node.target]
    elif isinstance(node, ast.Delete):
        targets = node.targets
    for target in targets:
        for sub in ast.walk(target):
            if isinstance(sub, ast.Attribute | ast.Subscript) and _root_name(sub) in state:
                return f"writes into module state {_root_name(sub)!r}"
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in MUTATORS
        and _root_name(node.func.value) in state
    ):
        return f"mutates module state {_root_name(node.func.value)!r}"
    return None


def violations(tree: ast.Module) -> list[tuple[int, str]]:
    """Return (line, what) for every purity violation in a module's syntax tree."""
    state = _module_names(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        names = _imports(node) if isinstance(node, ast.stmt) else []
        found.extend((line, f"imports {n!r}") for n in names if n in BANNED_IMPORTS)
        if isinstance(node, ast.Global | ast.Nonlocal):
            found.append((line, f"`{type(node).__name__.lower()}` statement"))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in BANNED_CALLS
        ):
            found.append((line, f"calls {node.func.id}()"))
        if message := _state_writes(node, state):
            found.append((line, message))
    return sorted(set(found))


def scan(package_dir: Path) -> list[tuple[Path, int, str]]:
    """Return (file, lineno, what) for every violation in the pure modules of a package."""
    found: list[tuple[Path, int, str]] = []
    for py in sorted(package_dir.rglob("*.py")):
        if py.relative_to(package_dir).as_posix() in IMPURE_MODULES:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        found.extend((py, line, what) for line, what in violations(tree))
    return found


def main() -> int:
    """Print every violation and return a non-zero exit code if there is any."""
    if not PACKAGE_DIR.is_dir():
        print(f"fp-purity-gate: {PACKAGE_DIR} not found", file=sys.stderr)
        return 2

    found = scan(PACKAGE_DIR)
    if not found:
        print("fp-purity-gate: every pure module is free of I/O, clock, randomness and state.")
        return 0

    print(f"fp-purity-gate: {len(found)} violation(s) in pure modules:")
    for path, lineno, what in found:
        print(f"  {path.relative_to(ROOT).as_posix()}:{lineno} {what}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
