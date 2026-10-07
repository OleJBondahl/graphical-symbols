"""`scripts/build_site.py` stages the pages, the spec and the schema, and builds them strict.

The module fixture stages a small stand-in repository and builds it once (about 1 s); the tests
share that build. `test_the_real_repository_builds_strict` stages the real sources instead.
"""

import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

import symdef

ROOT = Path(__file__).resolve().parent.parent
SITE = runpy.run_path(str(ROOT / "scripts" / "build_site.py"))
GUIDE_SET = Path(__file__).resolve().parent / "fixtures" / "guide"


def _stand_in(root: Path) -> Path:
    """A tiny repository: four one-line pages, the guide fixtures as the set, the real config."""
    (root / "docs" / "site").mkdir(parents=True)
    (root / "README.md").write_text("# Home\n\n[guide](docs/GUIDE.md) [x](AGENTS.md)\n")
    for name in ("TUTORIAL", "GUIDE", "DECISIONS"):
        (root / "docs" / f"{name}.md").write_text(f"# {name}\n\n[home](../README.md)\n")
    shutil.copytree(GUIDE_SET, root / "docs" / "tutorial-set")
    shutil.copy2(ROOT / "docs" / "site" / "mkdocs.yml", root / "docs" / "site" / "mkdocs.yml")
    for source in (SITE["SPEC"], SITE["SCHEMA"]):
        (root / source).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source, root / source)
    return root


@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    """Stage the stand-in once, build it strict once; return `(root, out)`."""
    base = tmp_path_factory.mktemp("site")
    root = _stand_in(base / "repo")
    out = SITE["stage"](root, base / "out")
    SITE["build"](out)
    return root, out


def test_api_markdown_lists_every_name_and_is_deterministic():
    text = SITE["api_markdown"]()
    assert all(f"## `{name}`" in text for name in symdef.__all__)
    assert text == SITE["api_markdown"]()
    positions = [text.index(f"## `{name}`") for name in symdef.__all__]
    assert positions == sorted(positions)


def test_api_markdown_gives_kind_and_signature():
    text = SITE["api_markdown"]()
    assert "*class*" in text
    assert "*function*" in text
    assert "*constant*" in text
    assert "to_svg(symbol: symdef.model.Symbol, *, module_mm: float = 2.5" in text


def test_staging_produces_the_pages(staged):
    _, out = staged
    pages = out / ".site-src" / "pages"
    names = {p.name for p in pages.iterdir()}
    expected = {"index.md", "tutorial.md", "guide.md", "decisions.md", "gallery.md", "api.md"}
    assert expected <= names
    assert {"SYMBOL_INTERFACE.html", "symbol.schema.json", "gallery"} <= names
    assert len(list((pages / "gallery").glob("*.svg"))) == 2 * 6


def test_spec_and_schema_are_byte_equal_to_their_sources(staged):
    root, out = staged
    pages = out / ".site-src" / "pages"
    for source, page in (
        (SITE["SPEC"], "SYMBOL_INTERFACE.html"),
        (SITE["SCHEMA"], "symbol.schema.json"),
    ):
        assert (pages / page).read_bytes() == (root / source).read_bytes()
        assert (out / ".site" / page).read_bytes() == (root / source).read_bytes()


def test_links_point_at_site_pages_or_github(staged):
    _, out = staged
    index = (out / ".site-src" / "pages" / "index.md").read_text(encoding="utf-8")
    assert "](guide.md)" in index
    assert f"]({SITE['REPO']}/blob/main/AGENTS.md)" in index
    assert "docs/GUIDE.md" not in index


def test_relink_leaves_fenced_code_and_absolute_links_alone():
    text = "```\n[a](docs/GUIDE.md)\n```\n[b](https://example.org/x) [c](#top)\n"
    assert SITE["relink"](text, "README.md") == text


def test_the_strict_build_succeeds(staged):
    _, out = staged
    assert (out / ".site" / "index.html").is_file()
    assert (out / ".site" / "gallery" / "index.html").is_file()


def test_a_broken_link_fails_the_strict_build(tmp_path):
    """ACCEPTANCE 9: the link check can fail."""
    out = SITE["stage"](_stand_in(tmp_path / "repo"), tmp_path / "out")
    index = out / ".site-src" / "pages" / "index.md"
    index.write_text(index.read_text(encoding="utf-8") + "\n[gone](missing-page.md)\n")
    with pytest.raises(subprocess.CalledProcessError):
        SITE["build"](out)


def test_the_real_repository_builds_strict(tmp_path):
    """Needs docs/TUTORIAL.md and docs/tutorial-set (P3 and P1); stages and builds the real site."""
    out = SITE["stage"](ROOT, tmp_path)
    SITE["build"](out)
    assert (out / ".site" / "tutorial" / "index.html").is_file()
