"""Render the README, the guide and the decisions into a minimal static site for GitHub Pages.

Usage:
    uv run python scripts/build_site.py OUT_DIR
"""

import re
import shutil
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/OleJBondahl/symdef"
SPEC = ROOT / "src" / "symdef" / "docs" / "SYMBOL_INTERFACE.html"
PAGES = {
    "README.md": "index.html",
    "docs/GUIDE.md": "guide.html",
    "docs/DECISIONS.md": "decisions.html",
}
PAGE = (
    "<!doctype html><html lang='en'><meta charset='utf-8'><title>symdef</title>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<style>body{{max-width:48rem;margin:2rem auto;padding:0 1rem;font:16px/1.5 sans-serif}}"
    "pre{{overflow-x:auto;background:#f4f4f4;padding:.5rem}}</style>"
    "<nav><a href='index.html'>symdef</a> | <a href='guide.html'>Guide</a> | "
    "<a href='decisions.html'>Decisions</a> | <a href='SYMBOL_INTERFACE.html'>Spec</a></nav>"
    "{body}</html>"
)
HREF = re.compile(r'href="([^"#]+)(#[^"]*)?"')


def _target(path: str) -> str:
    """Map a repository-relative link to its place on the site, or to GitHub."""
    name = path.rsplit("../", 1)[-1]
    if name.endswith("SYMBOL_INTERFACE.html"):
        return "SYMBOL_INTERFACE.html"
    for source, page in PAGES.items():
        if name == source or name == Path(source).name:
            return page
    return f"{REPO}/blob/main/{name}"


def _relink(html: str) -> str:
    """Point every relative link at a site page or at the repository on GitHub."""

    def fix(match: re.Match[str]) -> str:
        path, frag = match.group(1), match.group(2) or ""
        if "://" in path or path.startswith("mailto:"):
            return match.group(0)
        return f'href="{_target(path)}{frag}"'

    return HREF.sub(fix, html)


def main(out: Path) -> None:
    """Write the pages and the spec into `out`."""
    out.mkdir(parents=True, exist_ok=True)
    for source, page in PAGES.items():
        body = markdown.markdown(
            (ROOT / source).read_text(encoding="utf-8"), extensions=["fenced_code", "tables"]
        )
        (out / page).write_text(PAGE.format(body=_relink(body)), encoding="utf-8")
    shutil.copy(SPEC, out / "SYMBOL_INTERFACE.html")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
