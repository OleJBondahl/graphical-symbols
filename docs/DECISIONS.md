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
them in the schema would make those rules unreachable from a file. The schema carries no `$id`,
because the guide names no canonical host for it; a consumer refers to the file by path.
Cost if wrong: a stricter schema is a compatible tightening later; an `$id` is one added key.

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
- `Library` is a frozen dataclass that holds a mutable `Mapping`, so `hash(library)` raises
  `TypeError`. A library is never used as a key or in a set, so it stays as it is; the mapping a
  caller hands in stays theirs to change. Cost if wrong: `MappingProxyType` in `load_library` and
  `library_from_bundle`.

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
Computed with the fixture `S00171` (its geometry is ours, D10; its push bar runs 0.75 M west of its
`link` anchor): the body box spans x from -3.25 to 0, the slot boxes other than `tag` reach
x = 1.75, and the extent is exactly 5.0 M against the pitch of 4 (`tests/test_guide_lint.py`
asserts this). With `pole_pitch = 8` the example lints clean.
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
not depend on which file the walk reaches first. Order: stems sorted, then the finding order of
D34, generation order after that.
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
elements, then the composite's own elements. The composite keeps its own `lint_allow`,
`pole_pitch`, `status` and `kind` and drops its parts' (`resolve._compose`): guide section 7's
inheritance list covers ports, nodes and paths, anchors, slots and elements and is silent on these
four. Section 7 also says the composite "must redeclare the one that stays" when several inherited
paths are `through`; that is enforced only as the `through-missing` warning, which is what the
guide's own rule table makes of it (a warning), not as an error.
Why: the guide states the rules of inheritance, not these corners.
Cost if wrong: an order change in resolved JSON; nothing else.

## D21. `load_library` reports what it read, by file

Decided: `load_library` reads `library.toml` and `symbols/*.toml` as UTF-8, files in stem order; a
file that cannot be read (missing, unreadable, not UTF-8, a directory named `x.toml`) and a
missing `symbols/` directory are `schema` findings located at the file or directory name. It
raises one `LibraryError` holding every finding: `library.toml` first, then per file, each message
prefixed `<file name>: ` because a finding has no file of its own. Rule severity comes from the
registry (`lint/registry.py`, `rule_finding`): the eight resolver rules were registered with the
resolver, the linter's other 25 rules were added later, and all 33 are in one table.
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
added afterwards, so they cannot be exempted; an unknown rule is never also unused; a known rule
that does not apply to the symbol (`slot-missing` on an element) did not fire, so it is unused;
duplicate entries for one rule are each judged alone; an entry with an empty reason still exempts
and is reported once. A rule only the resolver reports (`schema`, `metadata`, `part-unknown`,
`part-cycle`, `part-anchor`, `part-port-unexported`, `export-unknown`; `RESOLVER_RULES` in
`lint/registry.py`) never fires in `lint` and the resolver does not read `lint_allow`, so an
exemption naming one changes nothing and is not reported as unused (C3). `id-format` is not in
that set: `lint` runs it on a symbol's own ids, so an `id-format` exemption is judged like any
other (one aimed at a part id is reported unused, since only the resolver reports those). The
package exports the function `lint`, which shadows the subpackage as an attribute of
`graphical_symbols`: write `from graphical_symbols.lint import ...`, never
`import graphical_symbols.lint as m`.
Why: the guide says who loops over orientations nowhere (D6) and leaves the exemption corners open.
Cost if wrong: a change in `ordered`, in `exempt` or in the two exemption functions; a rule row and
a `CHECKS` entry per rule instead of one registration if the two are ever merged.

## D24. What the geometry, id and anchor rules count

Decided: `off-drawing-grid` tests exactly (`value * 8` is integral) every line, polyline and
closed-outline point, circle and arc centre and radius (not arc angles), text position and height,
anchor position, slot point and slot box side; port positions are `port-off-wiring-grid`'s. The
exact test is deliberately not `units.on_grid`, which is public and tolerant (1e-9): a consumer that
pre-checks with `on_grid` can accept a value the rule then rejects. It
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
such angles (D22), so only hand-built symbols are affected. `arc_point` used to raise for an
infinite angle; since D32 it returns the centre, and the rule above stays in the boxes.

## D26. How overlap is computed and what the wire lane is clipped to

Decided: `lint/overlap.py` tests a shape against an open rectangle (a slot box or a lane). A line and
each segment of a polyline are tested exactly, with `Fraction`s, so touching is decided without
rounding; a circle is tested by squared distances (outline: nearest point closer than the radius,
farthest point farther; filled: nearest point closer), which are exact on the grid; an arc is cut at
the angles where its circle crosses the four lines of the rectangle and at its ends, and the middle
of each piece must be more than 1e-9 inside every edge (only the arc uses the tolerance). A closed
polyline is its outline, and if filled also its area by the even-odd rule (an outline that misses
the rectangle leaves the rectangle wholly inside or wholly outside, so its centre decides); an open
polyline is only its segments, however it is filled; a polyline of one point is a dot. A circle or
arc whose radius is not positive draws nothing. A text element is `element_box` shrunk by 1e-9 on
every side, because the width factor 0.6 is not a binary fraction and an edge that only touches
must stay touching. A rectangle with no area is overlapped by nothing, and any non-finite number
makes a shape overlap nothing. The lane of a port is the rectangle from the port to the edge of a
frame: the keep-out box united with every port position, grown by 1 M on every side (per symbol).
Why: the guide defines overlap but not the arithmetic, and the lane is unbounded.
Cost if wrong: the frame margin is one constant; a 1e-9 tolerance on segments would be a change in
one function. Consequence to know: an element that overlaps a lane always also pushes the body box
past its port, so `port-on-body-edge` fires with `port-lane-clear`; a text element does the same, because its box
is part of the body box too. Only a slot box can break the lane on its own, which is why the lane
fixtures use slot boxes.

## D27. What the Ports rules count

Decided: `port-duplicate-id`, `port-off-wiring-grid`, `port-off-geometry`, `port-on-body-edge` and
`port-lane-clear` give one finding per port at `ports[i]` (the later port for a duplicate id); the
lane finding names the first three offending elements or slots and counts the rest.
`port-spacing` and `port-position-shared` give one finding per later port, naming the first earlier
port it is out of step with (same `dir`, gap not a multiple of 2 M; same position, different node).
The grid and spacing tests are exact (`% 1`, `% 2`), so NaN and infinity fail them.
`port-off-geometry` is `point_on_geometry` with `endpoints_only=True` (D24): a bend of an open
polyline is not an end. `port-on-body-edge` compares exactly and requires the other coordinate to
lie in the side's closed extent. Nodes come from `nodes_of`; a port id listed by two nodes belongs
to the first, and two ports with one id are one node. `port-on-body-edge` and `port-lane-clear` are
orientation dependent (text boxes and slot boxes do not turn); the other five are invariant, which
a property test checks for random grid-multiple symbols in all 8 orientations.
Why: the guide names the rules, not their granularity.
Cost if wrong: locations and message text change; a per-pair report for spacing and shared
positions would list more findings for three or more ports on one side.

## D28. What the Connectivity rules count

Decided: nodes come from `nodes_of` (D27); a port id listed by two nodes belongs to the first.
`node-invalid` gives one finding per offending name at `nodes[i]`: an unknown port, or a port that
an earlier node lists already; a port named twice inside one node counts as listed twice.
`path-invalid` gives one finding per path at `paths[i]`, the first of: an unknown port (both
named), two ports of one node (`from == to` included), a repeat of an earlier path between the same
unordered pair of nodes (the earlier one is named). A path that joins one node to itself is not an
"earlier path". `through-count` gives one finding per through path after the first, at the later
path. `through-axis` checks every through path on its own, whatever `through-count` says: `a` is
the `to` port's y, which must be positive and whole (`a > 0`, `a % 1 == 0`), `from` must be at
`(0, -a)` facing N and `to` at `(0, a)` facing S, all compared exactly (`-0.0` is `0`); a path that
names an unknown port has no through-axis finding (`path-invalid` reports it), and the first port
with an id is the one used. `through-missing` is one finding for the whole file (no location):
`kind = "symbol"`, at least two nodes in `nodes_of`, no potential on any node, no through path.
`port-isolated` gives one finding per port at `ports[i]`: the port is named by no path (valid or
not), no declared node lists it together with another existing port, and its (first) node has no
potential. The fixtures of the Ports and Composition rules gained a `potential` on their single node
or a conductor path so the new warnings do not fire on them; the `through-count` fixture tolerates
`path-invalid`, because two through paths that are both right on the axis join the same two nodes.
Why: the guide names the rules, not the granularity, the corners, or which of two overlapping
rules reports a malformed path.
Cost if wrong: locations and message text change; a per-symbol `through-count` finding instead of
one per extra path.

## D29. What the Slots rules count

Decided: `slot-missing` (kind symbol only) gives one finding per missing slot, at that slot
(`slots.tag`, `slots.marking.<port id>`); ports that share an id need one marking slot, and
`value` is never required. `slot-unknown-port` (every kind) takes a slot whose id starts `marking.`
and looks up the rest of the id (only the first prefix is removed, so `marking.1.in` names the
port `1.in`); an empty rest is unknown. `slot-overlap-body` gives one finding per slot at
`slots.<id>` naming the first three overlapped elements, using `overlaps_rect` (D26).
`slot-overlap-slot` gives one finding per overlapping pair, at the later slot, naming both; boxes
without area overlap nothing. `pitch-overflow` (kind symbol only, base orientation, run once) has
two parts. A `pole_pitch` that is not a positive multiple of 4 is a finding at `pole_pitch`. For a
symbol with at least one through path the extent is `max.x - min.x` of `body_box` united with every
slot box whose id is neither `tag` nor `value`, and it must be at most the limit: `pole_pitch` if it
is positive (even when it is not a multiple of 4, so a pitch of 6 with an extent of 7 gives both
findings), otherwise 4. A symbol without a through path has no extent to check, as the guide
says "for a symbol with a through path". A through-path symbol with no elements has the origin
box (D13) as its body box. The two orientation-only fixtures rely on the box being upright: two
boxes 3 M wide and 1 M tall that stand 2 M apart vertically miss each other and overlap by 1 M once
the 2 M step is horizontal; a 1.5 x 3 M box beside a lead lies across it after a quarter turn.
Why: the guide names the rules, not their granularity or the corners.
Cost if wrong: locations and message text change; the limit for a `pole_pitch` that is positive
but not a multiple of 4 would be 4 instead.

## D30. What resolved JSON writes where D11 and the guide are silent

Decided: `ports`, `nodes`, `paths`, `anchors`, `elements` and `slots` are always written, as `[]` or
`{}` when empty (`slots` because the schema requires it for `kind = "symbol"`; the rest so a
consumer never tests for absence). `nodes` follows `nodes_of`: declared nodes in source order, then
one node per port in none. A path always writes `through`. Slots are a table written in slot-id order,
so a JSON object read back gives the slots in that order; a symbol's slot order is not preserved by
the round trip, and neither is a node list that was implicit. Text is canonical as `json.dumps` writes it
with `indent=2`, `sort_keys=True` and `ensure_ascii=False`, after every whole float has become an
int (`-0.0` prints as `0`), so a point is four lines; control characters in strings are escaped, so
no carriage return can occur. Floats print in Python `repr` form (`0.1`, `1e-05`), which is
valid JSON; grid values (multiples of 0.125) never take an exponent form. NaN and infinity have no JSON form: `to_json` writes `NaN`,
`Infinity` and `-Infinity` as Python's `json` does and does not raise; both validators reject them
(D22), so only a hand-built symbol can carry one.
Why: the guide fixes the text rules and the two computed keys and nothing else; `json.dumps` with
those options is what every language's standard pretty-printer produces plus a key sort.
Cost if wrong: a byte-level diff of every generated file; compact point arrays would need a
hand-written writer.

## D31. What the build writes, what stale means, what a bundle may contain

Decided: `serialize.py` holds `build_files(library) -> dict[str, bytes]` (path relative to the
repo root with `/`, in path order), `package_name` (D8) and `GENERATED_DIRS`; `gallery.py` holds
`readme`. `write_build` and `stale_build` in `build.py` both call `build_files`, so they cannot
disagree; both return `root / <relative path>` (relative if `root` is), ordered by their
relative `/` path; an unreadable file or unwritable path raises `OSError`. `write_build` creates directories, writes bytes (never text mode, so no `\r` on Windows)
and deletes nothing. `stale_build` reports a missing file, a directory where a file belongs, a
file with other bytes, and any file, at any depth, under `build/resolved`, `build/svg` or
`build/annotated` that the library does not produce; it looks at nothing else. Text UTF-8 cannot
encode (a lone surrogate, which JSON can carry) is written as `?`. The README has the standard, a
one-line note on status and a table (number linking to the resolved JSON, name, kind, status,
plain and annotated image); it uses `standard` and never `title`, so a library loaded from a
bundle builds the same bytes as the one loaded from the sources. A bundle is read by `parse_json`
and `validate_bundle` (both in `load.py`, pure) and `library_from_bundle`; `validate_bundle` checks
every symbol with `validate` and requires the resolved form (no `parts`, `ports` an array, slots
tables) and a key that is a file stem and equals the symbol's `reference.number`. A file stem is
letters, digits, `_` and `-` in parts joined by single dots (`5.1`, `ISO-14617-1.1`): the guide
says the number is the file stem and later standards (ISA 5.1, ISO 14617) have dots in theirs, so
dots must load; a leading, trailing or doubled dot, a separator, a space or an empty name cannot
name a file safely. `write_build` and `stale_build` raise `ValueError` for a library with a
number that is not a file stem, before reading or writing anything (`is_file_stem` in `load.py`
is the one test).
Why: the guide names the two functions and the layout; the rest keeps output byte-exact and keeps
a bundle from a stranger from writing outside the repo.
Cost if wrong: a number with another character (a space, `+`) cannot be a bundle key (relax
`_STEM` in `load.py`); extras outside the three directories stay unreported (add a directory to
`GENERATED_DIRS`); a data repo that wants stale extras removed writes that loop itself.

## D32. `to_svg` and `arc_point` are total; what the SVG does with input XML cannot carry

Decided: `arc_point` returns the arc's centre for a NaN or infinite angle (it used to raise from
`math.cos`), so `to_svg` never raises for a hand-built symbol. The boxes keep their own rule
(D25): an arc with a non-finite angle counts as its centre there even when its other angle is
finite, which `arc_point` alone would not give, so `_extent_points` still checks it. The number
formatter writes NaN and infinity as `0`; finite numbers are unchanged (at most 4 decimals, no
`-0`), so a huge value such as 1e300 is written out in full. Text in `<title>` and in every `<text>`
goes through one function: a character XML 1.0 cannot carry (C0 controls except tab, line feed and
carriage return, lone surrogates, U+FFFE, U+FFFF) becomes U+FFFD, not dropped, so the text keeps
its length; `&`, `<` and `>` become entities; a carriage return becomes `&#13;` (a parser reads
`\r` back, no `\r` byte reaches the file and `stale_build` stays stable on every platform). A line
feed and a tab stay as they are, because XML keeps both in character data. The annotation grid is
left out when the view is not finite or would hold more than 10 000 dots (100 by 100 M, 250 mm
square at the default module), because a dot per module of a 1e300 symbol would never finish.
Why: CLAUDE.md wants every module-level function pure and non-raising; a symbol name can carry
`"\r"` or a NUL from TOML, and a build the sibling repo compares byte for byte must be well-formed
XML with LF-only bytes.
"Never raises" covers the typed inputs, floats: a Python int beyond float range (10**400) in a
hand-built `Point` is outside the contract (the fields are `float`) and unreachable from files
(numbers are bounded to 1e6, D22).
Cost if wrong: a garbage symbol draws garbage numbers instead of an error; a real symbol above
100 by 100 M gets no grid in its annotated SVG (one constant); a `\r` in a name shows as `&#13;`
in the file.

## D33. What the annotated SVG draws, and the sample texts of the gallery

Decided: the guide says `annotate=True` draws "the grid, ports with ids and lanes, anchors, slot
boxes, and both boxes" and `texts` maps slot ids to sample strings. Drawn in this order, all inside
`<g class="annotation">`: the grid (`grid`, a dot at every whole module, D32); `body-box` (green)
and `keepout-box` (purple), both dashed 0.2/0.2, the keep-out one offset by 0.2 so they alternate
where they coincide; per slot, in slot-id order, a translucent `slot-box` (blue) and its id (`slot-id`,
size 0.3) just above the box; per anchor a teal diamond of half-size 0.2 (`anchor`) and its id
(`anchor-id`, size 0.4) centred 0.75 M out along the anchor direction; the `lane` of every port, a
red translucent strip 0.5 M wide from the port along its direction to the edge of the view; then
per port a red dot (`port`) and its id (`port-id`, size 0.6, centred 1 M out). The elements are
drawn first, under all of it. The view is the keep-out box united with every port label box, every
lane start (0.5 M across), every anchor marker and label and every slot label, plus 1 M on every
side; a port or anchor label box is 1 em wide per character (0.6 M per character at size 0.6, 0.4 M
at 0.4; the code keeps the half-width, 0.3 and 0.2 M per character), a little wider than the
glyphs, a slot label box is 0.6 em per character (0.18 M at size 0.3, the guide's own text width),
and each is one font size high. Plain, the view is the body box, plus the slot boxes of the texts
that are drawn. Sample text (`<g class="samples">`, drawn last, in both modes, class
`sample-text`, orange, no stroke, upright, `font-family="sans-serif"`): the font size is the
largest `s <= 1` with `s <= h` and `0.6 * s * characters <= w`, rounded down to 4 decimals; a
slot with no text, an empty one, a box without a positive size, or an id the symbol has no slot
for gets nothing. Vertical placement uses explicit baselines and no `dominant-baseline`, which
several renderers (MuPDF, cairosvg) ignore: E and W put the baseline 0.36 s below the slot point (a
capital is about 0.72 s tall, so it is centred on the point), N puts it on the point, S 0.72 s
below (the capitals hang from the point). The port id labels use the same 0.36 rule instead of
`dominant-baseline="central"`, so they moved 0.216 M down, and so does a symbol's own `Text`
element (its baseline is `at.y + 0.36 * height`, so the capitals are centred in the text box the
guide defines; it was `at.y`, which put them above the box). Slots are drawn in id order because
resolved JSON keeps them in id order (D30): a symbol loaded from a bundle must give the same
bytes as the one from the sources. The build (`build_files`) draws `build/annotated/<n>.svg` with
`sample_texts(symbol)` from `gallery.py`: `tag` is `-X1`, `value` is `10 A`, `marking.<port id>` is
the 1-based position of the port in `symbol.ports` (the first, for ports that share an id); the
plain `build/svg/<n>.svg` stays the bare definition.
Why: the guide names what is drawn, not how; the gallery must show a filled-in symbol, and a
sample text that does not depend on the symbol name keeps the files small and stable.
Cost if wrong: every annotated SVG changes (colours, sizes, label places are constants); a
different sample changes every annotated file; the 0.6 M per character width is the guide's own
text extent, and a real font is a little wider for some strings (`marking.out` at size 0.3 fits
its label box only about).

## D34. One finding order for the resolver and the linter

Decided: `finding_key` in `lint/registry.py` is the one sort key for a `Finding`, used by
`resolve_library` (per file) and by `lint.ordered`. It sorts by the rule's place in the guide's
section 9 table (`GUIDE_INDEX`; a rule outside the table after all of them, by id), then by
orientation (none first, then R0 to MR270), then by location with numbers compared as numbers
(`/parts/2` before `/parts/10`, `elements[2]` before `elements[10]`), then by generation order.
A data repo that concatenates `LibraryError.findings` and `lint` results and sorts them with
`finding_key` gets the table's order across both. The resolver used to sort by rule id in
alphabetical order (`id-format` before `metadata`, `export-unknown` before `part-port-unexported`).
Why: two orders for the same rules had no single rationale, and the table is the guide's own.
Cost if wrong: a change in one function; resolver findings of different rules swap places.

## C3. `lint_allow` cannot exempt the rules the resolver reports

Concern: guide section 4 calls `lint_allow` "the only way to be exempt from a lint rule", section 9
says composition and file rules "are reported the same way", and section 8 says an exemption whose
rule would not have fired is itself an error. The resolver's rules (`schema`, `metadata`,
`part-unknown`, `part-cycle`, `part-anchor`, `part-port-unexported`, `export-unknown`, and
`id-format` of a part id) run in `resolve_library`, outside `lint`, which never reads `lint_allow`;
the three statements cannot all hold for them.
Implemented as: these rules are not exemptable. An entry that names one of the seven that only the
resolver reports changes nothing, and `allow-unused` does not fire for it, so a mistaken entry is
inert and does not add a second error next to the original one (`id-format` is still judged by
`lint`, see D23). Cost if wrong: applying `lint_allow` in `resolve_library` to the composite's own
findings, and reporting an entry there as unused when the rule did not fire; the two exemption
functions in `lint/exemptions.py` would then serve both places. Owner to decide whether these rules
are formally non-exemptable or the resolver should apply `lint_allow`.

## D35. A standard with no letter or digit cannot be built

Decided: `write_build` and `stale_build` raise `ValueError` when `package_name(library.standard)`
is empty (a standard such as `...` or `-`), before reading or writing anything, the same error
type as for a number that is not a file stem (D31). `load_library` and `validate` still accept such
a standard: the check is in the impure shell (`_check_names` in `build.py`), not in `validate`,
`parse_config` and the bundle validator, which would each need a rule for it.
Why: D8 makes the package the standard with everything but letters and digits removed, so an empty
package would write `src/bundle.json` instead of `src/<package>/bundle.json`, silently.
Cost if wrong: a `schema` finding on `standard` in `parse_config` and `validate_bundle`, so
`load_library` reports it, and a matching key in the JSON Schema.

## D36. `deal` is the one runtime dependency, kept for the purity contracts

Decided: every module-level function in a pure module carries `@deal.pure`, checked at import
time, and `deal` is a runtime dependency of the package, not a dev dependency. No other
third-party package is added to `src/`; `jsonschema` stays a dev-only dependency of the schema
agreement test. This carries forward the reasoning of the Schematika v2 monorepo's decision 0008
from the interval this package spent as `packages/graphical-symbols` in that workspace, where a
boundary test enforced `deal` as the package's only allowed third-party import; that test does not
exist here, so this entry is the record now that the package is its own repository again.
Why: `scripts/fp_purity_gate.py` fails the build when a pure-module function is missing the
decorator, and the decorator is a runtime contract, so it cannot be moved to a dev group.
Cost if wrong: a second third-party import in `src/` with no record here, or `deal` dropped
without a replacement for the purity contracts it checks.

## D37. Build-time file access is confined to `build.py`, `load_bundle` and `load_library`

Decided: `load_library`, `load_bundle`, `write_build` and `stale_build`, and `scripts/build.py`,
read and write symbol source and build files as a build-time tool whose output is tracked data
(`build/`, `src/graphical_symbols/bundle.json`-shaped output for a consumer, the gallery). No
other module reads or writes a file; the pure core takes values and returns values.
`scripts/fp_purity_gate.py` exempts `build.py` by name, the same way `tests/test_boundaries.py`
in the Schematika v2 monorepo exempted it while this package lived there as
`packages/graphical-symbols` (that workspace's decision 0009, which also recorded
`electrical_symbols` reading its packaged `bundle.json` at import -- a fact about that package,
not this one, and no longer this repository's concern).
Why: symbol data is compiled by a developer running the build, not read at render time; the
toolkit itself never touches a file outside that build step.
Cost if wrong: a file read or write anywhere else in `src/` needs a new decision record and a
`fp_purity_gate.py` exemption, which the gate's own can-fail test would then have to prove.

## D38. The design guide is package data, read through `importlib.resources`

Decided: `docs/SYMBOL_INTERFACE.html` moved (`git mv`, history kept) to
`src/graphical_symbols/docs/SYMBOL_INTERFACE.html`. Hatch's wheel config already packages
everything under `src/graphical_symbols/`, so the file needs no new build-system entry: it sits
at the same relative path in the source tree and in the built wheel. A consumer reads it with
`importlib.resources.files("graphical_symbols").joinpath("docs/SYMBOL_INTERFACE.html")`, which
resolves the same way whether the package is installed from an editable source checkout, a git
dependency, or a built wheel. `tests/test_guide_package_data.py` proves the resource resolves and
carries the guide's own `<title>` (not a byte count, which would break on every edit to the
guide's prose and tests the wrong property).
Why: `electrical-symbols` compares its data byte for byte against this guide's worked examples
(its own D38, the "verbatim gate"), and until this toolkit left the Schematika v2 monorepo the two
packages shared one copy through a sibling directory. Now they are two repositories; the toolkit's
wheel never shipped `docs/`, so the sibling path stopped resolving. Moving the guide under the
package directory keeps exactly one copy, and it is the toolkit's own, which is the only copy a
downstream gate can check against and still mean anything (a vendored copy in the downstream
package would only prove agreement with itself).
Cost if wrong: a consumer with a stale copy or a broken resource path silently stops checking
against the real guide; `test_guide_package_data.py`'s can-fail test is the guard against a
resource that resolves but is not this file's content.

## D39. `to_fragment`: a placeable `<g>` fragment beside the standalone document `to_svg`

Decided: `svg.py` gains `to_fragment(symbol: Symbol) -> str`, returning `_GROUP_OPEN`, one
`_element(e)` per `symbol.elements` and `</g>`, joined by newlines with a trailing one -- exactly
the plain content group `to_svg` already builds, reusing `_element` and `_GROUP_OPEN` directly
rather than a second element-rendering path. No `<svg>` root, no `<title>`, no annotations, and no
sample texts: the function takes no `texts` parameter at all, so a slot's sample text can never
reach a fragment, not merely because no fixture happens to exercise it. It applies no transform,
scale or orientation of its own; the caller places it in its own coordinate system. Exported from
`graphical_symbols.__init__` alongside `to_svg`.
Why: `schematika_render` (the Schematika v2 monorepo's render package) assembles a page out of
several placed symbols and needs each one as a reusable piece it positions and scales itself, not
a whole standalone document; the guide (`SYMBOL_INTERFACE.html`) defines only the standalone
`to_svg` document and is silent on an embeddable fragment.
Cost if wrong: reusing `_element`/`_GROUP_OPEN` means any future change to how an element renders
is automatically picked up here too; if a future edit ever duplicated that logic instead, the
fragment and the document's plain mode could silently drift apart. A wrong function name is a
rename in two files (`svg.py`, `__init__.py`) and the tests that check it.

## D40. A line binds to a port with `port`; the file's `schema` integer does not step

Decided: `Line` gains a trailing field `port: str | None = None`, written by `line = { ...,
port = "in" }`. It is optional, additive and carries no default that changes an existing file's
meaning, so `schema` (the file-format marker, `const 1` in the JSON Schema and
`_schema_version`) stays 1: nothing that validated before stops validating, and nothing that
validates now would have validated under the old rule differently. A new lint rule
`lead-off-port` (ERROR, Ports group, guide section 9) fires when the named port does not exist,
or when it does but neither end of the line is at the port's position, or the line does not run
along the port's facing axis (the coordinate perpendicular to the port's direction must be equal
at both ends) -- one finding per offending line, at `elements[i]`. The resolved JSON writes
`port` only when set (D11's "absent" pattern, like `edition` and `pole_pitch`). `orient` and
`translate` carry `port` along for free through `dataclasses.replace`. `repeat` prefixes a bound
lead's `port` with `<k>.`, the same prefix it gives the port itself, so a repeated symbol's leads
stay bound. Composition namespaces a part's bound lead `<part>.<child port>` while placing it,
then rewrites that to the rename map's exported id once `_export_ports` has computed it; a lead
bound to a part port the rename map leaves out keeps the namespaced, unreachable id, which is
moot because `_export_ports` already fails the file on `part-port-unexported` for that port. A
part port the rename map exports under more than one new id (`{ a = "c.in", b = "c.in" }`) gives
a bound lead the first one the map declares: both exported ports still share the child's position
and direction, so the choice only decides which one the lead's own metadata names, never where
either one draws or routes; `test_resolve.py`'s
`test_a_lead_on_a_port_exported_twice_follows_the_first_declared_alias` pins it.
Why: the package version (`pyproject.toml`, currently 0.1.2) is this repo's only versioning
mechanism with a minor/major/patch structure; the work order that asked for this expects the
release that carries it to be tagged a minor step (`v0.2.0`) on that scheme, not on `schema`,
which is a single flat integer with no such structure and no precedent of ever moving off 1. A
consumer on the old tag simply never emits `port`; a consumer that needs it takes the new tag,
same as any other public addition here (CLAUDE.md's "coordinated change"). The `port-lane-clear`
guarantee already makes a wire reaching a port along its own axis safe at `t = 0`; `lead-off-port`
only makes sure a claimed binding actually is that wire, so a downstream renderer (or anything
else) can trust `element.port` without re-deriving it from geometry.
Cost if wrong: an unmapped `repeat` or composition would leave `element.port` naming a port that
no longer exists after flattening, silently turning every downstream reader's binding lookup
into "unbound" instead of a loud finding; `test_repeat.py` and `test_resolve.py` each gained one
test against exactly that. If the owner ever wants `schema` itself to carry a minor/major split,
that is a bigger, separate decision: nothing here depends on it.

## D41. Public, plain-markdown docs; v0.3.0; exact git tag; no PyPI for now

Decided (owner 2026-10-01): the repo's documentation is plain markdown in the repo, with no
documentation site: `README.md` (install, one worked example, the concepts), `docs/GUIDE.md`
(the concepts in more depth: how symbols are defined, built, linted and serialized) and
`AGENTS.md` (how an agent works here). Every public name in `__all__` carries a short Google-style
docstring. The README's Python examples are run by `tests/test_readme.py`, so they cannot drift.
The release that carries this is `v0.3.0`; consumers install by exact git tag (`uv add
"graphical-symbols @ git+https://github.com/OleJBondahl/graphical-symbols@v0.3.0"`). The package
is not published to PyPI for now.
Why: the toolkit is consumed by an exact tag already (D38's package data, Schematika's pin), a
site or an index would add upkeep with no reader today, and the README test already keeps the
examples true.
Cost if wrong: if a consumer outside the tag workflow appears, PyPI publication is a later,
separate decision (trusted publishing and a release workflow); nothing here blocks it. The docs
are only as true as their tests: prose outside the README's examples is not run.

## Open questions for the owner

- C1 (S00254 fails `pitch-overflow` as written): add `pole_pitch = 8` to the guide's example or
  shorten the link. The real `iec60617` `S00171` may change the extent; report the outcome there.
- C2 (`id-format` versus `repeat`'s `<k>.` port ids): keep the prefix form permanently, or change
  the guide's id pattern.
- C3 (`lint_allow` and the seven resolver-only rules): formally non-exemptable, or apply
  `lint_allow` in `resolve_library`.
- Merging `feat/toolkit` into `main` is the owner's call; nothing has been merged.

## Known limits, decided not to bound

Each is reachable only from the data repo owner's own files, and the guide is silent. Cost if
wrong: add a bound and a `schema` finding, as D22 did for numbers and `repeat`.

- `resolve_library`: nested composites with two parts each fan out as 2^depth elements (depth 16 is
  about 2 s; about 40 tiny files would not finish).
- A catastrophic-backtracking `number_pattern` in `library.toml` (for example `(a+)+$`; the time
  grows by 4 per 2 characters) can hang `re.search`. It is the only non-terminating path in the
  core. `^S\d{5}$`-style patterns are safe.
- Lint cost is quadratic in the number of poles of a `repeat`ed device (64 poles about 21 s, 24
  poles 2.8 s; `deal` tracing is about 2.2 times of that). The gates need only `repeat(s, 3)`.
- `load_library` accepts a file stem or `number_pattern` that yields a number failing the stem
  regex (`a b.toml`, or a Windows device name such as `CON`); `write_build` and `stale_build` then
  raise `ValueError` (D31), and `build/svg/CON.svg` would misbehave on Windows.
- `validate` still raises on a mapping key that is a 4300-digit integer (unreachable from TOML or
  JSON); some private module-level tables (`orient._PARTS`, `load._ELEMENTS`, `svg._SAMPLE_ALIGN`,
  `geometry._RIGHT_ANGLE_COS_SIN`) are mutable dicts.
- In the annotated S00227 the sample text `-X1` covers the start of the `link` anchor label,
  because the guide's `tag` slot ends 1 M west of that anchor. Cosmetic, gallery only.

## What `../iec60617` must do because of these decisions

- Add `.gitattributes` with `* text=auto eol=lf`; without it, on Windows with `core.autocrlf=true`,
  tracked build files become CRLF and `stale_build` reports everything stale.
- Run `write_build` again: the `Text` baseline fix (D33) changed the bytes of every SVG that contains
  a `Text` element, so any committed build is stale.
- Use `finding_key` (`graphical_symbols.lint.registry`, D34) to sort the concatenated
  `LibraryError.findings` and `lint` results; wrap `load_bundle` at import time for `LibraryError`.
- Lint `repeat(s, 3)` for every symbol with a through path, and report the C1 outcome.
