"""Local pre-flight checks for Carpentries Workbench lessons.

Mirrors (a fast, local subset of) what sandpaper::validate_lesson() and
pegboard's validate_divs()/validate_headings()/validate_links() check in CI,
plus an optional AI narrative review layered on top.
"""

# Single source for the package version (pyproject.toml reads it via hatch).
# pixi.toml's [workspace] version is still kept in sync by hand.
__version__ = "0.2.0"
