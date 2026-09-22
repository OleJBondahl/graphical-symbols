"""The guide's own example files are the toolkit's first fixtures: verbatim, loadable, valid."""

import tomllib
from html.parser import HTMLParser
from pathlib import Path

import pytest

from graphical_symbols.load import parse_config, parse_toml, symbol_from_data, validate

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "src" / "graphical_symbols" / "docs" / "SYMBOL_INTERFACE.html"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "guide"
SYMBOL_FILES = sorted((FIXTURES / "symbols").glob("*.toml"))

ATOMIC_PORT_IDS = {
    "S00227": ("in", "out"),
    "S00230": ("com", "no", "nc"),
    "S00305": ("in", "out"),
    "S00016": ("n", "e", "s", "w"),
    "S00171": (),
}


class _CodeBlocks(HTMLParser):
    """Collect the text of every `<pre data-lang=...><code>` block, entities decoded."""

    def __init__(self) -> None:
        super().__init__()
        self.lang: str | None = None
        self.in_code = False
        self.buffer: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.lang = dict(attrs).get("data-lang")
        elif tag == "code" and self.lang:
            self.in_code = True
            self.buffer = []

    def handle_endtag(self, tag):
        if tag == "code" and self.in_code:
            self.blocks.append((self.lang or "", "".join(self.buffer)))
            self.in_code = False
        elif tag == "pre":
            self.lang = None

    def handle_data(self, data):
        if self.in_code:
            self.buffer.append(data)


def guide_blocks(html: str) -> dict[str, str]:
    """Map a fixture path relative to `tests/fixtures/guide` to the guide block it must equal."""
    parser = _CodeBlocks()
    parser.feed(html)
    blocks: dict[str, str] = {}
    for lang, text in parser.blocks:
        if lang == "toml":
            number = tomllib.loads(text)["reference"]["number"]
            blocks[f"symbols/{number}.toml"] = text
        elif lang == "toml-config":
            blocks["library.toml"] = text
    return blocks


def mismatches(html: str) -> list[str]:
    """Return the fixtures that differ, byte for byte, from their code block in `html`."""
    return [
        name
        for name, text in guide_blocks(html).items()
        if (FIXTURES / name).read_bytes() != text.encode("utf-8")
    ]


def test_the_guide_has_the_five_examples_and_the_config():
    assert sorted(guide_blocks(GUIDE.read_bytes().decode("utf-8"))) == [
        "library.toml",
        "symbols/S00016.toml",
        "symbols/S00227.toml",
        "symbols/S00230.toml",
        "symbols/S00254.toml",
        "symbols/S00305.toml",
    ]


def test_fixtures_are_byte_equal_to_the_guide_code_blocks():
    assert mismatches(GUIDE.read_bytes().decode("utf-8")) == []


def test_the_byte_comparison_can_fail():
    html = GUIDE.read_bytes().decode("utf-8")
    mutated = html.replace('at = [0, -2], dir = "N"', 'at = [0, -3], dir = "N"', 1)
    assert mutated != html
    assert mismatches(mutated) == ["symbols/S00227.toml"]


def test_entities_in_a_block_are_decoded():
    html = '<pre data-lang="toml-config"><code>a = "&lt;&amp;&gt;"</code></pre>'
    assert guide_blocks(html) == {"library.toml": 'a = "<&>"'}


def test_the_fixture_directory_holds_the_six_symbols():
    assert [p.stem for p in SYMBOL_FILES] == [
        "S00016",
        "S00171",
        "S00227",
        "S00230",
        "S00254",
        "S00305",
    ]


@pytest.mark.parametrize("path", SYMBOL_FILES, ids=lambda p: p.stem)
def test_every_symbol_file_parses_and_validates(path):
    data, parse_findings = parse_toml(path.read_text(encoding="utf-8"))
    assert parse_findings == ()
    assert data is not None
    assert validate(data) == ()
    assert data["reference"]["number"] == path.stem


@pytest.mark.parametrize("number", sorted(ATOMIC_PORT_IDS))
def test_atomic_symbols_build_with_their_port_ids(number):
    data, _ = parse_toml((FIXTURES / "symbols" / f"{number}.toml").read_text(encoding="utf-8"))
    assert data is not None
    symbol = symbol_from_data(data)
    assert tuple(port.id for port in symbol.ports) == ATOMIC_PORT_IDS[number]
    assert symbol.reference.number == number
    assert symbol.reference.standard == "IEC 60617"


def test_the_composite_example_has_no_elements_of_its_own():
    data, _ = parse_toml((FIXTURES / "symbols" / "S00254.toml").read_text(encoding="utf-8"))
    assert data is not None
    assert "elements" not in data
    assert [part["as"] for part in data["parts"]] == ["contact", "actuator"]


def test_the_library_config_parses():
    config, findings = parse_config((FIXTURES / "library.toml").read_text(encoding="utf-8"))
    assert findings == ()
    assert config is not None
    assert (config.standard, config.title, config.number_pattern) == (
        "IEC 60617",
        "IEC 60617 symbols",
        r"^S\d{5}$",
    )
