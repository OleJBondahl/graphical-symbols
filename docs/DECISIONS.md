# Decisions

Where `SYMBOL_INTERFACE.html` (the guide) is silent, decisions are recorded here, one entry each:
what was decided, why, and what it costs if wrong. Concerns about the guide itself are recorded as
`C<n>` entries; the guide is never edited.

## D1. `Symbol` carries a trailing `lint_allow` field

Decided: `Symbol(name, kind, status, reference, elements, ports, nodes, paths, anchors, slots,
pole_pitch, lint_allow)`. The guide's signature stops at `pole_pitch`.
Why: `lint(symbol)` must apply exemptions and report `allow-unknown` / `allow-unused`, and the
resolved JSON carries `lint_allow` ("same schema as the source"), so a loaded bundle needs it.
Cost if wrong: one extra trailing field with an empty default; consumers that construct `Symbol`
positionally up to `pole_pitch` are unaffected.

## D2. Purity split: file IO lives in `build.py`, pure helpers in extra modules

Decided: every module is pure except `build.py`, which holds all file IO, including `load_library`
and `load_bundle` (the guide lists only `write_build` and `stale_build` there, but says `build` is
the only impure module and both load functions read files). Everything they do besides reading is
pure: `load.py` parses text and decoded data, `serialize.py` renders canonical JSON, `gallery.py`
renders the gallery README. `lint/` is a package with one module per rule group.
Why: the purity gate and the guide's "only impure module" rule cannot both hold otherwise.
Cost if wrong: moving two functions and re-exporting them.

## D3. The pure core never raises; problems are `Finding`s

Decided: parsing, validation and resolution return findings (`schema`, `metadata`, `id-format`,
`part-*`, `export-unknown`) instead of raising. `LibraryError` (carrying the findings) is raised
only by `load_library` in `build.py`. `repeat` states its preconditions with `deal.pre`.
Why: CLAUDE.md requires every module-level function in a pure module to be `@deal.pure` and not
raise; findings are also how the guide says composition rules are reported.
Cost if wrong: a consumer wanting exceptions wraps the result.

## D4. The JSON Schema is structural only

Decided: `schema/symbol.schema.json` checks types, required keys, enums, array shapes and "exactly
one shape key". It does not check the id pattern, the grid, positive sizes or the number pattern.
Why: those are lint rules (`id-format`, `off-drawing-grid`, `degenerate`, `metadata`); enforcing
them in the schema would make those rules unreachable from a file.
Cost if wrong: a stricter schema is a compatible tightening later.

## D5. A port on a filled circle or filled closed outline counts as "on geometry"

Decided: for `port-off-geometry`, "on a circle" includes any point of a filled circle's disk, and
"on a closed outline" includes any point of a filled polygon's area.
Why: the guide's connection point S00016 has its ports at the centre of a filled dot and is stated
to pass `port-off-geometry` without an exemption.
Cost if wrong: S00016 would need one more `lint_allow` entry.

## D6. `lint` takes a base-orientation symbol and evaluates 8 orientations itself

Decided: `lint(symbol)` expects a symbol in base orientation. Orientation-invariant rules run once
(`orientation = None`); orientation-dependent geometric rules (`port-on-body-edge`,
`port-lane-clear`, `slot-overlap-body`, `slot-overlap-slot`) run on `orient(symbol, o)` for all 8
`o` and report the orientation. Base-orientation-only rules (`through-axis`, `pitch-overflow`)
run once. A `lint_allow` entry exempts a rule in every orientation and counts as used if the rule
fired in at least one.
Why: the guide requires "all 8 orientations" and gates "lints clean in all 8 orientations" without
saying who loops.
Cost if wrong: a data repo loops `orient` itself; findings would then carry no new information.

## D7. Bundle keys are exactly the guide's; a loaded bundle has a bare `Library`

Decided: `bundle.json` is `{"schema": 1, "standard": ..., "symbols": {...}}` and nothing else.
`load_bundle` returns `Library(standard, title=standard, number_pattern="", symbols)`.
Why: the guide fixes the bundle format exactly; `title` and `number_pattern` come from
`library.toml`, which the bundle does not ship.
Cost if wrong: two extra keys in the bundle and one in `load_bundle`.

## D8. The bundle package name is the normalised standard

Decided: `src/<package>/bundle.json`, with `<package>` = the standard lowercased with every
non-alphanumeric character removed (`IEC 60617` -> `iec60617`, `ISA 5.1` -> `isa51`).
Why: `write_build(library, root)` gets no package name and `library.toml` has no key for it.
Cost if wrong: an optional `package` key in `library.toml`; a rename of the output directory.

## D9. Small API shape decisions

- `Slot.box` is a `(width, height)` tuple; `slot_box(slot)` returns the resolved `Box`.
- `Text` has no `anchor` field (guide: always middle-anchored, always upright) and carries `weight`
  so an element round-trips through the file format losslessly; it is not rendered with it.
- `to_svg` has no `margin` parameter (the guide's signature has none); the margin is a constant.
- The old `Anchor` text-anchor enum is removed; `Anchor` is the composition attachment point.
- `InvalidSymbolError` and `DuplicateSymbolError` are removed with the registry they served.
  `UnknownSymbolError` stays for `Library.get`.

## D10. Fixture layout

Decided: `tests/fixtures/guide/` is a mini data repo (`library.toml`, `symbols/`) holding the five
guide examples verbatim plus `S00171` (the qualifier the push-button example uses; the guide names
it but does not define it, so its geometry is ours). A test compares each verbatim file with its
code block in the guide. `tests/fixtures/broken/<rule-id>/` holds one broken mini library per lint
rule (`symbols/S00001.toml` is the failing file); `tests/fixtures/broken/library.toml` is the
default library config.
Why: `metadata` needs a file stem that matches a number pattern, and composition rules need
sibling files, so one directory per rule is uniform.
Cost if wrong: renames.

## D11. Resolved JSON is explicit

Decided: resolved JSON writes every element key that has a default (`weight`, `style`, `closed`,
`fill`) and every port `description`, so a consumer in another language needs no defaults. Keys
whose default is "absent" (`potential`, `edition`, `form`, `pole_pitch`, `lint_allow` when empty)
are omitted.
Why: the guide says consumers "never implement composition" and should be about thirty lines.
Cost if wrong: byte-level diff of every generated file.

## D12. Composite `nodes`

Decided: a composite's own `nodes` entries may only restate an inherited node (same port set) to
add a `potential`; any other node declaration in a composite is a `node-invalid` finding.
Why: the guide defers merging parts' nodes (section 14) and is silent on composite `nodes`.
Cost if wrong: one more inheritance rule.

## C1. Guide example S00254 (push-button) fails `pitch-overflow` as written

Concern: `S00254` declares no `pole_pitch`, so its pitch is 4. Its flattened body extends from
x = -2.5 or further (the dashed link from the contact's `link` anchor at (-0.5, 0) runs 2 M west to
(-2.5, 0), and the actuator sits at that end), and the inherited marking slots reach x = 1.75. The
extent from section 8 point 6 is therefore at least 4.25 M, more than 4, so `pitch-overflow` fires.
The guide says the five examples "must load and lint clean" and that only the four atomic ones were
machine-checked. Implemented as written; the guide-verbatim fixture is expected to produce exactly
that one finding, and a variant with `pole_pitch = 8` is clean. Owner to decide: add `pole_pitch = 8`
to the example, or shorten the link.

## D13. Box and angle edge cases the guide leaves open

Decided: a symbol without elements has the body box `Box(Point(0, 0), Point(0, 0))`, so its keep-out
box still contains the origin; an element with no points (a polyline with none) has that same origin
box as `element_box` but adds nothing to `body_box`; `orient` normalises arc angles into [0, 360)
under every orientation, `R0` included, so `R0` is the identity only for symbols whose arcs are
already normalised.
Why: `body_box` must not raise on malformed symbols (the linter reports them), and section 3 says
angles are normalised to [0, 360) without exempting `R0`.
Cost if wrong: a slot-only symbol's keep-out box grows to the origin; a symbol with an arc at
-90 or 360 reads back as 270 or 0 after `orient(symbol, R0)`.

## D14. File-format gaps the schema had to close

Decided: the schema (and `validate`) require `height` on a text element; `fill` on a circle,
`closed` and `fill` on a polyline, `weight` and `style` are optional with the defaults the model
already has. A file must contain `elements`, `parts` or both. `ports` is never required. `slots` is
required when `kind = "symbol"`, as section 4's key table says (an empty `[slots]` table satisfies
it; a symbol whose `[slots]` lacks `tag` or a marking still reads and trips the `slot-missing` lint).
Reversal: the first version of this entry made `slots` never required, which deviated from the guide
without need; the schema now has `if kind = "symbol" then required slots`, and `validate` the same.
`schema`, `pole_pitch` and `repeat` accept integral floats (`8.0`), as JSON Schema's `integer` does.
`repeat >= 1` is not a schema rule; the resolver must report it. Unknown keys are errors on every
table; the only extra top-level keys are the resolved form's `body_box` and `keepout_box`.
Why: the guide shows `height` in every text example and gives it no default; the rest follows
section 4 and D4.
Cost if wrong: `height` optional (default 1) is a compatible loosening; the rest is unchanged.

## D15. Reading reports through `schema` findings with pointer locations

Decided: every reading problem is a `Finding(rule="schema", ERROR)`: TOML syntax errors, schema
violations, and `library.toml` problems (missing or non-string `standard`, `title`,
`number_pattern`; a pattern that does not compile). `location` is a JSON Pointer such as
`/ports/0/dir`, with `~` and `/` in keys escaped; a problem with the whole file has `location =
None`. `library.toml` may carry unknown keys; they are ignored.
Why: the guide names only the `schema` rule for "the file fails validation" and says nothing of the
config file; one rule keeps `LibraryError` messages uniform.
Cost if wrong: a separate `config` rule id and a check that ignores unknown keys becoming strict.
