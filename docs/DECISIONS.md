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

## D16. What `repeat` does where the guide is silent

Decided: the result lists every node explicitly, one per pole, with the ports prefixed and
`potential` kept; a port in no declared node becomes a one-port node (`nodes_of`), so a symbol
without `nodes` still yields explicit ones. A slot id starting `marking.` is renamed per pole
(`marking.in` -> `marking.2.in`, `marking.c.in` -> `marking.2.c.in`); `tag`, `value` and any other
slot id come from pole 1 only, unprefixed. The dashed link line is normal weight and is appended
after every pole's elements; `lint_allow` is carried over unchanged.
Why: the guide names `tag` and `value` and the `marking.` prefix, and says "nodes and paths repeat
per pole" without saying how implicit nodes are treated.
Cost if wrong: an unknown slot id that should repeat is lost on poles 2..n; resolved JSON of a
repeated symbol lists nodes that were implicit before.

## D17. Structural problems `validate` cannot see are `schema` findings from the resolver

Decided: `validate` does not know a composite from an atomic file, and `repeat` states preconditions
as contracts, so `resolve_library` reports these itself, all as rule `schema`: `repeat` below 1,
above 64 (D22), or on a part whose file has no through path (at `/parts/<i>/repeat`); `ports`
as an array of tables in a file with `parts` (`/ports`); `ports` as a rename table, or a slot
given as a string reference, in a file without `parts` (`/ports`, `/slots/<id>`); two parts with the same `as`
(`/parts/<i>/as`, the later one). A file with any of them has no symbol.
Why: the guide names one rule, `schema`, for "the file fails validation", and `repeat` must not be
called in violation of its contracts.
Cost if wrong: a separate rule id and a fixture for it; a second `validate` pass in the schema.

## D18. What `part-anchor` covers, and where it points

Decided: besides an unknown anchor and anchors that do not face each other (`dA == -dT` after
`orient`), `part-anchor` covers the malformed placements: `to` that is not `part.anchor`, names no
earlier part, or names an anchor the part lacks (`/parts/<i>/to`); an unknown `attach` anchor or
`attach` without `to` (`/parts/<i>/attach`); `via` without `length > 0` (`/parts/<i>/via`); a part
after the first with neither or both of `attach` and `at`, `at` together with `to`, `length` or
`via`, and `to`, `length` or `via` without `attach` (`/parts/<i>`). The first part with none of
these sits at the origin. A negative `length` is placed as written (the guide only bounds it with
`via`). A target that is an anchor of a part that itself failed to place adds no finding.
Why: the guide gives the rule one line; every one of these makes the placement undefined.
Cost if wrong: a finding moves to another rule or location.

## D19. Findings are keyed by file stem, never cascade, and sort deterministically

Decided: `Resolution.symbols` and `.findings` are keyed by file stem (the number, when the
`metadata` rule is clean); `findings` lists only stems that have some. A symbol with only `metadata`
or `id-format` findings still resolves. A file whose part file is unknown, in a cycle, or itself
failed has no symbol, and only the file at fault reports: its users get no finding of their own.
`part-cycle` is reported on every file of the cycle, at the part that leads on, so the result does
not depend on which file the walk reaches first. Order: stems sorted, then rule id, then location
with numbers compared as numbers (`/parts/2` before `/parts/10`), generation order after that.
`metadata` uses `re.search` with the config's pattern, since the guide's pattern anchors itself; a
pattern that does not compile matches nothing.
Why: findings on a user of a broken file only repeat what the broken file already says.
Cost if wrong: users of broken files also list a finding; a stricter `fullmatch` for patterns
without anchors.

## D20. Composite inheritance where the guide is silent

Decided: a composite's own `nodes` entry that restates an inherited node (same port set, in the
composite's port ids) replaces it and carries its `potential`, or the inherited one if it has none;
any other own node is appended, so the linter's `node-invalid` reports it (D12). A part port
exported under two names yields two ports at the same place in one node; paths use the first name.
When several inherited paths are `through` and the composite redeclares none with `through = true`,
the result has no through path (the linter then warns `through-missing`). Inherited paths keep
part order; the composite's own paths follow, and an own path removes the inherited path between
the same two nodes. Elements are ordered part by part, a part's `via` link line before its own
elements, then the composite's own elements.
Why: the guide states the rules of inheritance, not these corners.
Cost if wrong: an order change in resolved JSON; nothing else.

## D21. `load_library` reports what it read, by file

Decided: `load_library` reads `library.toml` and `symbols/*.toml` as UTF-8, files in stem order; a
file that cannot be read (missing, unreadable, not UTF-8, a directory named `x.toml`) and a
missing `symbols/` directory are `schema` findings located at the file or directory name. It
raises one `LibraryError` holding every finding: `library.toml` first, then per file, each message
prefixed `<file name>: ` because a finding has no file of its own. Rule severity comes from the
registry (`lint/registry.py`, `rule_finding`); the eight rules of the resolver are registered, the
remaining 25 come with the linter.
Why: a data repo gate needs to know which file a finding is about.
Cost if wrong: a `file` field on `Finding` instead of a message prefix.

## D22. Every number is bounded, `repeat` is capped, the walk has no recursion limit

Decided: every numeric value in a source or bundle file must be finite with an absolute value of at
most 1e6 module units (1e6 M is 2.5 km). Both validators enforce it and stay in agreement: the
hand-written `validate` tests `not (-1e6 <= x <= 1e6)`, so NaN and infinity fail; the JSON Schema
has `$defs/number` and `$defs/integer` (used by every number and integer key, `pole_pitch` and
`repeat` included) written as `not { anyOf: [exclusiveMinimum 1e6, exclusiveMaximum -1e6] }`,
because jsonschema's `maximum` lets NaN through and this form does not (JSON has no NaN; a TOML
file does). The `schema` constant and the enum-like values are unaffected. The resolver also
rejects a part `repeat` above 64, like `repeat` below 1: a `schema` finding at
`/parts/<i>/repeat`, part not resolved; a direct call of `repeat(symbol, n)` is unchanged. The walk
over part files uses an explicit stack, so a chain of composites of any depth resolves, with no
depth cap; a `part-cycle` message shows the first 8 files of a cycle and `...` when it is longer.
`_matches` in `lint/file.py` treats a pattern that raises `OverflowError` or `RecursionError` as
matching nothing, as it does one that is not a valid regex.
Why: with bounded input all later arithmetic (`orient`, boxes, the coming overlap tests, placement
sums) is total, so the pure core can keep its promise never to raise (D3); `validate` accepted
integers of up to 4300 digits, which overflowed `int + float` in placement and made `repeat` hang.
64 poles is far beyond any real switching device.
Cost if wrong: a larger bound is a one-constant change in `load.py` and the schema; a symbol beyond
2.5 km or a 65-pole device cannot be written until then.

## D23. How `lint` runs the rules, orders findings and treats exemptions

Decided: a rule is one function `(Symbol) -> tuple[Finding, ...]`, one `Rule(id, severity, group,
orientation_dependent)` row in `lint/registry.py` and one entry in `CHECKS` in `lint/__init__.py`.
`run_checks` calls an orientation-dependent rule on `orient(symbol, o)` for the 8 orientations and
stamps `o` on its findings; any other rule runs once, with no orientation. `RULE_IDS` and the sort
order derive from `GUIDE_ORDER`, the 33 ids in the guide table's order (a test reads the table out
of the guide and compares). Findings sort by rule order, then orientation (none first, then R0 to
MR270), then location with numbers as numbers (`anchors[2]` before `elements[0]`, `elements[2]`
before `elements[10]`), then generation order. `lint_allow` removes a rule's findings, of both
severities and in every orientation, and an entry counts as used when the rule fired in any of
them before the removal. `allow-unknown` (a rule id outside the 33, or a reason that is empty
or only whitespace; two findings if both) and `allow-unused` (a known rule that did not fire) are
added afterwards, so they cannot be exempted; an unknown rule is never also unused; a rule of
another task counts as known but has not fired, so it is unused; duplicate entries for one rule are
each judged alone; an entry with an empty reason still exempts and is reported once. A rule the
resolver reports (`schema`, `metadata`, `part-*`, `export-unknown`, and `id-format` of a part id)
never fires in `lint`, so `allow-unused` reports an exemption of it. The package exports the
function `lint`, which shadows the subpackage as an attribute of `graphical_symbols`: write
`from graphical_symbols.lint import ...`, never `import graphical_symbols.lint as m`.
Why: the guide says who loops over orientations nowhere (D6) and leaves the exemption corners open.
Cost if wrong: a change in `ordered`, in `exempt` or in the two exemption functions; a rule row and
a `CHECKS` entry per rule instead of one registration if the two are ever merged.

## D24. What the geometry, id and anchor rules count

Decided: `off-drawing-grid` tests exactly (`value * 8` is integral) every line, polyline and
closed-outline point, circle and arc centre and radius (not arc angles), text position and height,
anchor position, slot point and slot box side; port positions are `port-off-wiring-grid`'s. It
gives one finding per element, anchor or slot, naming every value off the grid, located at
`elements[i]`, `anchors[i]` or `slots.<id>`. `degenerate` also covers a circle or arc radius of
zero or less, an arc whose angles are equal modulo 360, and an element equal to an earlier one,
which is reported at the later copy (three copies give two findings); "equal" is the dataclass
equality of the whole element, so `weight` and `style` count (a reversed line or a dashed copy is
not a duplicate); an element can have more than one finding. Symbol-level `id-format` checks port
ids and anchor ids (`ports[i]`, `anchors[i]`; part ids stay the resolver's).
`point_on_geometry(point, elements, *, endpoints_only)` in `lint/geometry.py` is the one test of "on geometry", tolerance 1e-9: on a line or polyline
segment, on a circle or arc curve (an arc's ends included), on a closed polyline's outline, inside
a filled circle or filled closed polyline (D5); text is not geometry. `anchor-off-geometry` uses
it whole; `endpoints_only` keeps only the ends of a line and of an open polyline, for
`port-off-geometry`. A polyline of one point is a dot; a filled open polyline has no area.
Why: the guide names the quantities but not the granularity of a finding or the corners.
Cost if wrong: locations and message text change; `endpoints_only` moves if ports are meant to
count a polyline's interior vertices.

## C2. `id-format` and `repeat` disagree about port ids

Concern: section 3 says port ids match `^[a-z][a-z0-9_]*$` and the dot is reserved for namespacing,
section 7 says `repeat` makes the ports `1.in`, `2.in`, and section 12 says every symbol with a
through path lints clean as `repeat(symbol, 3)`. `1.in` does not match the pattern, so the three
cannot all hold as written. `repeat` also accepts its own result (it has a through path), and
prefixes `<k>.` again, so `repeat(repeat(S, 2), 2)` has the ports `1.1.in`, `1.2.in`, `2.1.in`,
`2.2.in`. Implemented: a port id is valid if it matches the pattern or is one or more pole numbers
(`[1-9][0-9]*`), each followed by a dot, and then such an id (`(?:[1-9][0-9]*\.)+` and the
pattern, matched in full); anchor ids and part ids get no such form. A source file with an
authored port `2.in` or `1.2.in` therefore passes `id-format`. Owner
to decide: keep this, or have `repeat` be exempt from the id rule some other way (a `lint` that knows
a symbol was repeated, which its signature cannot).

## D25. An arc with a non-finite angle counts as its centre in the boxes

Decided: `element_box` and `body_box` reduce an arc's start and end angle modulo 360 before they
compute its extent, and an arc whose start or end angle is NaN or infinite has no swept extent, so
its extent points are just its centre. Finite angles behave as before.
Why: `arc_point` calls `math.cos` on the angle, which raises for infinity; `body_box` is called by
the linter on hand-built symbols and must be total (D3, D22).
Cost if wrong: a garbage arc shrinks a box to a point instead of being an error; files cannot carry
such angles (D22), so only hand-built symbols are affected. `arc_point` itself still raises for an
infinite angle; the boxes and the linter reduce it first, `svg.py` does not (a bundle cannot carry such an
angle, so only a hand-built symbol could make `to_svg` raise).
