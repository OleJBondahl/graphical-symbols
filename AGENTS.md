# AGENTS.md

`CLAUDE.md` holds this repo's rules for any agent, not only Claude. This file restates none of
them.

- To work on the toolkit: read `CLAUDE.md`, then the spec,
  `src/graphical_symbols/docs/SYMBOL_INTERFACE.html`. `just --list` names the recipes, and
  `just ci` is the gate.
- To use the toolkit from another project: read `README.md` (install and a short tour), then
  `docs/GUIDE.md` (the concepts and the calls). The docstrings of the names in
  `graphical_symbols.__all__` are the API reference. The spec ships inside the package:
  `importlib.resources.files("graphical_symbols").joinpath("docs/SYMBOL_INTERFACE.html")`.
