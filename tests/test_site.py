"""`scripts/build_site.py` renders the pages, relinks them, and ships the spec."""

import runpy
from pathlib import Path

SITE = runpy.run_path(str(Path(__file__).resolve().parent.parent / "scripts" / "build_site.py"))


def test_the_site_has_its_four_pages(tmp_path):
    SITE["main"](tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "SYMBOL_INTERFACE.html",
        "decisions.html",
        "guide.html",
        "index.html",
    ]


def test_links_point_at_site_pages_or_github(tmp_path):
    SITE["main"](tmp_path)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'href="guide.html"' in index
    assert 'href="docs/GUIDE.md"' not in index
    assert f'href="{SITE["REPO"]}/blob/main/AGENTS.md"' in index
