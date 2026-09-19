"""Every Python example in the README runs, so the README cannot drift from the code."""

import re
import shutil
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
GUIDE_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "guide"
BLOCK = re.compile(r"^```python[^\n]*\n(.*?)^```$", re.MULTILINE | re.DOTALL)


def examples() -> list[str]:
    """Return the code of every ```python block of the README, in order."""
    return BLOCK.findall(README.read_text(encoding="utf-8"))


def test_the_readme_has_examples():
    assert len(examples()) >= 3


def test_a_fence_with_an_info_string_after_python_is_an_example():
    text = "```python title=x\nprint(1)\n```\n\n```py\nprint(2)\n```\n"
    assert BLOCK.findall(text) == ["print(1)\n"]


def test_the_readme_examples_run_in_order_on_a_data_repo(tmp_path):
    # `root` is "a data repo" in the README; here it is a copy of the guide fixtures.
    root = tmp_path / "repo"
    shutil.copytree(GUIDE_FIXTURES, root)
    namespace = {"root": root}
    for number, code in enumerate(examples(), start=1):
        exec(compile(code, f"README.md example {number}", "exec"), namespace)  # noqa: S102
    assert (root / "build" / "resolved" / "S00227.json").is_file()
    assert (root / "src" / "iec60617" / "bundle.json").is_file()
