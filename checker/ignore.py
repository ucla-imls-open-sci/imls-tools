"""`.wbcheck.toml`: per-lesson suppressions, committed with the lesson so
collaborators share them (issue #23).

    # .wbcheck.toml, at the lesson root
    [ignore]
    codes = ["WB404"]                      # a rule, everywhere
    paths = ["episodes/all_exercises.md"]  # every finding in these files (globs ok)
    ids = ["8289307d05d3"]                 # single findings, by stable ID

`wbcheck check` and `wbcheck review` drop matching findings before saving
results. The TUI's ignore key appends IDs here; the file is then rewritten
in this canonical form, so hand-written comments inside it are not kept.
"""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from checker.report import Finding

IGNORE_FILENAME = ".wbcheck.toml"


@dataclass
class IgnoreRules:
    """Codes, path globs, and finding IDs to suppress."""

    codes: set[str] = field(default_factory=set)
    paths: list[str] = field(default_factory=list)
    ids: set[str] = field(default_factory=set)

    def matches(self, f: Finding) -> bool:
        """Whether `f` is suppressed by any rule."""
        if f.id in self.ids or (f.code and f.code in self.codes):
            return True
        return bool(f.location) and any(fnmatch.fnmatch(f.location or "", pattern) for pattern in self.paths)

    def apply(self, findings: list[Finding]) -> tuple[list[Finding], int]:
        """Findings not suppressed, and how many were."""
        kept = [f for f in findings if not self.matches(f)]
        return kept, len(findings) - len(kept)


def load_ignore(lesson_dir: Path | None) -> IgnoreRules:
    """Rules from `<lesson_dir>/.wbcheck.toml`; empty if absent. Raises
    ValueError with the file path on invalid TOML."""
    if lesson_dir is None:
        return IgnoreRules()
    path = lesson_dir / IGNORE_FILENAME
    if not path.exists():
        return IgnoreRules()
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path} is not valid TOML: {exc}") from exc
    section = data.get("ignore") or {}
    return IgnoreRules(
        codes={str(c) for c in section.get("codes") or []},
        paths=[str(p) for p in section.get("paths") or []],
        ids={str(i) for i in section.get("ids") or []},
    )


def _toml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    items = "".join(f'  "{v}",\n' for v in values)
    return f"[\n{items}]"


def save_ignore(lesson_dir: Path, rules: IgnoreRules) -> Path:
    """Write `rules` to `<lesson_dir>/.wbcheck.toml` in canonical form."""
    path = lesson_dir / IGNORE_FILENAME
    path.write_text(
        "# wbcheck suppressions for this lesson. Commit this file so collaborators share them.\n"
        "# Rewritten by `wbcheck tui` when you ignore a finding; comments inside are not kept.\n"
        "[ignore]\n"
        f"codes = {_toml_list(sorted(rules.codes))}\n"
        f"paths = {_toml_list(rules.paths)}\n"
        f"ids = {_toml_list(sorted(rules.ids))}\n"
    )
    return path


def add_ignored_ids(lesson_dir: Path, ids: set[str]) -> IgnoreRules:
    """Append finding IDs to the lesson's ignore file, creating it if needed."""
    rules = load_ignore(lesson_dir)
    rules.ids |= ids
    save_ignore(lesson_dir, rules)
    return rules
