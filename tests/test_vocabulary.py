"""A symbol set declares its own words and required slots in `library.toml` (SD6, SD7)."""

import shutil
from pathlib import Path

import pytest

import symdef
from symdef import LibraryError, Vocabulary, lint, load_library
from symdef.load import parse_config
from symdef.vocabulary import vocabulary_findings

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PIPE = FIXTURES / "pipe"
GUIDE = FIXTURES / "guide"
KIND_LINE = 17  # the `pipe` path in P00001.toml
POTENTIAL_LINE = 13


def copy_of(source: Path, tmp_path: Path, config: str | None = None) -> Path:
    """Copy a fixture set to `tmp_path`, with `config` as its `library.toml` when given."""
    root = tmp_path / "repo"
    shutil.copytree(source, root)
    if config is not None:
        (root / "library.toml").write_text(config, encoding="utf-8")
    return root


def messages(root: Path) -> list[str]:
    with pytest.raises(LibraryError) as raised:
        load_library(root)
    return [f.message for f in raised.value.findings]


def undeclared(stem: str, label: str, word: str, declared: str, line: int) -> str:
    """The load error for a word not declared in `library.toml`."""
    where = f"library.toml [vocabulary] {declared} (line {line})"
    return f"{stem}.toml: {label} '{word}' is not declared in {where}"


def pipe_config(vocabulary: str = "", rules: str = "") -> str:
    head = (PIPE / "library.toml").read_text(encoding="utf-8").split("[vocabulary]")[0]
    return head + vocabulary + rules


class TestADeclaredWordLoads:
    def test_the_pipe_set_loads_with_its_own_words(self):
        library = load_library(PIPE)
        assert library.vocabulary == Vocabulary(("pipe",), ("vent",), ())
        assert library.get("P00001").paths[0].kind == "pipe"
        assert library.get("P00001").nodes[0].potential == "vent"

    def test_the_pipe_set_lints_clean_with_no_slot_duty(self):
        library = load_library(PIPE)
        assert library.required_slots == ()
        assert lint(library.get("P00001"), library.required_slots) == ()

    def test_the_guide_set_declares_today_s_words(self):
        library = load_library(GUIDE)
        assert "switch_open" in library.vocabulary.path_kinds
        assert library.vocabulary.potentials[0] == "earth"
        assert library.vocabulary.links == ("mechanical_link",)

    def test_vocabulary_is_public(self):
        assert symdef.Vocabulary is Vocabulary
        assert "Vocabulary" in symdef.__all__


class TestAnUndeclaredWordIsALoadError:
    def test_a_path_kind_names_the_word_the_file_and_the_line(self, tmp_path):
        root = copy_of(PIPE, tmp_path, pipe_config('[vocabulary]\npath_kinds = ["duct"]\n'))
        assert messages(root) == [
            undeclared("P00001", "path kind", "pipe", "path_kinds", KIND_LINE),
            undeclared("P00001", "potential", "vent", "potentials", POTENTIAL_LINE),
        ]

    def test_a_missing_list_is_empty(self, tmp_path):
        root = copy_of(PIPE, tmp_path, pipe_config())
        assert len(messages(root)) == 2

    def test_a_potential_names_the_word_the_file_and_the_line(self, tmp_path):
        config = pipe_config('[vocabulary]\npath_kinds = ["pipe"]\npotentials = ["tank"]\n')
        assert messages(copy_of(PIPE, tmp_path, config)) == [
            undeclared("P00001", "potential", "vent", "potentials", POTENTIAL_LINE)
        ]

    def test_a_link_names_the_word_the_file_and_the_line(self, tmp_path):
        text = (GUIDE / "library.toml").read_text(encoding="utf-8")
        config = text.replace('links = ["mechanical_link"]', "links = []")
        assert messages(copy_of(GUIDE, tmp_path, config)) == [
            undeclared("S00254", "link", "mechanical_link", "links", 9)
        ]

    def test_a_word_used_twice_is_reported_once_at_its_first_line(self, tmp_path):
        root = copy_of(PIPE, tmp_path, pipe_config('[vocabulary]\npotentials = ["vent"]\n'))
        symbol = root / "symbols" / "P00001.toml"
        again = '{ from = "out", to = "in", kind = "pipe" },\n  '
        symbol.write_text(
            symbol.read_text(encoding="utf-8").replace("{ from", again + "{ from"), "utf-8"
        )
        (found,) = messages(root)
        assert found.endswith(f"path_kinds (line {KIND_LINE})")

    def test_a_word_written_with_an_escape_is_found_at_line_one(self, tmp_path):
        root = copy_of(PIPE, tmp_path, pipe_config('[vocabulary]\npotentials = ["vent"]\n'))
        symbol = root / "symbols" / "P00001.toml"
        escaped = 'kind = "p\\u0069pe"'
        symbol.write_text(
            symbol.read_text(encoding="utf-8").replace('kind = "pipe"', escaped), encoding="utf-8"
        )
        assert messages(root)[0].endswith("path_kinds (line 1)")

    def test_a_single_quoted_word_is_found_too(self, tmp_path):
        root = copy_of(PIPE, tmp_path, pipe_config('[vocabulary]\npotentials = ["vent"]\n'))
        symbol = root / "symbols" / "P00001.toml"
        symbol.write_text(
            symbol.read_text(encoding="utf-8").replace('kind = "pipe"', "kind = 'pipe'"),
            encoding="utf-8",
        )
        assert messages(root)[0].endswith(f"path_kinds (line {KIND_LINE})")


class TestVocabularyFindings:
    WORDS = Vocabulary(("a",), (), ())

    def test_a_declared_word_is_clean(self):
        assert vocabulary_findings({"paths": [{"kind": "a"}]}, self.WORDS, "") == ()

    @pytest.mark.parametrize(
        "data",
        [{}, {"paths": "x"}, {"paths": ["x"]}, {"paths": [{"kind": 3}]}, {"paths": [{}]}],
    )
    def test_a_shape_the_schema_check_reports_is_left_to_it(self, data):
        assert vocabulary_findings(data, self.WORDS, "") == ()

    def test_the_location_is_the_first_use(self):
        data = {"paths": [{"kind": "a"}, {"kind": "b"}, {"kind": "b"}]}
        (found,) = vocabulary_findings(data, self.WORDS, "")
        assert (found.rule, found.location) == ("schema", "/paths/1/kind")


class TestConfigTables:
    def test_the_lists_are_read_and_a_missing_one_is_empty(self):
        config, found = parse_config(pipe_config('[vocabulary]\npath_kinds = ["x", "y"]\n'))
        assert found == ()
        assert config is not None
        assert config.vocabulary == Vocabulary(("x", "y"), (), ())
        assert config.required_slots == ()

    @pytest.mark.parametrize(
        ("table", "location"),
        [
            ('[vocabulary]\npath_kinds = "pipe"\n', "/vocabulary/path_kinds"),
            ("[vocabulary]\npotentials = [1]\n", "/vocabulary/potentials/0"),
            ("[vocabulary]\nlink = []\n", "/vocabulary/link"),
            ('[rules]\nrequired_slots = "tag"\n', "/rules/required_slots"),
            ("[rules]\nrequired = []\n", "/rules/required"),
        ],
    )
    def test_a_bad_table_is_a_schema_finding(self, table, location):
        config, found = parse_config(pipe_config(table))
        assert config is None
        assert [(f.rule, f.location) for f in found] == [("schema", location)]


class TestRequiredSlots:
    def library(self, tmp_path, rules=""):
        return load_library(copy_of(PIPE, tmp_path, (PIPE / "library.toml").read_text() + rules))

    def locations(self, tmp_path, rules):
        library = self.library(tmp_path, rules)
        found = lint(library.get("P00001"), library.required_slots)
        return [f.location for f in found if f.rule == "slot-missing"]

    def test_absent_means_no_slot_duty(self, tmp_path):
        assert self.locations(tmp_path, "") == []

    def test_declared_slots_are_required_and_a_port_entry_means_one_per_port(self, tmp_path):
        rules = '\n[rules]\nrequired_slots = ["tag", "marking.<port>"]\n'
        assert self.locations(tmp_path, rules) == [
            "slots.marking.in",
            "slots.marking.out",
            "slots.tag",
        ]

    def test_a_set_may_name_its_own_slots(self, tmp_path):
        rules = '\n[rules]\nrequired_slots = ["gauge", "label.<port>"]\n'
        library = self.library(tmp_path, rules)
        found = lint(library.get("P00001"), library.required_slots)
        assert [(f.location, f.message) for f in found] == [
            ("slots.gauge", "the file has no gauge slot"),
            ("slots.label.in", "the file has no label slot for the port 'in'"),
            ("slots.label.out", "the file has no label slot for the port 'out'"),
        ]

    def test_the_library_carries_what_the_file_declares(self, tmp_path):
        library = self.library(tmp_path, '\n[rules]\nrequired_slots = ["tag"]\n')
        assert library.required_slots == ("tag",)
