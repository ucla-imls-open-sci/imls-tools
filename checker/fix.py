"""Fixing findings locally: which files changed, vim/nvim quickfix output,
automatic fixes, and suggestions.

Two tiers, each shown as a diff before anything is written:

Safe fixes (`wbcheck fix --apply`): the edit is unambiguous from the
finding and changes no meaning, so `--yes` may apply them in bulk.

    WB103  `exercise:` typo in front matter  -> `exercises:`
    WB213  heading skips a level             -> set it one below the previous heading

Suggestions (`wbcheck fix --suggest`): mechanically well-defined, but
editorial decisions, so each is confirmed individually and `--yes` never
applies them.

    WB401  vague objective opener            -> the suggested rewrite (Understand -> Explain, ...);
                                                changes what the objective says
    WB009  episode file not in config.yaml   -> append it to `episodes:`; publishes a file
                                                that may be an intentionally unlisted draft
"""

from __future__ import annotations

import difflib
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from checker.lesson_check import _looks_misplaced, check_episode, rewrite_objective_opener
from checker.report import Finding

SAFE_FIX_CODES = ("WB103", "WB213")
SUGGESTION_CODES = ("WB401", "WB009")
AUTOFIX_CODES = SAFE_FIX_CODES + SUGGESTION_CODES


# -- changed files ---------------------------------------------------------------


def changed_files(lesson_dir: Path, since: str | None = None) -> set[str] | None:
    """Lesson-relative paths changed in the working tree (staged, unstaged,
    or untracked), plus, with `since`, everything that differs from that git
    ref. None if the lesson isn't a git repo or git fails."""
    try:
        # -z: NUL-separated records with paths verbatim; without it git
        # quotes paths containing spaces or non-ASCII ("episodes/a b.md").
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all"],
            cwd=lesson_dir, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if status.returncode != 0:
        return None
    # porcelain paths are relative to the repo root, which may sit above the lesson
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=lesson_dir,
                         capture_output=True, text=True, timeout=10).stdout.strip()
    root = Path(top) if top else lesson_dir
    paths = {record[3:] for record in status.stdout.split("\0") if len(record) > 3}
    if since:
        diff = subprocess.run(["git", "diff", "--name-only", "-z", f"{since}...HEAD"], cwd=lesson_dir,
                              capture_output=True, text=True, timeout=10)
        if diff.returncode != 0:
            raise ValueError(f"git can't compare against `{since}`: {diff.stderr.strip()}")
        paths |= {p for p in diff.stdout.split("\0") if p}
    out = set()
    for p in paths:
        try:
            out.add(str((root / p).resolve().relative_to(lesson_dir.resolve())))
        except ValueError:
            continue  # outside the lesson directory
    return out


def only_changed(findings: list[Finding], changed: set[str]) -> list[Finding]:
    """Findings located in one of the `changed` files."""
    return [f for f in findings if f.location in changed]


# -- vim / nvim quickfix -----------------------------------------------------------


def quickfix_lines(findings: list[Finding], lesson_dir: Path) -> list[str]:
    """`path:line:col: [CODE] message` per finding, in file/line order: the
    format vim's default 'errorformat' reads with `vim -q` / `:cfile`."""
    lines = []
    for f in sorted(findings, key=lambda f: (f.location or "", f.line or 0)):
        if not f.location:
            continue
        message = " ".join(f.message.split())
        if f.hint:
            message += f"  Fix: {' '.join(f.hint.split())}"
        lines.append(f"{lesson_dir / f.location}:{f.line or 1}:1: [{f.code or f.category}] {message}")
    return lines


def uses_quickfix(editor: str) -> bool:
    """Whether `editor` (a $VISUAL/$EDITOR value) is a vim that takes `-q`."""
    name = Path(editor.split()[0]).name if editor.strip() else ""
    return name in ("vim", "nvim", "gvim", "mvim", "vi") or name.startswith("nvim")


# -- automatic fixes ---------------------------------------------------------------


@dataclass
class Edit:
    """Replace line `index` (0-based) of `path` with `new`, or, when `insert`
    is true, insert `new` after it. `old` guards against editing a line that
    changed since the check ran."""

    path: Path
    index: int
    old: str
    new: str
    insert: bool = False


@dataclass
class AutoFix:
    """One proposed fix for one finding."""

    finding: Finding
    description: str
    edit: Edit
    # Raises ValueError if the edited file text is wrong (e.g. config.yaml
    # no longer parses, or lost an episode). Run before anything is written.
    validate: Callable[[str], None] | None = None

    def diff(self, root: Path) -> str:
        """Unified diff of this fix alone against the file as it is now."""
        lines = self.edit.path.read_text().splitlines(keepends=True)
        after = _applied(lines, self.edit)
        rel = self.edit.path.relative_to(root) if self.edit.path.is_relative_to(root) else self.edit.path
        return "".join(difflib.unified_diff(lines, after, f"a/{rel}", f"b/{rel}", n=1))


def _applied(lines: list[str], edit: Edit) -> list[str]:
    if lines[edit.index].rstrip("\n") != edit.old:
        raise ValueError(f"{edit.path.name}:{edit.index + 1} changed since the check; re-run `wbcheck check`")
    newline = "\n" if lines[edit.index].endswith("\n") else ""
    if edit.insert:
        # a last line without a newline needs one before anything goes after it
        anchor = lines[edit.index] if newline else lines[edit.index] + "\n"
        return lines[: edit.index] + [anchor, edit.new + "\n"] + lines[edit.index + 1 :]
    return lines[: edit.index] + [edit.new + newline] + lines[edit.index + 1 :]


def apply_fix(fix: AutoFix) -> None:
    """Write `fix` to disk, after re-checking the line is unchanged and
    running its validator on the result."""
    lines = fix.edit.path.read_text().splitlines(keepends=True)
    new_text = "".join(_applied(lines, fix.edit))
    if fix.validate is not None:
        fix.validate(new_text)
    fix.edit.path.write_text(new_text)


_HEADING_RE = re.compile(r"^(#{1,6})(\s+.*)$")
_LEVEL_JUMP_RE = re.compile(r"from level (\d) to level (\d)")
_TYPO_RE = re.compile(r"^exercise(\s*:.*)$")


def _fix_wb103(f: Finding, path: Path, lines: list[str]) -> AutoFix | None:
    if "`exercises`" not in f.message or f.line is None:
        return None
    old = lines[f.line - 1]
    match = _TYPO_RE.match(old)
    if not match:
        return None
    return AutoFix(f, "rename front-matter key `exercise:` to `exercises:`",
                   Edit(path, f.line - 1, old, "exercises" + match.group(1)))


def _fix_wb213(f: Finding, path: Path, lines: list[str]) -> AutoFix | None:
    levels = _LEVEL_JUMP_RE.search(f.message)
    if f.line is None or not levels:
        return None
    old = lines[f.line - 1]
    heading = _HEADING_RE.match(old)
    target = int(levels.group(1)) + 1
    if not heading or len(heading.group(1)) != int(levels.group(2)):
        return None
    return AutoFix(f, f"make this a level-{target} heading",
                   Edit(path, f.line - 1, old, "#" * target + heading.group(2)))


def _fix_wb401(f: Finding, path: Path, lines: list[str]) -> AutoFix | None:
    if f.line is None:
        return None
    old = lines[f.line - 1]
    bullet = re.match(r"^(\s*(?:[-*+]|\d+[.)])\s+)(.*)$", old)
    if not bullet:
        return None
    rewritten = rewrite_objective_opener(bullet.group(2))
    if rewritten is None:
        return None
    return AutoFix(f, "use the suggested observable verb (check it still says what you mean)",
                   Edit(path, f.line - 1, old, bullet.group(1) + rewritten))


_UNLISTED_RE = re.compile(r"^episodes/(\S+) exists but is not listed")


def _looks_like_reference(lesson_dir: Path, name: str) -> bool:
    """WB013's test, run on the file itself, so the safeguard holds even
    when WB013 was filtered out (--code) or ignored in .wbcheck.toml."""
    path = lesson_dir / "episodes" / name
    return path.is_file() and _looks_misplaced(check_episode(path, lesson_dir))


def _episodes_validator(expected: list[str]) -> Callable[[str], None]:
    def validate(text: str) -> None:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"config.yaml would no longer parse: {exc}") from exc
        episodes = data.get("episodes") if isinstance(data, dict) else None
        if not isinstance(episodes, list) or episodes[: len(expected)] != expected:
            raise ValueError("config.yaml `episodes:` wouldn't come out as expected; not changed")
    return validate


def _fix_wb009(f: Finding, config: Path, lines: list[str], lesson_dir: Path) -> AutoFix | None:
    name = _UNLISTED_RE.match(f.message)
    if not name or _looks_like_reference(lesson_dir, name.group(1)):
        return None  # WB013: probably reference content, not an unwritten episode
    start = next((i for i, line in enumerate(lines) if re.match(r"^episodes:\s*$", line)), None)
    if start is None:
        return None  # flow style (`episodes: [a, b]`) or missing: leave it to the author
    last = start
    for i in range(start + 1, len(lines)):
        if re.match(r"^\s*-\s+\S", lines[i]):
            last = i
        elif lines[i].strip() and not lines[i].startswith((" ", "\t", "#")):
            break
    item = re.match(r"^(\s*)-", lines[last]) if last != start else None
    indent = item.group(1) if item else ""
    # YAML-quote names that need it ([draft].md, a: b.md, ...)
    scalar = yaml.safe_dump([name.group(1)], default_flow_style=False).strip()[2:]
    current = yaml.safe_load("\n".join(lines))
    listed = current.get("episodes") if isinstance(current, dict) else None
    expected = [*(listed if isinstance(listed, list) else []), name.group(1)]
    return AutoFix(f, f"add {name.group(1)} to the end of config.yaml `episodes:`",
                   Edit(config, last, lines[last], f"{indent}- {scalar}", insert=True),
                   validate=_episodes_validator(expected))


def plan_autofixes(
    findings: list[Finding], lesson_dir: Path, codes: tuple[str, ...] = SAFE_FIX_CODES
) -> list[AutoFix]:
    """Proposed fixes for the findings that have a safe one, bottom-up within
    each file so applying one never shifts another's line."""
    fixes: list[AutoFix] = []
    for f in findings:
        if f.code not in codes or not f.location:
            continue
        if f.code == "WB009":
            path = lesson_dir / "config.yaml"
        else:
            path = lesson_dir / f.location
        if not path.is_file():
            continue
        lines = path.read_text().splitlines()
        if f.code != "WB009" and (f.line is None or f.line > len(lines)):
            continue
        fix = {
            "WB103": lambda: _fix_wb103(f, path, lines),
            "WB213": lambda: _fix_wb213(f, path, lines),
            "WB401": lambda: _fix_wb401(f, path, lines),
            "WB009": lambda: _fix_wb009(f, path, lines, lesson_dir),
        }[f.code]()
        if fix is not None:
            fixes.append(fix)
    # Several WB009 inserts can land after the same line. Each insert goes
    # directly below it, so applying them in reverse name order leaves them in
    # name order; then sort (stably) bottom-up per file.
    fixes.sort(key=lambda x: x.finding.message, reverse=True)
    return sorted(fixes, key=lambda x: (str(x.edit.path), -x.edit.index))
