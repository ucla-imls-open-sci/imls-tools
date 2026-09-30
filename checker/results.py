"""The results file: one JSON document every `wbcheck` subcommand reads or
writes, so the fast mechanical check, the slow AI review, report rendering,
issue filing, and the TUI can run as separate steps (issue #24).

Default location is inside the checked lesson, `<lesson>/.wbcheck/results.json`,
with a `.gitignore` of `*` written alongside it so lesson repos don't need
to ignore it themselves (the same trick pytest's cache directory uses).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path

from checker import __version__
from checker.report import Finding, LessonMetadata, _normalize_for_id

# v3 adds Finding.identity_anchor, which keeps a finding's ID stable when its
# message wording changes. A pre-v3 wbcheck rejects a v3 file (unsupported
# version) rather than recompute IDs from the new wording; re-run
# `wbcheck check` with that version to rebuild, or upgrade.
RESULTS_VERSION = 3
READABLE_VERSIONS = (1, 2, 3)  # v1 lacks target_id/revision/scope/file_hashes; read with defaults
RESULTS_DIRNAME = ".wbcheck"
RESULTS_FILENAME = "results.json"


def default_results_path(base_dir: Path) -> Path:
    """`<base_dir>/.wbcheck/results.json`."""
    return base_dir / RESULTS_DIRNAME / RESULTS_FILENAME


def _finding_from_dict(data: dict, version: int = RESULTS_VERSION) -> Finding:
    # `id` and `guides` are derived properties in the file, not fields. The
    # serialized `id` is never trusted over the inputs it's derived from.
    known = {f.name for f in fields(Finding)}
    finding = Finding(**{k: v for k, v in data.items() if k in known})
    if finding.identity_anchor is not None and not isinstance(finding.identity_anchor, str):
        raise ValueError(f"identity_anchor must be a string, got {type(finding.identity_anchor).__name__}")
    if version < 3 and finding.identity_anchor is None and finding.source != "ai":
        # Freeze the anchor from the message as it was written, so a later
        # rewording of that rule's message can't change this finding's ID.
        finding.identity_anchor = _normalize_for_id(finding.message)
    return finding


def _metadata_from_dict(data: dict | None) -> LessonMetadata | None:
    if data is None:
        return None
    known = {f.name for f in fields(LessonMetadata)}
    return LessonMetadata(**{k: v for k, v in data.items() if k in known})


@dataclass
class Results:
    """Everything a check/review run produced, plus the git context needed
    to render links later exactly as they were at check time."""

    target: str  # what the user passed: a path or a git URL
    lesson_dir: str | None  # absolute path, None when checked from a temporary clone
    findings: list[Finding] = field(default_factory=list)
    metadata: LessonMetadata | None = None
    blame: dict[str, str] | None = None
    github_base: str | None = None
    dirty_files: list[str] = field(default_factory=list)
    ai_reviews: dict[str, str] = field(default_factory=dict)
    ignored: int = 0  # findings suppressed by the lesson's .wbcheck.toml
    target_id: str | None = None  # resolved lesson path, or host/owner/repo for a clone
    revision: str | None = None  # git HEAD at check time
    scope: str = "full"  # "full", or "partial" after an --episode check that couldn't merge
    file_hashes: dict[str, str] = field(default_factory=dict)  # location -> content hash at check time
    generated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def title(self) -> str:
        """Report heading, matching the legacy CLI's."""
        return f"Lesson Check Report — {self.target}"

    @property
    def error_count(self) -> int:
        """Number of error-severity findings (drives the exit code)."""
        return sum(1 for f in self.findings if f.severity == "error")

    def to_json(self) -> str:
        """Serialize, including each finding's derived `id` and `guides`."""
        payload = {
            "version": RESULTS_VERSION,
            "generated_by": {"name": "carpentries-workbench-checker", "version": __version__},
            "generated": self.generated,
            "target": self.target,
            "lesson_dir": self.lesson_dir,
            "lesson": asdict(self.metadata) if self.metadata is not None else None,
            "git": {
                "github_base": self.github_base,
                "dirty_files": sorted(self.dirty_files),
                "blame": self.blame,
            },
            "findings": [f.to_dict() for f in self.findings],
            "ai_reviews": self.ai_reviews,
            "ignored": self.ignored,
            "target_id": self.target_id,
            "revision": self.revision,
            "scope": self.scope,
            "file_hashes": self.file_hashes,
        }
        # default=str: config.yaml's unquoted `created:` is a datetime.date.
        return json.dumps(payload, indent=2, default=str)

    @classmethod
    def from_json(cls, text: str) -> Results:
        """Parse a results file. Raises ResultsFormatError (a ValueError)
        for anything unreadable: bad JSON, the wrong shape, or an
        unsupported version."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResultsFormatError(f"results file is not valid JSON ({exc.msg}); {RECOVER}") from exc
        if not isinstance(data, dict):
            raise ResultsFormatError(f"results file is not a JSON object; {RECOVER}")
        version = data.get("version")
        if version not in READABLE_VERSIONS:
            raise ResultsFormatError(
                f"results file version {version!r} is not supported (expected {RESULTS_VERSION}); {RECOVER}"
            )
        try:
            return cls._from_dict(data)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise ResultsFormatError(f"results file is damaged ({type(exc).__name__}: {exc}); {RECOVER}") from exc

    @classmethod
    def _from_dict(cls, data: dict) -> Results:
        git = data.get("git") or {}
        return cls(
            target=data["target"],
            lesson_dir=data.get("lesson_dir"),
            findings=[_finding_from_dict(f, data["version"]) for f in data.get("findings", [])],
            metadata=_metadata_from_dict(data.get("lesson")),
            blame=git.get("blame"),
            github_base=git.get("github_base"),
            dirty_files=list(git.get("dirty_files") or []),
            ai_reviews=dict(data.get("ai_reviews") or {}),
            ignored=int(data.get("ignored") or 0),
            target_id=data.get("target_id"),
            revision=data.get("revision"),
            scope=data.get("scope") or "full",
            file_hashes=dict(data.get("file_hashes") or {}),
            generated=data.get("generated") or "",
        )


class ResultsFormatError(ValueError):
    """A results file that can't be read."""


RECOVER = "re-run `wbcheck check` to rebuild it"


def save(results: Results, path: Path) -> Path:
    """Write `results` to `path`, creating its directory. Inside a
    `.wbcheck/` directory, also drops a `*` .gitignore so the results never
    get committed to the lesson by accident."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # the .wbcheck folder itself, even when results sit in a per-clone subfolder
    wbcheck_dir = next((p for p in (path.parent, *path.parent.parents) if p.name == RESULTS_DIRNAME), None)
    if wbcheck_dir is not None:
        gitignore = wbcheck_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("# Created by wbcheck, safe to delete.\n*\n")
    # Write then rename, so an interrupted save never leaves a half-written file.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(results.to_json())
    os.replace(tmp, path)
    return path


def load(path: Path) -> Results:
    """Read a results file written by `save`."""
    return Results.from_json(path.read_text())
