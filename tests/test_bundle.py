"""Reading a bundle: `library_from_bundle`, `parse_json`, `validate_bundle` and `load_bundle`."""

import json
from pathlib import Path

import pytest
from roundtrip import normalised

import graphical_symbols
from graphical_symbols.build import load_bundle, load_library, stale_build, write_build
from graphical_symbols.errors import LibraryError
from graphical_symbols.load import library_from_bundle, parse_json, validate_bundle
from graphical_symbols.model import Library
from graphical_symbols.serialize import bundle_to_data, to_json

GUIDE = Path(__file__).resolve().parent / "fixtures" / "guide"
LIBRARY = load_library(GUIDE)
BUNDLE = "src/iec60617/bundle.json"


def bundle_data() -> dict:
    """A fresh, mutable bundle of the guide library, as decoded JSON."""
    return json.loads(to_json(bundle_to_data(LIBRARY)))


def bundle_file(tmp_path: Path, data) -> Path:
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestLibraryFromBundle:
    def test_it_gives_a_bare_library_of_the_same_symbols(self):
        library = library_from_bundle(bundle_data())
        assert isinstance(library, Library)
        assert (library.standard, library.title, library.number_pattern) == (
            "IEC 60617",
            "IEC 60617",
            "",
        )
        assert sorted(library.symbols) == sorted(LIBRARY.symbols)
        for number, symbol in LIBRARY.symbols.items():
            assert library.symbols[number] == normalised(symbol)

    def test_iteration_is_sorted_by_number(self):
        library = library_from_bundle(bundle_data())
        assert [s.reference.number for s in library] == sorted(LIBRARY.symbols)


class TestParseJson:
    def test_it_decodes_json(self):
        assert parse_json('{"a": [1, 2.5]}') == ({"a": [1, 2.5]}, ())

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("", id="empty"),
            pytest.param("{", id="unclosed"),
            pytest.param("nope", id="word"),
            pytest.param('{"a": 1,}', id="trailing comma"),
            pytest.param("[" * 100_000, id="nested too deeply"),
            pytest.param("1" * 5000, id="integer of 5000 digits"),
        ],
    )
    def test_text_that_is_not_json_is_a_schema_finding_not_an_exception(self, text):
        data, (finding,) = parse_json(text)
        assert data is None
        assert (finding.rule, finding.location) == ("schema", None)
        assert finding.message.startswith("invalid JSON: ")


class TestValidateBundle:
    def test_the_bundle_of_the_guide_library_is_valid(self):
        assert validate_bundle(bundle_data()) == ()

    def test_a_bundle_with_no_symbols_is_valid(self):
        assert validate_bundle({"schema": 1, "standard": "X", "symbols": {}}) == ()

    @pytest.mark.parametrize("data", [None, [], "x", 1])
    def test_a_bundle_must_be_a_table(self, data):
        (finding,) = validate_bundle(data)
        assert (finding.rule, finding.location) == ("schema", None)

    @pytest.mark.parametrize("key", ["schema", "standard", "symbols"])
    def test_every_top_level_key_is_required(self, key):
        data = bundle_data()
        del data[key]
        (finding,) = validate_bundle(data)
        assert key in finding.message

    def test_the_schema_version_must_be_one(self):
        data = bundle_data()
        data["schema"] = 2
        (finding,) = validate_bundle(data)
        assert finding.location == "/schema"

    def test_unknown_top_level_keys_are_rejected(self):
        data = bundle_data()
        data["title"] = "x"
        (finding,) = validate_bundle(data)
        assert finding.location == "/title"

    def test_the_standard_must_be_a_string(self):
        data = bundle_data()
        data["standard"] = 1
        (finding,) = validate_bundle(data)
        assert finding.location == "/standard"

    def test_a_symbol_that_fails_validation_is_located_inside_the_bundle(self):
        data = bundle_data()
        data["symbols"]["S00227"]["ports"][0]["dir"] = "up"
        (finding,) = validate_bundle(data)
        assert (finding.rule, finding.location) == ("schema", "/symbols/S00227/ports/0/dir")

    def test_a_whole_symbol_problem_is_located_at_the_symbol(self):
        data = bundle_data()
        del data["symbols"]["S00227"]["elements"]
        (finding,) = validate_bundle(data)
        assert finding.location == "/symbols/S00227"

    def test_a_symbol_that_is_not_a_table_is_reported(self):
        data = bundle_data()
        data["symbols"]["S00227"] = 3
        (finding,) = validate_bundle(data)
        assert finding.location == "/symbols/S00227"

    def test_a_bundle_symbol_must_be_resolved(self):
        data = bundle_data()
        symbol = data["symbols"]["S00227"]
        symbol["parts"] = []
        symbol["ports"] = {"in": "x.in"}
        symbol["slots"]["tag"] = "x.tag"
        locations = {f.location for f in validate_bundle(data)}
        assert locations == {
            "/symbols/S00227/parts",
            "/symbols/S00227/ports",
            "/symbols/S00227/slots/tag",
        }

    @pytest.mark.parametrize("key", ["../x", "a/b", "a\\b", "", "S 1", "a.b", ".."])
    def test_a_key_that_is_not_a_file_name_stem_is_reported(self, key):
        data = bundle_data()
        data["symbols"][key] = data["symbols"].pop("S00227")
        (finding,) = validate_bundle(data)
        assert finding.location == f"/symbols/{key.replace('/', '~1')}"
        assert "file name" in finding.message

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), 1e7])
    def test_numbers_are_bounded_like_in_a_source_file(self, value):
        data = bundle_data()
        data["symbols"]["S00227"]["body_box"][0][0] = value
        (finding,) = validate_bundle(data)
        assert finding.location == "/symbols/S00227/body_box/0/0"


class TestLoadBundle:
    def test_a_written_bundle_loads_as_the_library_it_was_built_from(self, tmp_path):
        write_build(LIBRARY, tmp_path)
        loaded = load_bundle(tmp_path / BUNDLE)
        assert loaded.standard == LIBRARY.standard
        assert sorted(loaded.symbols) == sorted(LIBRARY.symbols)
        for number, symbol in LIBRARY.symbols.items():
            assert loaded.get(number) == normalised(symbol)

    def test_a_loaded_bundle_builds_the_same_files(self, tmp_path):
        write_build(LIBRARY, tmp_path)
        assert stale_build(load_bundle(tmp_path / BUNDLE), tmp_path) == ()

    def test_it_is_exported_by_the_package(self):
        assert graphical_symbols.load_bundle is load_bundle

    def test_a_missing_file_raises_library_error(self, tmp_path):
        with pytest.raises(LibraryError) as raised:
            load_bundle(tmp_path / "nope.json")
        (finding,) = raised.value.findings
        assert (finding.rule, finding.location) == ("schema", "nope.json")
        assert finding.message.startswith("nope.json: ")

    def test_a_directory_raises_library_error(self, tmp_path):
        with pytest.raises(LibraryError):
            load_bundle(tmp_path)

    def test_bytes_that_are_not_utf8_raise_library_error(self, tmp_path):
        path = tmp_path / "bundle.json"
        path.write_bytes(b'{"schema": \xff}')
        with pytest.raises(LibraryError):
            load_bundle(path)

    @pytest.mark.parametrize("text", ["", "{", "null"])
    def test_invalid_json_raises_library_error(self, tmp_path, text):
        path = tmp_path / "bundle.json"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(LibraryError) as raised:
            load_bundle(path)
        assert all(f.rule == "schema" for f in raised.value.findings)
        assert all(f.message.startswith("bundle.json: ") for f in raised.value.findings)

    def test_a_wrong_schema_version_raises_library_error(self, tmp_path):
        data = bundle_data()
        data["schema"] = 2
        with pytest.raises(LibraryError) as raised:
            load_bundle(bundle_file(tmp_path, data))
        (finding,) = raised.value.findings
        assert finding.location == "/schema"

    def test_a_symbol_failing_validation_raises_library_error_naming_it(self, tmp_path):
        data = bundle_data()
        del data["symbols"]["S00227"]["name"]
        with pytest.raises(LibraryError) as raised:
            load_bundle(bundle_file(tmp_path, data))
        (finding,) = raised.value.findings
        assert finding.location == "/symbols/S00227"
        assert "'name'" in finding.message

    def test_every_problem_is_reported_at_once(self, tmp_path):
        data = bundle_data()
        data["schema"] = 2
        data["symbols"]["S00227"]["kind"] = "thing"
        data["symbols"]["S00016"]["status"] = "maybe"
        with pytest.raises(LibraryError) as raised:
            load_bundle(bundle_file(tmp_path, data))
        assert sorted(str(f.location) for f in raised.value.findings) == [
            "/schema",
            "/symbols/S00016/status",
            "/symbols/S00227/kind",
        ]
