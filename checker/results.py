"""The results file: one JSON document every `wbcheck` subcommand reads or
writes, so the fast mechanical check, the slow AI review, report rendering,
issue filing, and the TUI can run as separate steps (issue #24).

Default location is inside the checked lesson, `<lesson>/.wbcheck/results.json`,
with a `.gitignore` of `*` written alongside it so lesson repos don't need
to ignore it themselves (the same trick pytest's cache directory uses).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path

from checker import __version__
from checker.report import Finding, LessonMetadata

RESULTS_VERSION = 1
RESULTS_DIRNAME = ".wbcheck"
RESULTS_FILENAME = "results.json"


def default_results_path(base_dir: Path) -> Path:
    """`<base_dir>/.wbcheck/results.json`."""
    return base_dir / RESULTS_DIRNAME / RESULTS_FILENAME


def _finding_from_dict(data: dict) -> Finding:
    # `id` and `guides` are derived properties in the file, not fields.
    known = {f.name for f in fields(Finding)}
    return Finding(**{k: v for k, v in data.items() if k in known})


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
        }
        # default=str: config.yaml's unquoted `created:` is a datetime.date.
        return json.dumps(payload, indent=2, default=str)

    @classmethod
    def from_json(cls, text: str) -> Results:
        """Parse a results file; raises ValueError on an unsupported version."""
        data = json.loads(text)
        version = data.get("version")
        if version != RESULTS_VERSION:
            raise ValueError(
                f"results file version {version!r} is not supported (expected {RESULTS_VERSION}); "
                "re-run `wbcheck check`"
            )
        git = data.get("git") or {}
        return cls(
            target=data["target"],
            lesson_dir=data.get("lesson_dir"),
            findings=[_finding_from_dict(f) for f in data.get("findings", [])],
            metadata=_metadata_from_dict(data.get("lesson")),
            blame=git.get("blame"),
            github_base=git.get("github_base"),
            dirty_files=list(git.get("dirty_files") or []),
            ai_reviews=dict(data.get("ai_reviews") or {}),
            generated=data.get("generated") or "",
        )


def save(results: Results, path: Path) -> Path:
    """Write `results` to `path`, creating its directory. Inside a
    `.wbcheck/` directory, also drops a `*` .gitignore so the results never
    get committed to the lesson by accident."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.name == RESULTS_DIRNAME:
        gitignore = path.parent / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("# Created by wbcheck, safe to delete.\n*\n")
    path.write_text(results.to_json())
    return path


def load(path: Path) -> Results:
    """Read a results file written by `save`."""
    return Results.from_json(path.read_text())
