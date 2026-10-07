# Tutorial: your first symbol

This page takes you from an empty folder to a symbol drawn in a web page. You install symdef, make a
symbol set, build and check it, edit a symbol, declare a word of your own, and place the symbol in a page.

## Install

Add the toolkit to a project, or run it once without installing it:

```console
$ uv add symdef
$ uvx symdef --help
```

The rest of this page assumes `symdef` is on your path. Inside a project, put `uv run` in front of it.

## Make a symbol set

A symbol set is a folder of symbol files and one `library.toml`. `symdef init` writes a small one:

```console
$ symdef init my-symbols
wrote my-symbols/library.toml
wrote my-symbols/symbols/resistor.toml
wrote my-symbols/.gitattributes
```

The folder holds three files:

```text
my-symbols/
  library.toml            the set: its name, its words and its rules
  symbols/resistor.toml   one symbol; the file name is its reference number
  .gitattributes          keeps line ends as LF
```

`init` stops with exit code 1 and writes nothing if any of these files already exists.

## The set file

`library.toml` names your set and declares the words its symbols may use.

<!-- shows: my-symbols/library.toml -->
```toml
#:schema https://olejbondahl.github.io/symdef/symbol.schema.json
standard = "My symbols"
title = "My symbols"
number_pattern = '^[a-z][a-z0-9-]*$'

[vocabulary]
path_kinds = ["conductor", "impedance"]
potentials = []
links = []

[rules]
required_slots = ["tag", "marking.<port>"]
```

- `standard` is the name of the standard or house style the set follows. It can be any text.
- `number_pattern` is a regular expression every reference number must match.
- `[vocabulary]` lists the words your symbols may use: path kinds, node potentials and links.
  The toolkit has no built-in list, so a word you do not declare is an error.
- `required_slots` lists the text slots every symbol must have. `marking.<port>` means one slot per port.

The first line is an editor hint. An editor that reads `#:schema` fetches the schema and then
completes and checks the file as you type.

## The starter symbol

`symbols/resistor.toml` is the whole definition of one symbol.

<!-- shows: my-symbols/symbols/resistor.toml -->
```toml
#:schema https://olejbondahl.github.io/symdef/symbol.schema.json
schema = 1
name = "Resistor"
kind = "symbol"
status = "unverified"
reference = { standard = "My symbols", number = "resistor" }

ports = [
  { id = "in",  at = [0, -2], dir = "N" },
  { id = "out", at = [0, 2],  dir = "S" },
]

paths = [
  { from = "in", to = "out", kind = "impedance", through = true },
]

elements = [
  { line = [[0, -2], [0, -1]] },
  { line = [[0, 2], [0, 1]] },
  { polyline = [[-0.5, -1], [0.5, -1], [0.5, 1], [-0.5, 1]], closed = true },
]

[slots]
tag           = { at = [-1, 0],      side = "W", box = [6, 1] }
"marking.in"  = { at = [0.75, -1.5], side = "E", box = [1.5, 1] }
"marking.out" = { at = [0.75, 1.5],  side = "E", box = [1.5, 1] }
```

Each part has a job:

- **Ports** are the places where a wire may attach. Each has an id, a position `at` and a direction `dir`.
  Positions are in modules, a fixed length of 2.5 mm. Ids name a role, such as `in`, not a terminal number.
- **Paths** say what connects the ports. This one links `in` to `out` with the word `impedance`,
  and `through = true` marks it as a path that continues through the symbol.
- **Elements** are the drawing: lines and polylines in module units.
- **Slots** are boxes the symbol reserves for text. `tag` is for the designation, and `marking.in` is the text beside port `in`.

The interface spec, [SYMBOL_INTERFACE.html](SYMBOL_INTERFACE.html), defines every field, rule and
orientation in full.

## Build and check

`symdef build` loads the set, lints every symbol and writes the build:

```console
$ symdef build my-symbols
wrote 5 files
```

The build holds a resolved JSON file, a plain and an annotated SVG for each symbol, a gallery
`README.md`, and `src/mysymbols/bundle.json`, which holds every symbol in one file.
Open `build/annotated/resistor.svg` to see the ports, slots and wire lanes.

`symdef check` runs every gate a set needs: files load, symbols lint clean, and the build matches the source.
No output and exit code 0 mean everything is fine:

```console
$ symdef check my-symbols
```

## Edit the symbol

Make the resistor body wider. This edit replaces the `polyline` line of the symbol file.

<!-- edit: my-symbols/symbols/resistor.toml | find: polyline -->
```toml
  { polyline = [[-0.75, -1], [0.75, -1], [0.75, 1], [-0.75, 1]], closed = true },
```

The build on disk still shows the old body, so `check` reports it as stale:

```console
$ symdef check my-symbols  # exit 1
error stale-build: build/annotated/resistor.svg is stale; run `symdef build`
error stale-build: build/resolved/resistor.json is stale; run `symdef build`
error stale-build: build/svg/resistor.svg is stale; run `symdef build`
error stale-build: src/mysymbols/bundle.json is stale; run `symdef build`
error bundle-differs: resistor: the bundle differs from the source
```

Rebuild, and `check` is quiet again:

```console
$ symdef build my-symbols
wrote 5 files
$ symdef check my-symbols
```

## Declare your own word

Say you draw pipes. A path of your symbol needs the kind `pipe`, which the set does not declare.
Change the kind in the symbol file.

<!-- edit: my-symbols/symbols/resistor.toml | find: kind = "impedance" -->
```toml
  { from = "in", to = "out", kind = "pipe", through = true },
```

The build refuses the word and names it, the file and the line:

```console
$ symdef build my-symbols  # exit 1
error schema [/paths/0/kind]: resistor.toml: path kind 'pipe' is not declared in library.toml [vocabulary] path_kinds (line 14)
```

Declare the word in `[vocabulary]` and build again.

<!-- edit: my-symbols/library.toml | find: path_kinds -->
```toml
path_kinds = ["conductor", "impedance", "pipe"]
```

```console
$ symdef build my-symbols
wrote 5 files
$ symdef check my-symbols
```

A potential (such as `earth`) or a link (a `via` between parts) is declared the same way,
in `potentials` or `links`.

## Put the symbol in a page

The build is plain data. Load the set, turn the symbol, and write an SVG into an HTML page:

```python
from pathlib import Path

from symdef import Orientation, load_library, orient, to_svg

library = load_library(Path("my-symbols"))
resistor = orient(library.get("resistor"), Orientation.R90)
svg = to_svg(resistor, texts={"tag": "R1"})
Path("page.html").write_text(f"<!doctype html>\n<title>My symbols</title>\n{svg}", encoding="utf-8")
```

Open `page.html` in a browser. The resistor lies on its side and the sample text `R1` sits in its tag slot.

A program that only draws does not need the TOML. It reads the bundle instead, and
`to_fragment` gives a `<g>` it can place inside its own drawing:

```python
from symdef import load_bundle, to_fragment

bundle = load_bundle(Path("my-symbols") / "src" / "mysymbols" / "bundle.json")
group = to_fragment(bundle.get("resistor"))
Path("sheet.svg").write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-4 -4 8 8">\n{group}</svg>\n',
    encoding="utf-8",
)
```

## Where next

[The guide](GUIDE.md) covers composite symbols, repeated poles, linting and the build in depth.
The [interface spec](SYMBOL_INTERFACE.html) is the binding definition.
