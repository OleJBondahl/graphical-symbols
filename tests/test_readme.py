"""Every Python example in the README and docs/GUIDE.md runs, so they cannot drift from the code."""

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "GUIDE.md"
GUIDE_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "guide"
BLOCK = re.compile(r"^```python[^\n]*\n(.*?)^```$", re.MULTILINE | re.DOTALL)


def examples(path: Path = README) -> list[str]:
    """Return the code of every ```python block of a markdown file, in order."""
    return BLOCK.findall(path.read_text(encoding="utf-8"))


def run_examples(path: Path, tmp_path: Path) -> Path:
    """Run a file's examples in order on a fresh copy of the guide fixtures; return that copy.

    `root` is "a data repo" in the docs; here it is the copy.
    """
    root = tmp_path / "repo"
    shutil.copytree(GUIDE_FIXTURES, root)
    namespace = {"root": root}
    for number, code in enumerate(examples(path), start=1):
        exec(compile(code, f"{path.name} example {number}", "exec"), namespace)  # noqa: S102
    return root


def test_the_readme_has_examples():
    assert len(examples()) >= 3


def test_the_guide_has_examples():
    assert len(examples(GUIDE)) >= 4


def test_a_fence_with_an_info_string_after_python_is_an_example():
    text = "```python title=x\nprint(1)\n```\n\n```py\nprint(2)\n```\n"
    assert BLOCK.findall(text) == ["print(1)\n"]


def test_the_readme_examples_run_in_order_on_a_data_repo(tmp_path):
    root = run_examples(README, tmp_path)
    assert (root / "build" / "resolved" / "S00227.json").is_file()
    assert (root / "src" / "iec60617" / "bundle.json").is_file()


def test_the_guide_examples_run_in_order_on_their_own_data_repo(tmp_path):
    root = run_examples(GUIDE, tmp_path)
    assert (root / "build" / "resolved" / "S00227.json").is_file()
    assert (root / "src" / "iec60617" / "bundle.json").is_file()
