"""Fixing findings locally: which files changed, vim/nvim quickfix output,
and safe automatic fixes.

Automatic fixes are deliberately narrow: only findings where the right edit
is unambiguous from the finding itself, each shown as a diff before it's
written. Content (objectives, prose, placeholders) is left to the author,
except WB401, whose rewrite is a suggestion the author confirms one by one.

    WB103  `exercise:` typo in front matter  -> `exercises:`
    WB009  episode file not in config.yaml   -> append it to `episodes:`
    WB213  heading skips a level             -> set it one below the previous heading
    WB401  vague objective opener            -> the suggested rewrite (Understand -> Explain, ...)
"""

from __future__ import annotations

import difflib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from checker.report import Finding

AUTOFIX_CODES = ("WB103", "WB009", "WB213", "WB401")


# -- changed files ---------------------------------------------------------------


def changed_files(lesson_dir: Path, since: str | None = None) -> set[str] | None:
    """Lesson-relative paths changed in the working tree (staged, unstaged,
    or untracked), plus, with `since`, everything that differs from that git
    ref. None if the lesson isn't a git repo or git fails."""
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--no-renames", "--untracked-files=all"],
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
    paths = {line[3:] for line in status.stdout.splitlines() if len(line) > 3}
    if since:
        diff = subprocess.run(["git", "diff", "--name-only", f"{since}...HEAD"], cwd=lesson_dir,
                              capture_output=True, text=True, timeout=10)
        if diff.returncode != 0:
            raise ValueError(f"git can't compare against `{since}`: {diff.stderr.strip()}")
        paths |= set(diff.stdout.split())
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
        return lines[: edit.index + 1] + [edit.new + "\n"] + lines[edit.index + 1 :]
    return lines[: edit.index] + [edit.new + newline] + lines[edit.index + 1 :]


def apply_fix(fix: AutoFix) -> None:
    """Write `fix` to disk (after re-checking the line is unchanged)."""
    lines = fix.edit.path.read_text().splitlines(keepends=True)
    fix.edit.path.write_text("".join(_applied(lines, fix.edit)))


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
    suggestion = re.search(r'Try "([^"]+)"', f.hint or "")
    if f.line is None or not suggestion:
        return None
    old = lines[f.line - 1]
    bullet = re.match(r"^(\s*[-*+]\s+)(.*?)(\.?)\s*$", old)
    if not bullet:
        return None
    return AutoFix(f, "use the suggested observable verb (check it still says what you mean)",
                   Edit(path, f.line - 1, old, bullet.group(1) + suggestion.group(1) + bullet.group(3)))


_UNLISTED_RE = re.compile(r"^episodes/(\S+) exists but is not listed")


def _fix_wb009(f: Finding, config: Path, lines: list[str], misplaced: set[str]) -> AutoFix | None:
    name = _UNLISTED_RE.match(f.message)
    if not name or f"episodes/{name.group(1)}" in misplaced:
        return None  # WB013 says it's probably not an episode at all
    start = next((i for i, line in enumerate(lines) if re.match(r"^episodes:\s*$", line)), None)
    if start is None:
        return None
    last = start
    for i in range(start + 1, len(lines)):
        if re.match(r"^\s*-\s+\S", lines[i]):
            last = i
        elif lines[i].strip() and not lines[i].startswith((" ", "\t", "#")):
            break
    item = re.match(r"^(\s*)-", lines[last]) if last != start else None
    indent = item.group(1) if item else ""
    return AutoFix(f, f"add {name.group(1)} to the end of config.yaml `episodes:`",
                   Edit(config, last, lines[last], f"{indent}- {name.group(1)}", insert=True))


def plan_autofixes(findings: list[Finding], lesson_dir: Path, codes: tuple[str, ...] = AUTOFIX_CODES) -> list[AutoFix]:
    """Proposed fixes for the findings that have a safe one, bottom-up within
    each file so applying one never shifts another's line."""
    misplaced = {f.location for f in findings if f.code == "WB013" and f.location}
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
            "WB009": lambda: _fix_wb009(f, path, lines, misplaced),
        }[f.code]()
        if fix is not None:
            fixes.append(fix)
    # Several WB009 inserts can land after the same line. Each insert goes
    # directly below it, so applying them in reverse name order leaves them in
    # name order; then sort (stably) bottom-up per file.
    fixes.sort(key=lambda x: x.finding.message, reverse=True)
    return sorted(fixes, key=lambda x: (str(x.edit.path), -x.edit.index))
