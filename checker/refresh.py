"""One way to bring a saved results file up to date (issues #3, #7, #8 of
the 2026-09-29 Codex review).

Every command that touches saved results (`check`, `review`, `fix`, and the
TUI's re-check) goes through `refresh()`, so they all follow the same
policy:

- **Identity.** Results record whose they are: `target_id` (the lesson's
  resolved path, or a normalized repo URL for a clone) and the git
  `revision`. Results saved for a different target are replaced, never
  merged. Clones of different repos get separate results folders.
- **Scope.** A full check replaces every mechanical finding. `check
  --episode` replaces only that episode's findings (plus lesson-level ones)
  and keeps the rest only if those files haven't changed; otherwise the
  results are marked `partial`.
- **Freshness.** Each checked file's content hash is recorded. AI findings
  are kept across refreshes, and marked `stale` when their file has changed
  since the review, rather than silently dropped or silently trusted.
- **IDs.** Mechanical finding IDs are assigned once by run_checks(), before
  any ignore rules apply, and are never renumbered. AI findings are
  numbered among themselves.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from checker.cli import _blame_map, _dirty_files, _github_blob_base
from checker.ignore import load_ignore
from checker.lesson_check import read_lesson_metadata, run_checks
from checker.report import Finding, assign_occurrences
from checker.results import RESULTS_DIRNAME, RESULTS_FILENAME, Results, load, save

_SCP_URL_RE = re.compile(r"^(?:ssh://)?git@([^:/]+)[:/](.+)$")


def normalize_target(target: str, lesson_dir: Path, is_clone: bool) -> str:
    """A stable identity for what was checked: the resolved directory for a
    local lesson, or `host/owner/repo` (lowercase host, no scheme or .git)
    for a clone, so https and ssh URLs of one repo match."""
    if not is_clone:
        return str(lesson_dir.resolve())
    url = target.strip().rstrip("/")
    scp = _SCP_URL_RE.match(url)
    if scp:
        host, path = scp.group(1), scp.group(2)
    else:
        url = re.sub(r"^[a-z]+://", "", url)
        url = re.sub(r"^[^@/]+@", "", url)  # credentials
        host, _, path = url.partition("/")
    path = re.sub(r"\.git$", "", path)
    return f"{host.lower()}/{path}"


def results_path_for(target_id: str, lesson_dir: Path, is_clone: bool, override: Path | None) -> Path:
    """Explicit --results wins; a clone gets its own folder under
    ./.wbcheck/ (the clone itself is deleted after the run); otherwise the
    results live inside the lesson."""
    if override is not None:
        return override
    if is_clone:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", target_id)
        return Path.cwd() / RESULTS_DIRNAME / slug / RESULTS_FILENAME
    return lesson_dir / RESULTS_DIRNAME / RESULTS_FILENAME


def git_revision(lesson_dir: Path) -> str | None:
    """HEAD's commit, or None if the lesson isn't a git repo."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=lesson_dir, capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def file_hashes(lesson_dir: Path) -> dict[str, str]:
    """Content hash of every file findings can point at: episodes,
    config.yaml, and the learners/instructors/profiles pages."""
    hashes: dict[str, str] = {}
    candidates = [lesson_dir / "config.yaml"]
    for folder in ("episodes", "learners", "instructors", "profiles"):
        if (lesson_dir / folder).is_dir():
            candidates += sorted((lesson_dir / folder).glob("*"))
    for path in candidates:
        if path.is_file():
            hashes[str(path.relative_to(lesson_dir))] = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
    return hashes


@dataclass
class RefreshNotes:
    """Things the caller should tell the user about."""

    replaced_target: str | None = None  # results for another lesson were discarded
    stale: int = 0  # AI findings whose file changed since review
    messages: list[str] = field(default_factory=list)


def _load_existing(path: Path) -> Results | None:
    if not path.exists():
        return None
    try:
        return load(path)
    except (ValueError, KeyError):
        return None


def _same_target(old: Results, target_id: str, target: str) -> bool:
    if old.target_id:
        return old.target_id == target_id
    return old.target == target  # results saved before target_id existed


def refresh(
    target: str,
    lesson_dir: Path,
    is_clone: bool,
    path: Path,
    episode: str | None = None,
    blame: bool = False,
) -> tuple[Results, RefreshNotes]:
    """Re-run the mechanical checks, merge with what's saved at `path` per
    the module's policy, apply .wbcheck.toml, save, and return the results.
    Raises ValueError for an invalid .wbcheck.toml."""
    rules = load_ignore(lesson_dir)
    notes = RefreshNotes()
    target_id = normalize_target(target, lesson_dir, is_clone)
    hashes = file_hashes(lesson_dir)
    fresh = run_checks(lesson_dir, episode_filter=episode)  # IDs assigned here, once

    old = _load_existing(path)
    if old is not None and not _same_target(old, target_id, target):
        notes.replaced_target = old.target
        old = None

    scope = "full"
    mechanical = fresh
    if episode:
        checked = f"episodes/{episode}"
        if old is not None and old.scope == "full":
            others = [
                f for f in old.findings
                if f.source != "ai" and (f.location or "").startswith("episodes/") and f.location != checked
            ]
            # every other episode file, not just ones with findings: an edited
            # file that was clean before may have new problems now
            other_files = {
                loc for loc in {*hashes, *old.file_hashes}
                if loc.startswith("episodes/") and loc != checked
            }
            unchanged = all(hashes.get(loc) == old.file_hashes.get(loc) for loc in other_files)
            if unchanged:
                mechanical = fresh + others
            else:
                scope = "partial"
        else:
            scope = "partial"

    ai: list[Finding] = []
    if old is not None:
        for f in old.findings:
            if f.source != "ai":
                continue
            if hashes.get(f.location or "") != old.file_hashes.get(f.location or ""):
                f.stale = True
            ai.append(f)
    ai = assign_occurrences(ai)  # AI numbered among themselves; mechanical IDs untouched
    notes.stale = sum(1 for f in ai if f.stale)

    kept, ignored = rules.apply(mechanical + ai)
    github_base = _github_blob_base(lesson_dir)
    results = Results(
        target=target,
        lesson_dir=None if is_clone else str(lesson_dir),
        findings=kept,
        metadata=read_lesson_metadata(lesson_dir),
        blame=_blame_map(lesson_dir, kept) if blame else None,
        github_base=github_base,
        dirty_files=sorted(_dirty_files(lesson_dir)) if github_base else [],
        ai_reviews=old.ai_reviews if old is not None else {},
        ignored=ignored,
        target_id=target_id,
        revision=git_revision(lesson_dir),
        scope=scope,
        file_hashes=hashes,
    )
    save(results, path)
    return results, notes


def merge_ai_review(results: Results, reviewed: dict[str, list[Finding]], lesson_dir: Path, path: Path) -> Results:
    """Replace the AI findings for each reviewed location with the new ones
    (fresh, not stale), re-number AI findings among themselves, apply
    .wbcheck.toml, and save."""
    rules = load_ignore(lesson_dir)
    ai = [f for f in results.findings if f.source == "ai" and f.location not in reviewed]
    for new in reviewed.values():
        ai.extend(new)
    ai = assign_occurrences(ai)
    mechanical = [f for f in results.findings if f.source != "ai"]
    results.findings, ignored_ai = rules.apply(mechanical + ai)
    results.ignored += ignored_ai
    save(results, path)
    return results
