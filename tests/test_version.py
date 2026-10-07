"""`LIBRARY_VERSION` is the package version, and `_version.py` is what `scripts/build.py` writes.

The stale-constant gate: bump `version` in `pyproject.toml` without running the build script
and this file fails, and so does `just ci`.
"""

import importlib.util
from pathlib import Path

import symdef

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("symdef_build", ROOT / "scripts" / "build.py")
assert _spec is not None
assert _spec.loader is not None
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
GENERATED = (ROOT / "src" / "symdef" / "_version.py").read_text(encoding="utf-8")


def test_the_constant_is_the_package_version():
    assert build.project_version(PYPROJECT) == symdef.LIBRARY_VERSION


def test_the_generated_module_is_what_the_build_writes():
    assert build.version_module(build.project_version(PYPROJECT)) == GENERATED


def test_the_constant_is_public():
    assert "LIBRARY_VERSION" in symdef.__all__


def test_the_written_module_defines_the_constant():
    namespace: dict[str, str] = {}
    exec(build.version_module("1.2.3"), namespace)  # noqa: S102 (the module the build writes)
    assert namespace["LIBRARY_VERSION"] == "1.2.3"


def test_another_version_in_pyproject_makes_the_module_stale():
    """The gate can fail: a bumped version gives text unlike what is on disk."""
    bumped = build.project_version('[project]\nversion = "9.9.9"\n')
    assert bumped != symdef.LIBRARY_VERSION
    assert build.version_module(bumped) != GENERATED
