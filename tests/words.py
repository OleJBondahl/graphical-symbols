"""The `library.toml` tables that declare today's words and slot duties, for inline configs."""

WORDS = """
[vocabulary]
path_kinds = ["conductor", "switch_open", "switch_closed", "impedance", "source", "diode"]
potentials = ["earth", "protective_earth", "functional_earth", "frame"]
links = ["mechanical_link"]

[rules]
required_slots = ["tag", "marking.<port>"]
"""
