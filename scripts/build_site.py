"""Stage the docs site and build it with Zensical, strict: a broken link fails the build.

Usage:
    uv run python scripts/build_site.py

Pages are staged into `.site-src/pages/` and built into `.site/`; both are gitignored and
rebuilt each run.
"""

import inspect
import posixpath
import re
import shutil
import subprocess
import sys
from annotationlib import Format
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import symdef
from symdef.gallery import sample_texts

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/OleJBondahl/symdef"
SPEC = "src/symdef/docs/SYMBOL_INTERFACE.html"
SCHEMA = "src/symdef/schema/symbol.schema.json"
PAGES = {
    "README.md": "index.md",
    "docs/TUTORIAL.md": "tutorial.md",
    "docs/GUIDE.md": "guide.md",
    "docs/DECISIONS.md": "decisions.md",
    SPEC: "SYMBOL_INTERFACE.html",
    SCHEMA: "symbol.schema.json",
}
LINK = re.compile(r"\]\(([^)\s#]+)(#[^)\s]*)?\)")


def _target(repo_path: str) -> str:
    """Map a repository path to its place on the site, or to GitHub."""
    return PAGES.get(repo_path) or f"{REPO}/blob/main/{repo_path}"


def relink(text: str, source: str) -> str:
    """Point every relative Markdown link of `source` at a site page or at the repository."""
    folder = posixpath.dirname(source)

    def fix(match: re.Match[str]) -> str:
        path, frag = match.group(1), match.group(2) or ""
        if "://" in path or path.startswith("mailto:"):
            return match.group(0)
        return f"]({_target(posixpath.normpath(posixpath.join(folder, path)))}{frag})"

    out, fenced = [], False
    for line in text.splitlines(keepends=True):
        edge = line.lstrip().startswith("```")
        fenced ^= edge
        out.append(line if fenced or edge else LINK.sub(fix, line))
    return "".join(out)


def _kind(obj: object) -> str:
    if inspect.isclass(obj):
        return "class"
    return "function" if callable(obj) else "constant"


def _signature(obj: Callable[..., object]) -> str:
    """The signature, or `(...)` for a class that inherits a builtin one (an exception)."""
    try:
        return str(inspect.signature(obj, annotation_format=Format.FORWARDREF))
    except ValueError:
        return "(...)"


def _entry(name: str) -> str:
    obj = getattr(symdef, name)
    kind = _kind(obj)
    lines = [f"## `{name}`", "", f"*{kind}*", ""]
    if kind == "constant":
        lines += [f"Value: `{obj!r}`", ""]
    else:
        lines += [f"```python\n{name}{_signature(obj)}\n```", ""]
        doc = inspect.getdoc(obj)
        if doc:
            lines += [f"```text\n{doc}\n```", ""]
    return "\n".join(lines)


def api_markdown() -> str:
    """The API reference: each name of `symdef.__all__` in order, with its facts."""
    head = "# API reference\n\nEvery name `symdef` exports, in the order of `symdef.__all__`.\n\n"
    return head + "\n".join(_entry(name) for name in symdef.__all__)


def gallery_markdown(root: Path, site_src: Path) -> str:
    """Write each symbol of `docs/tutorial-set` as two SVGs and return the gallery page."""
    library = symdef.load_library(root / "docs" / "tutorial-set")
    images = site_src / "gallery"
    images.mkdir(parents=True)
    lines = [
        "# Gallery",
        "",
        "Every symbol of the tutorial set, plain and annotated with its ports, anchors and slots.",
        "",
    ]
    for number in sorted(library.symbols):
        symbol = library.symbols[number]
        stem = quote(number, safe="", errors="replace")
        (images / f"{stem}.svg").write_text(symdef.to_svg(symbol), encoding="utf-8")
        annotated = symdef.to_svg(symbol, annotate=True, texts=sample_texts(symbol))
        (images / f"{stem}-annotated.svg").write_text(annotated, encoding="utf-8")
        lines += [
            f"## {number} {symbol.name}",
            "",
            f"Status: `{symbol.status.value}`",
            "",
            f"![{number}](gallery/{stem}.svg) ![{number} annotated](gallery/{stem}-annotated.svg)",
            "",
        ]
    return "\n".join(lines)


def stage(root: Path, out: Path) -> Path:
    """Rebuild `out/.site-src/pages/` and `out/mkdocs.yml` from `root`'s sources; return `out`."""
    site_src = out / ".site-src" / "pages"
    shutil.rmtree(site_src.parent, ignore_errors=True)
    site_src.mkdir(parents=True)
    for source, page in PAGES.items():
        if page.endswith(".md"):
            text = (root / source).read_text(encoding="utf-8")
            (site_src / page).write_text(relink(text, source), encoding="utf-8")
        else:
            shutil.copy2(root / source, site_src / page)
    (site_src / "gallery.md").write_text(gallery_markdown(root, site_src), encoding="utf-8")
    (site_src / "api.md").write_text(api_markdown(), encoding="utf-8")
    shutil.copy2(root / "docs" / "site" / "mkdocs.yml", out / "mkdocs.yml")
    return out


def build(project: Path) -> None:
    """Run Zensical strict from `project`, the folder that holds the config."""
    subprocess.run(
        [sys.executable, "-m", "zensical", "build", "--strict", "-f", "mkdocs.yml"],
        cwd=project,
        check=True,
    )


def main() -> None:
    """Stage the repository's site and build it into `.site/`."""
    shutil.rmtree(ROOT / ".site", ignore_errors=True)
    build(stage(ROOT, ROOT))
    sys.stdout.write(f"site built: {ROOT / '.site'}\n")


if __name__ == "__main__":
    main()
