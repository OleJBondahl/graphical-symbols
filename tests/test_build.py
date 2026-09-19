"""`write_build` and `stale_build`: what a build writes, and what counts as out of date."""

import shutil
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

import graphical_symbols
from graphical_symbols.build import load_library, stale_build, write_build
from graphical_symbols.geometry import Direction, Line, Point, Text
from graphical_symbols.model import Library, Port, Slot, Status
from graphical_symbols.serialize import build_files, package_name

TESTS = Path(__file__).resolve().parent
GUIDE = TESTS / "fixtures" / "guide"
EXPECTED = TESTS / "fixtures" / "expected"
LIBRARY = load_library(GUIDE)
NUMBERS = sorted(LIBRARY.symbols)

RESOLVED = "build/resolved/S00227.json"
SVG = "build/svg/S00227.svg"
ANNOTATED = "build/annotated/S00227.svg"
README = "build/README.md"
BUNDLE = "src/iec60617/bundle.json"


def relative(paths, root):
    return [p.relative_to(root).as_posix() for p in paths]


def edited(**changes) -> Library:
    """The guide library with S00227 changed."""
    symbols = {**LIBRARY.symbols, "S00227": replace(LIBRARY.get("S00227"), **changes)}
    return replace(LIBRARY, symbols=symbols)


@pytest.fixture
def built(tmp_path) -> Path:
    write_build(LIBRARY, tmp_path)
    return tmp_path


class TestPackageName:
    @pytest.mark.parametrize(
        ("standard", "package"),
        [("IEC 60617", "iec60617"), ("ISA 5.1", "isa51"), ("ISO 14617", "iso14617")],
    )
    def test_the_standard_lowercased_without_non_alphanumerics(self, standard, package):
        assert package_name(standard) == package


class TestBuildFiles:
    def test_the_paths_are_the_layout_of_the_guide(self):
        paths = list(build_files(LIBRARY))
        expected = [
            *(
                f"build/{d}/{n}.{e}"
                for d, e in (("resolved", "json"), ("svg", "svg"), ("annotated", "svg"))
                for n in NUMBERS
            ),
            README,
            BUNDLE,
        ]
        assert sorted(paths) == sorted(expected)
        assert paths == sorted(paths)

    def test_the_values_are_bytes_without_carriage_returns_and_end_in_one_newline(self):
        for data in build_files(LIBRARY).values():
            assert isinstance(data, bytes)
            assert b"\r" not in data
            assert data.endswith(b"\n")
            assert not data.endswith(b"\n\n")

    def test_it_is_deterministic(self):
        assert build_files(LIBRARY) == build_files(load_library(GUIDE))

    def test_a_lone_surrogate_in_a_name_does_not_raise(self):
        files = build_files(edited(name="a\ud800b"))
        assert b"a?b" in files[README]


class TestWriteBuild:
    def test_it_writes_every_file_of_the_layout_and_returns_the_paths_in_order(self, tmp_path):
        written = write_build(LIBRARY, tmp_path)
        assert relative(written, tmp_path) == sorted(build_files(LIBRARY))
        assert all(p.is_file() for p in written)
        assert all(p.is_relative_to(tmp_path) for p in written)

    def test_it_writes_exactly_the_bytes_of_build_files(self, tmp_path):
        for path in write_build(LIBRARY, tmp_path):
            assert path.read_bytes() == build_files(LIBRARY)[path.relative_to(tmp_path).as_posix()]

    def test_the_resolved_json_of_the_make_contact_is_the_reviewed_file(self, built):
        assert (built / RESOLVED).read_bytes() == (EXPECTED / "S00227.json").read_bytes()

    def test_no_written_byte_is_a_carriage_return(self, built):
        for path in built.rglob("*"):
            if path.is_file():
                assert b"\r" not in path.read_bytes(), path

    def test_two_builds_are_byte_identical(self, tmp_path):
        first, second = tmp_path / "a", tmp_path / "b"
        write_build(LIBRARY, first)
        write_build(LIBRARY, first)
        write_build(LIBRARY, second)
        files = {p.relative_to(first) for p in first.rglob("*") if p.is_file()}
        assert files == {p.relative_to(second) for p in second.rglob("*") if p.is_file()}
        assert files
        for relative_path in files:
            assert (first / relative_path).read_bytes() == (second / relative_path).read_bytes()

    def test_paths_are_under_the_root_as_given_relative_if_the_root_is(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        root = Path("out")
        written = write_build(LIBRARY, root)
        assert written == tuple(root / rel for rel in sorted(build_files(LIBRARY)))
        assert not any(p.is_absolute() for p in written)
        (root / SVG).unlink()
        assert stale_build(LIBRARY, root) == (root / SVG,)

    @pytest.mark.parametrize(
        "number", ["../../x", "a/b", "a\\b", "", "..", "a..b", ".a", "a.", "S 1"]
    )
    def test_it_refuses_a_number_that_is_not_a_file_name_stem_and_writes_nothing(
        self, tmp_path, number
    ):
        symbols = {**LIBRARY.symbols, number: LIBRARY.get("S00227")}
        with pytest.raises(ValueError, match="file name"):
            write_build(replace(LIBRARY, symbols=symbols), tmp_path / "repo")
        assert not (tmp_path / "repo").exists()
        assert list(tmp_path.rglob("*")) == []

    def test_it_accepts_numbers_with_interior_dots(self, tmp_path):
        symbols = {"5.1": LIBRARY.get("S00227"), "ISO-14617-1.1": LIBRARY.get("S00016")}
        written = write_build(replace(LIBRARY, symbols=symbols), tmp_path)
        assert tmp_path / "build" / "resolved" / "5.1.json" in written

    def test_the_bundle_goes_to_the_package_of_the_standard(self, built):
        assert (built / BUNDLE).is_file()

    def test_it_creates_missing_directories_and_leaves_other_files_alone(self, tmp_path):
        root = tmp_path / "deep" / "repo"
        (root / "build").mkdir(parents=True)
        (root / "build" / "keep.txt").write_bytes(b"mine")
        write_build(LIBRARY, root)
        assert (root / "build" / "keep.txt").read_bytes() == b"mine"

    def test_it_never_deletes_a_stale_extra(self, built):
        extra = built / "build" / "resolved" / "S99999.json"
        extra.write_bytes(b"{}\n")
        write_build(LIBRARY, built)
        assert extra.is_file()

    def test_it_overwrites_a_changed_file(self, built):
        (built / RESOLVED).write_bytes(b"changed")
        write_build(LIBRARY, built)
        assert stale_build(LIBRARY, built) == ()

    def test_the_svg_files_are_the_renderings_of_the_symbols(self, built):
        text = (built / SVG).read_text(encoding="utf-8")
        assert text.startswith("<svg ")
        assert 'class="annotation"' not in text
        assert 'class="annotation"' in (built / ANNOTATED).read_text(encoding="utf-8")

    def test_the_annotated_svg_shows_the_sample_texts_and_the_plain_svg_shows_none(self, built):
        plain = ET.fromstring((built / SVG).read_bytes())  # noqa: S314 - our own output
        assert not [e for e in plain.iter() if e.get("class") == "sample-text"]
        annotated = ET.fromstring((built / ANNOTATED).read_bytes())  # noqa: S314 - our own output
        texts = [e.text for e in annotated.iter() if e.get("class") == "sample-text"]
        # Slots are drawn in id order. S00227 has no value slot, so the value sample is not drawn.
        assert texts == ["1", "2", "-X1"]

    def test_a_value_slot_gets_the_value_sample(self, tmp_path):
        base = LIBRARY.get("S00227")
        value = Slot("value", Point(1, 0), Direction.E, (2, 1))
        library = edited(slots=(*base.slots, value))
        write_build(library, tmp_path)
        annotated = ET.fromstring((tmp_path / ANNOTATED).read_bytes())  # noqa: S314
        texts = [e.text for e in annotated.iter() if e.get("class") == "sample-text"]
        assert texts == ["1", "2", "-X1", "10 A"]


class TestStaleBuild:
    def test_a_fresh_build_is_not_stale(self, built):
        assert stale_build(LIBRARY, built) == ()

    def test_a_missing_build_reports_every_file(self, tmp_path):
        assert relative(stale_build(LIBRARY, tmp_path), tmp_path) == sorted(build_files(LIBRARY))

    def test_a_geometry_change_reports_exactly_the_files_that_show_it(self, built):
        library = edited(
            elements=(*LIBRARY.get("S00227").elements, Line(Point(0, 0), Point(-2, 0)))
        )
        assert relative(stale_build(library, built), built) == sorted(
            [RESOLVED, SVG, ANNOTATED, BUNDLE]
        )

    def test_a_status_change_reports_the_json_the_readme_and_the_bundle(self, built):
        library = edited(status=Status.VERIFIED)
        assert relative(stale_build(library, built), built) == sorted([RESOLVED, README, BUNDLE])

    def test_a_name_change_reports_everything_that_shows_the_name(self, built):
        library = edited(name="Another name")
        assert relative(stale_build(library, built), built) == sorted(
            [RESOLVED, SVG, ANNOTATED, README, BUNDLE]
        )

    def test_a_deleted_file_is_reported(self, built):
        (built / SVG).unlink()
        assert relative(stale_build(LIBRARY, built), built) == [SVG]

    def test_a_deleted_directory_reports_its_files(self, built):
        shutil.rmtree(built / "build" / "annotated")
        assert relative(stale_build(LIBRARY, built), built) == sorted(
            f"build/annotated/{n}.svg" for n in NUMBERS
        )

    @pytest.mark.parametrize("directory", ["resolved", "svg", "annotated"])
    def test_an_extra_file_in_a_generated_directory_is_reported(self, built, directory):
        extra = built / "build" / directory / "S99999.json"
        extra.write_bytes(b"{}\n")
        assert relative(stale_build(LIBRARY, built), built) == [f"build/{directory}/S99999.json"]

    def test_an_extra_file_in_a_subdirectory_of_a_generated_directory_is_reported(self, built):
        nested = built / "build" / "svg" / "old"
        nested.mkdir()
        (nested / "S1.svg").write_bytes(b"<svg/>\n")
        assert relative(stale_build(LIBRARY, built), built) == ["build/svg/old/S1.svg"]

    def test_a_symbol_removed_from_the_library_leaves_its_files_stale(self, built):
        symbols = {n: s for n, s in LIBRARY.symbols.items() if n != "S00016"}
        library = replace(LIBRARY, symbols=symbols)
        assert relative(stale_build(library, built), built) == sorted(
            [
                "build/resolved/S00016.json",
                "build/svg/S00016.svg",
                "build/annotated/S00016.svg",
                README,
                BUNDLE,
            ]
        )

    def test_one_changed_byte_is_reported(self, built):
        data = bytearray((built / ANNOTATED).read_bytes())
        data[len(data) // 2] ^= 1
        (built / ANNOTATED).write_bytes(bytes(data))
        assert relative(stale_build(LIBRARY, built), built) == [ANNOTATED]

    def test_crlf_line_endings_are_reported(self, built):
        (built / README).write_bytes((built / README).read_bytes().replace(b"\n", b"\r\n"))
        assert relative(stale_build(LIBRARY, built), built) == [README]

    def test_a_trailing_byte_is_reported(self, built):
        (built / BUNDLE).write_bytes((built / BUNDLE).read_bytes() + b"\n")
        assert relative(stale_build(LIBRARY, built), built) == [BUNDLE]

    def test_a_directory_where_a_file_belongs_is_reported(self, built):
        (built / README).unlink()
        (built / README).mkdir()
        assert relative(stale_build(LIBRARY, built), built) == [README]

    def test_files_outside_the_generated_paths_are_left_alone(self, built):
        (built / "build" / "notes.txt").write_bytes(b"x")
        (built / "src" / "iec60617" / "__init__.py").write_bytes(b"")
        (built / "symbols").mkdir()
        (built / "symbols" / "S00227.toml").write_bytes(b"")
        assert stale_build(LIBRARY, built) == ()

    @pytest.mark.parametrize("number", ["../../x", "a/b", "", "a..b"])
    def test_it_refuses_a_number_that_is_not_a_file_name_stem(self, tmp_path, number):
        symbols = {**LIBRARY.symbols, number: LIBRARY.get("S00227")}
        with pytest.raises(ValueError, match="file name"):
            stale_build(replace(LIBRARY, symbols=symbols), tmp_path)

    def test_the_result_is_sorted_under_the_root_and_writing_clears_it(self, built):
        (built / SVG).unlink()
        (built / RESOLVED).write_bytes(b"x")
        stale = stale_build(LIBRARY, built)
        assert stale == tuple(built / rel for rel in sorted([RESOLVED, SVG]))
        write_build(LIBRARY, built)
        assert stale_build(LIBRARY, built) == ()


ODD_NAMES = [
    "a\rb",
    "a\r\nb",
    "\r",
    "&<>\"'",
    "a\x00b",
    "a\ud800b",
    "\udfff\ud800",
    "\U000000e9\U00002713\U0001f600",
]


class TestOddText:
    """A name, a text element or a port id can carry anything TOML can spell."""

    @staticmethod
    def library(odd) -> Library:
        base = LIBRARY.get("S00227")
        symbol = replace(
            base,
            name=odd,
            elements=(*base.elements, Text(odd, Point(0, 0), 0.5)),
            ports=(*base.ports, Port(odd, Point(3, 0), Direction.E)),
        )
        return replace(LIBRARY, symbols={**LIBRARY.symbols, "S00227": symbol})

    @pytest.mark.parametrize("odd", ODD_NAMES)
    def test_no_file_has_a_carriage_return_every_svg_parses_and_the_build_is_not_stale(
        self, tmp_path, odd
    ):
        library = self.library(odd)
        written = write_build(library, tmp_path)
        assert stale_build(library, tmp_path) == ()
        for path in written:
            data = path.read_bytes()
            assert b"\r" not in data, path
            if path.suffix == ".svg":
                ET.fromstring(data)  # noqa: S314 - parses this library's own output


def test_the_package_exports_the_build_functions():
    assert graphical_symbols.write_build is write_build
    assert graphical_symbols.stale_build is stale_build
