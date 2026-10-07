"""docs/TUTORIAL.md runs, step by step, in an empty folder, so it cannot drift from the toolkit.

The convention, in document order:
- A ```console block: each line starting `$ ` is a command. Only `$ symdef ...` is run, through
  `symdef.cli.main`. A trailing `# exit N` (default 0) is the exit code the tutorial states. The
  other lines of the block are output; each must appear among the lines the command printed.
- An HTML comment `<!-- edit: PATH | find: TEXT -->` makes the next ```toml block an edit: the
  first line of PATH that contains TEXT is replaced by the block's lines.
- An HTML comment `<!-- shows: PATH -->` makes the next ```toml block the exact text of PATH.
- Every ```python block runs, in order, in one namespace.
"""

import re
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from symdef.cli import main

if TYPE_CHECKING:
    import pytest

TUTORIAL = Path(__file__).resolve().parent.parent / "docs" / "TUTORIAL.md"
STEP = re.compile(
    r"<!-- (?P<kind>edit|shows): (?P<args>[^>]*?) -->\n```toml\n(?P<toml>.*?)^```$"
    r"|^```(?P<lang>console|python)\n(?P<body>.*?)^```$",
    re.MULTILINE | re.DOTALL,
)


def steps(text: str) -> list[tuple[str, str, str]]:
    """Return (kind, args, body) for each runnable block of the text, in order."""
    return [
        (m["kind"], m["args"], m["toml"]) if m["kind"] else (m["lang"], "", m["body"])
        for m in STEP.finditer(text)
    ]


def edit(root: Path, args: str, new: str) -> None:
    """Replace the first line of the file that contains the `find:` text by `new`."""
    path, find = (part.strip() for part in args.split("| find:"))
    file = root / path
    lines = file.read_text(encoding="utf-8").splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if find in line)
    lines[index : index + 1] = [new]
    file.write_text("".join(lines), encoding="utf-8")


def console(block: str, capsys: pytest.CaptureFixture[str]) -> int:
    """Run each `$ symdef` command of a block and check its exit code and printed lines."""
    ran = 0
    lines = block.splitlines()
    for number, line in enumerate(lines):
        if not line.startswith("$ symdef "):
            continue
        command, _, exit_text = line[2:].partition("  # exit ")
        after = lines[number + 1 :]
        expected = after[: next((i for i, o in enumerate(after) if o.startswith("$ ")), len(after))]
        code = main(shlex.split(command)[1:])
        printed = capsys.readouterr()
        shown = (printed.out + printed.err).splitlines()
        assert code == int(exit_text or 0), f"{command}: exit {code}"
        assert all(out in shown for out in expected), f"{command}: printed {shown}"
        ran += 1
    return ran


def test_the_tutorial_runs_from_an_empty_folder_to_a_page(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {}
    commands = 0
    for kind, args, body in steps(TUTORIAL.read_text(encoding="utf-8")):
        if kind == "console":
            commands += console(body, capsys)
        elif kind == "edit":
            edit(tmp_path, args, body)
        elif kind == "shows":
            assert (tmp_path / args).read_text(encoding="utf-8") == body, f"{args} differs"
        else:
            exec(compile(body, "TUTORIAL.md python block", "exec"), namespace)  # noqa: S102
    assert commands >= 9
    assert "<svg" in (tmp_path / "page.html").read_text(encoding="utf-8")
    assert "<g" in (tmp_path / "sheet.svg").read_text(encoding="utf-8")


def test_steps_reads_the_four_block_kinds():
    text = (
        "<!-- edit: a | find: x -->\n```toml\nnew\n```\n"
        "<!-- shows: b -->\n```toml\nold\n```\n"
        "```console\n$ symdef check d\n```\n```python\npass\n```\n```toml\nplain\n```\n"
    )
    assert steps(text) == [
        ("edit", "a | find: x", "new\n"),
        ("shows", "b", "old\n"),
        ("console", "", "$ symdef check d\n"),
        ("python", "", "pass\n"),
    ]


def test_edit_replaces_the_first_line_with_the_text(tmp_path):
    (tmp_path / "f").write_text("a\nbx\nbx\n", encoding="utf-8")
    edit(tmp_path, "f | find: x", "new\n")
    assert (tmp_path / "f").read_text(encoding="utf-8") == "a\nnew\nbx\n"
