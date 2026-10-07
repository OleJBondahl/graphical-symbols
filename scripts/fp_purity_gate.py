"""Fail when a module-level function in a pure module lacks @deal.pure.

Pure modules are every `.py` file under `src/symdef/`, subpackages included, except
the top-level impure shell and the top-level `__init__.py`. Modules are
identified by their path relative to the package, so `lint/__init__.py` is scanned.

Usage:
    uv run python scripts/fp_purity_gate.py
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "src" / "symdef"
IMPURE_MODULES = frozenset(
    {"files.py", "project.py", "cli.py", "__main__.py", "__init__.py"}
)  # paths relative to the package


def _decorator_name(dec: ast.expr) -> str:
    """Render a decorator AST node as a dotted name."""
    match dec:
        case ast.Name(id=name):
            return name
        case ast.Attribute(value=base, attr=attr):
            return f"{_decorator_name(base)}.{attr}"
        case ast.Call(func=func):
            return _decorator_name(func)
        case _:
            return "<expr>"


def scan(package_dir: Path) -> list[tuple[Path, int, str]]:
    """Return (file, lineno, name) for module-level defs in pure modules lacking @deal.pure."""
    missing: list[tuple[Path, int, str]] = []
    for py in sorted(package_dir.rglob("*.py")):
        if py.relative_to(package_dir).as_posix() in IMPURE_MODULES:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if "deal.pure" not in (_decorator_name(d) for d in node.decorator_list):
                missing.append((py, node.lineno, node.name))
    return missing


def main() -> int:
    """Print every violation and return a non-zero exit code if there is any."""
    if not PACKAGE_DIR.is_dir():
        print(f"fp-purity-gate: {PACKAGE_DIR} not found", file=sys.stderr)
        return 2

    missing = scan(PACKAGE_DIR)
    if not missing:
        print("fp-purity-gate: every module-level function in pure modules has @deal.pure.")
        return 0

    print(f"fp-purity-gate: {len(missing)} function(s) missing @deal.pure:")
    for path, lineno, name in missing:
        print(f"  {path.relative_to(ROOT).as_posix()}:{lineno} {name}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
