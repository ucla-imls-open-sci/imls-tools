"""Findings model and report renderers (terminal / markdown / json / html)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from checker import __version__
from checker.rules import Guide, get_rule

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
SEVERITY_ICON = {"error": "\033[31m❌\033[0m", "warning": "\033[33m⚠️\033[0m", "info": "ℹ️"}
SEVERITY_ICON_PLAIN = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}

# Category-wide fallback guide, used only for findings with no rule code
# (every mechanical check has one -- see checker/rules.py, which cites the
# specific guide section per rule). `boilerplate` has no entry deliberately:
# it's a check this tool invented, so there's no canonical page to point at.
CATEGORY_GUIDE_LINKS: dict[str, tuple[str, str]] = {
    "config": ("Episodes and lesson structure", "https://carpentries.github.io/sandpaper-docs/episodes.html"),
    "front-matter": ("Episode front matter", "https://carpentries.github.io/sandpaper-docs/episodes.html"),
    "divs": ("Workbench Component Guide", "https://carpentries.github.io/sandpaper-docs/component-guide.html"),
    "headings": ("Episodes and lesson structure", "https://carpentries.github.io/sandpaper-docs/episodes.html"),
    "links": ("Episodes and lesson structure", "https://carpentries.github.io/sandpaper-docs/episodes.html"),
    "objectives": (
        "CLDT: SMART objectives",
        "https://carpentries.github.io/lesson-development-training/aio.html",
    ),
    "style": (
        "Carpentries Lab reviewer checklist",
        "https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md",
    ),
}


# Spans whose digits are part of a finding's subject (a quoted bullet, a
# backticked filename like `03-data.md`) and must survive ID normalization.
_PROTECTED_SPAN_RE = re.compile(r"`[^`]*`|\"[^\"]*\"")
# "on line 14" / "line 14" references move whenever the file is edited above
# the finding; they are location, not identity.
_LINE_REF_RE = re.compile(r"\b(?:on )?lines? \d+\b")
# Counts ("7 contractions", "12.5 per 1,000 words") drift as prose changes
# without the underlying problem changing.
_NUMBER_RE = re.compile(r"\d[\d,.]*")


def _normalize_for_id(message: str) -> str:
    """Message text with line references and counts removed, except inside
    backtick/double-quote spans, so a finding's ID survives edits elsewhere
    in the file."""
    parts = []
    last = 0
    for match in _PROTECTED_SPAN_RE.finditer(message):
        parts.append(_NUMBER_RE.sub("#", _LINE_REF_RE.sub("", message[last:match.start()])))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_NUMBER_RE.sub("#", _LINE_REF_RE.sub("", message[last:])))
    return " ".join("".join(parts).lower().split())


@dataclass
class Finding:
    """One check result: a severity/category/message, where it applies, and
    optionally how to fix it. `code` ties it to a Rule in checker/rules.py;
    `source` is "mechanical" for these checks and "ai" for model findings,
    whose `quote` is the verbatim text they point at."""

    severity: str  # "error" | "warning" | "info"
    category: str  # "config" | "front-matter" | "divs" | "headings" | "links" | ...
    message: str
    location: str | None = None  # e.g. "episodes/01-intro.md" or "config.yaml"
    hint: str | None = None
    line: int | None = None  # 1-indexed source line, when the check knows one
    code: str | None = None  # e.g. "WB112", see checker/rules.py
    quote: str | None = None
    source: str = "mechanical"
    scope: str | None = None  # AI findings: groups related findings into one PR-sized issue
    # Nth repeat (in file order) of an otherwise-identical finding in the
    # same file, e.g. the 3rd duplicate `Exercise:` heading; set by
    # assign_occurrences(), 0 for the first/only one.
    occurrence: int = 0

    @property
    def identity_key(self) -> str:
        """Rule code (or category) + file + normalized message: what makes
        two findings "the same problem", before occurrence numbering."""
        return f"{self.code or self.category}|{self.location or ''}|{_normalize_for_id(self.message)}"

    @property
    def id(self) -> str:
        """Stable 12-hex-char identity: `identity_key` plus the occurrence
        number for repeats. Line numbers and counts are excluded, so the
        same problem keeps its ID when unrelated edits shift it around --
        what lets a re-run recognize a finding that already has an issue
        filed."""
        key = self.identity_key + (f"#{self.occurrence}" if self.occurrence else "")
        return hashlib.sha1(key.encode()).hexdigest()[:12]

    @property
    def guides(self) -> tuple[Guide, ...]:
        """Guide citations for this finding, most specific first: the rule's
        own citations, falling back to the category-wide link for findings
        without a registered code."""
        rule = get_rule(self.code)
        if rule is not None:
            return rule.guides
        entry = CATEGORY_GUIDE_LINKS.get(self.category)
        return (entry,) if entry else ()

    def to_dict(self) -> dict:
        """JSON-ready dict: every field plus the derived `id` and `guides`."""
        data = asdict(self)
        data["id"] = self.id
        data["guides"] = [{"label": label, "url": url} for label, url in self.guides]
        return data

    def sort_key(self):
        """Sort errors before warnings before info, then group by location,
        then by line within a location."""
        return (
            SEVERITY_ORDER.get(self.severity, 9),
            self.location or "",
            self.line if self.line is not None else -1,
            self.category,
        )


def assign_occurrences(findings: list[Finding]) -> list[Finding]:
    """Number repeats of the same identity_key in file order (by line), so
    each occurrence gets a distinct, still line-independent ID. Mutates and
    returns `findings`."""
    seen: dict[str, int] = {}
    ordered = sorted(
        findings, key=lambda f: (f.location or "", f.line if f.line is not None else -1)
    )
    for f in ordered:
        key = f.identity_key
        f.occurrence = seen.get(key, 0)
        seen[key] = f.occurrence + 1
    return findings


@dataclass
class LessonMetadata:
    """Lesson identity for the report header, read from config.yaml and (if
    present) CITATION.cff -- see lesson_check.read_lesson_metadata(). Purely
    descriptive context for whoever reads the report, not a check result;
    every field is optional since not every lesson has all of this filled
    in (or a CITATION.cff at all)."""

    title: str | None = None
    carpentry: str | None = None  # friendly name, e.g. "Library Carpentry"
    life_cycle: str | None = None
    license: str | None = None
    source: str | None = None
    contact: str | None = None
    created: str | None = None
    authors: list[str] = field(default_factory=list)

    def has_content(self) -> bool:
        """Whether there's anything worth rendering -- false when config.yaml
        itself was missing or empty, so the header block can be skipped
        entirely rather than printed blank."""
        return bool(self.title or self.carpentry or self.source or self.authors)


def summarize(findings: list[Finding]) -> dict[str, int]:
    """Count findings per severity."""
    counts = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def _blame_suffix(location: str, blame: dict[str, str] | None) -> str:
    if not blame:
        return ""
    author = blame.get(location)
    return f" (last change authored by: {author})" if author else ""


def _guide_suffix(finding: Finding) -> str:
    """Appendable ' (see: Label, url)' text for the terminal, citing the
    finding's primary guide; empty if it has none."""
    guides = finding.guides
    return f" (see: {guides[0][0]}, {guides[0][1]})" if guides else ""


def _guide_link_markdown(finding: Finding) -> str:
    """Every guide citation for the finding as markdown links, ' · '-joined."""
    return "".join(
        f"{' ·' if i else ''} [{label}]({url})" for i, (label, url) in enumerate(finding.guides)
    )


def _code_label(finding: Finding) -> str:
    """`WB112` when the finding has a rule code, else its category."""
    return finding.code or finding.category


def _terminal_location_prefix(location: str, line: int | None) -> str:
    """`path:line` token, left plain (no ANSI) so terminals that recognize
    that pattern (VS Code's integrated terminal, several others) can turn it
    into a clickable jump-to-line link."""
    return f"{location}:{line} " if line is not None else ""


def _markdown_location_link(
    location: str,
    line: int | None,
    github_base: str | None,
    dirty_files: frozenset[str] = frozenset(),
) -> str:
    """A clickable `path:line` reference for the markdown report. Prefers a
    real GitHub blob URL anchored to the line (works when pasted into a PR,
    an issue, or opened in a browser); falls back to plain `path:line` text
    when the lesson isn't a GitHub repo, has no clean remote, or -- since
    `github_base` is pinned to HEAD while checks read the working tree --
    `location` has uncommitted changes, where a HEAD link could easily point
    at a version of the file that doesn't contain what was actually
    flagged."""
    label = f"{location}:{line}" if line is not None else location
    if github_base and location not in dirty_files:
        anchor = f"#L{line}" if line is not None else ""
        return f"[{label}]({github_base}/{location}{anchor})"
    if location in dirty_files:
        return f"`{label}` (uncommitted, not yet on GitHub)"
    return f"`{label}`"


def _lesson_metadata_lines(
    metadata: LessonMetadata | None, bold_open: str = "", bold_close: str = ""
) -> list[str]:
    """Plain-text lesson-identity lines shared by terminal/markdown: title
    (wrapped in the caller's own bold markup), carpentry/life cycle/license
    tags, source repo, authors, contact. Empty list if there's nothing to
    show -- e.g. config.yaml was missing or empty."""
    if metadata is None or not metadata.has_content():
        return []
    lines = []
    header_bits = []
    if metadata.title:
        header_bits.append(f"{bold_open}{metadata.title}{bold_close}")
    tags = [t for t in (metadata.carpentry,) if t]
    if metadata.life_cycle:
        tags.append(f"life cycle: {metadata.life_cycle}")
    if metadata.license:
        tags.append(f"license: {metadata.license}")
    if tags:
        header_bits.append(f"({', '.join(tags)})")
    if header_bits:
        lines.append(" ".join(header_bits))
    if metadata.source:
        lines.append(f"Source: {metadata.source}")
    if metadata.authors:
        lines.append(f"Authors: {', '.join(metadata.authors)}")
    if metadata.contact:
        lines.append(f"Contact: {metadata.contact}")
    return lines


def render_terminal(
    findings: list[Finding],
    title: str,
    blame: dict[str, str] | None = None,
    metadata: LessonMetadata | None = None,
    ai_reviews: dict[str, str] | None = None,
) -> str:
    """Colored, grouped-by-location report for a terminal.

    `ai_reviews` (label -> review text or recorded failure), when given, is
    appended as its own section so `--ai` output lands in the same report
    as the mechanical findings instead of being printed separately after.
    """
    lines = [f"\033[1m{title}\033[0m"]
    lines.extend(_lesson_metadata_lines(metadata, bold_open="\033[1m", bold_close="\033[0m"))
    if metadata is not None and metadata.has_content():
        lines.append("")
    counts = summarize(findings)
    lines.append(
        f"carpentries-workbench-checker v{__version__} · {counts['error']} error(s), "
        f"{counts['warning']} warning(s), {counts['info']} note(s)"
    )
    if not findings:
        lines.append("\033[32m✅ No issues found\033[0m")
    else:
        by_location: dict[str, list[Finding]] = {}
        for f in sorted(findings, key=Finding.sort_key):
            by_location.setdefault(f.location or "general", []).append(f)

        for location, items in by_location.items():
            lines.append(f"\n\033[1m{location}\033[0m{_blame_suffix(location, blame)}")
            for f in items:
                icon = SEVERITY_ICON.get(f.severity, "")
                prefix = _terminal_location_prefix(location, f.line)
                lines.append(f"  {icon} {prefix}[{_code_label(f)}] {f.message}")
                if f.hint:
                    lines.append(f"     → {f.hint}{_guide_suffix(f)}")
                elif f.guides:
                    lines.append(f"     →{_guide_suffix(f)}")

    if ai_reviews:
        lines.append("\n\033[1mAI review\033[0m")
        for label, text in ai_reviews.items():
            lines.append(f"\n\033[1m{label}\033[0m")
            lines.append(text)

    return "\n".join(lines)


_ANCHOR_STRIP_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def _anchor(text: str) -> str:
    """Best-effort GitHub-flavored-markdown heading anchor: lowercase, strip
    everything except word characters/spaces/hyphens, then spaces -> hyphens.
    Used for file-path headings (`episodes/01-intro.md` -> a slug with no
    `/`/`.`), matching GitHub's own algorithm closely enough for the paths
    that actually appear here."""
    slug = _ANCHOR_STRIP_RE.sub("", text.lower())
    return re.sub(r"\s+", "-", slug.strip())


def _group_by_category_and_hint(
    items: list[Finding],
) -> list[tuple[str, str | None, list[Finding]]]:
    """Findings grouped by (category, exact shared `hint` text), largest
    group first. Findings with no hint never merge with each other just
    because both lack one -- each stays its own singleton, since two
    unrelated problems that both happen to lack a hint are not the same
    fix. Grouping is keyed on the literal `hint` string, not a stripped/
    normalized `message` -- normalizing message text is what would
    eventually merge unrelated findings or silently stop grouping when
    wording changes elsewhere. Shared by the cross-file Action Summary
    table and each file's detail section."""
    hinted: dict[tuple[str, str], list[Finding]] = {}
    singles: list[Finding] = []
    for f in items:
        if f.hint:
            hinted.setdefault((f.category, f.hint), []).append(f)
        else:
            singles.append(f)
    groups = sorted(hinted.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    result: list[tuple[str, str | None, list[Finding]]] = [
        (category, hint, group_items) for (category, hint), group_items in groups
    ]
    result += [(f.category, None, [f]) for f in singles]
    return result


def _grouped_sections(
    findings: list[Finding],
) -> list[tuple[str, str, str | None, list[Finding]]]:
    """Findings grouped into (severity, category, hint) patterns for the
    Action Summary table: one row per exact shared corrective action,
    ordered by severity (errors, then warnings, then notes), largest
    pattern first within a severity. See `_group_by_category_and_hint` for
    how a shared fix is identified."""
    by_severity: dict[str, list[Finding]] = {}
    for f in sorted(findings, key=Finding.sort_key):
        by_severity.setdefault(f.severity, []).append(f)

    sections = []
    for severity, items in by_severity.items():
        for category, hint, group_items in _group_by_category_and_hint(items):
            sections.append((severity, category, hint, group_items))

    sections.sort(key=lambda s: (SEVERITY_ORDER.get(s[0], 9), -len(s[3]), s[1]))
    return sections


def _render_file_finding_group(
    hint: str | None,
    items: list[Finding],
    github_base: str | None,
    guide_link: str,
    dirty_files: frozenset[str] = frozenset(),
) -> list[str]:
    """One blockquote within a file's section: a shared fix (if `hint` is
    set) leading a checklist of every line in *this file* it applies to, or
    -- for a hint-less singleton -- just that one finding. Each occurrence
    line carries its own severity icon (a file section can mix severities,
    unlike the old severity-scoped design). The guide link (once, not once
    per occurrence) closes the block."""
    lines = [f"> **Change:** {hint}", ">"] if hint else []
    for f in items:
        icon = SEVERITY_ICON_PLAIN.get(f.severity, "")
        prefix = "- [ ]" if f.severity in ("error", "warning") else "-"
        where = _markdown_location_link(f.location or "General", f.line, github_base, dirty_files)
        quote = f' _“{f.quote}”_' if f.quote else ""
        lines.append(f"> {prefix} {icon} {where} — `{_code_label(f)}` {f.message}{quote}")
    if guide_link:
        lines.append(">")
        lines.append(f"> **Guide:**{guide_link}")
    return lines


def render_markdown(
    findings: list[Finding],
    title: str,
    blame: dict[str, str] | None = None,
    github_base: str | None = None,
    metadata: LessonMetadata | None = None,
    ai_reviews: dict[str, str] | None = None,
    dirty_files: frozenset[str] = frozenset(),
) -> str:
    """PR/issue-ready report: a file-level checklist for triage, an Action
    Summary of every shared fix pattern across the whole lesson (so a
    repeated problem, e.g. 16 duplicate-heading warnings, is visible as one
    row instead of scattered lines), then findings grouped file-first --
    matching the order someone actually fixes them in an editor -- with
    same-fix findings inside a file still collapsed into one change/
    checklist rather than N separate cards.

    `github_base` (e.g. `https://github.com/org/repo/blob/<sha>`), when
    given, turns every location:line reference into a real clickable GitHub
    link instead of plain text -- see `cli._github_blob_base`. Checks read
    the working tree, but this link is pinned to a single commit, so
    `dirty_files` (paths with uncommitted changes, relative to the lesson
    root -- see `cli._dirty_files`) tells the renderer which locations to
    leave as plain text instead of a link that may not show what was
    actually flagged. `metadata` (see `LessonMetadata`), when given, adds a
    lesson-identity block (title, carpentry, authors, ...) below the report
    title. `ai_reviews` (label -> review text or recorded failure), when
    given, is appended as its own section, so `--ai --output report.md`
    actually saves that output instead of only printing it to stdout after
    this report is written.
    """
    counts = summarize(findings)
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# {title}", ""]
    metadata_lines = _lesson_metadata_lines(metadata, bold_open="**", bold_close="**")
    if metadata_lines:
        # Trailing double-space = a CommonMark/GFM hard line break, so these
        # render as separate lines instead of collapsing into one reflowed
        # paragraph (Markdown treats consecutive non-blank lines as the same
        # paragraph otherwise).
        lines.extend(f"{line}  " for line in metadata_lines)
        lines.append("")
    lines.append(
        f"Generated {generated} by carpentries-workbench-checker v{__version__} · "
        f"{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} note(s)"
    )
    if github_base:
        sha = github_base.rsplit("/", 1)[-1]
        lines.append(
            f"GitHub links point at commit `{sha[:12]}`. Files with uncommitted "
            "changes at generation time are shown as plain text instead, since "
            "that commit may not contain what was actually checked."
        )
    lines.append("")
    if not findings:
        lines.append("All checks passed. Nothing to address before opening a PR.")
        lines.append("")
    else:
        by_location: dict[str, list[Finding]] = {}
        for f in sorted(findings, key=Finding.sort_key):
            by_location.setdefault(f.location or "General", []).append(f)

        # File-level overview: which files need attention, linking down to
        # that file's own detail section (file-first grouping below means a
        # file again corresponds to exactly one section, same as
        # pre-restructure).
        lines.append("## Files")
        lines.append("")
        for location, items in by_location.items():
            actionable = sum(1 for f in items if f.severity in ("error", "warning"))
            box = "- [ ]" if actionable else "-"
            count_label = f"{actionable} issue(s)" if actionable else f"{len(items)} note(s) only"
            lines.append(f"{box} [{location}](#{_anchor(location)}) — {count_label}")
        lines.append("")

        # Action summary: every shared-fix pattern across the whole lesson,
        # so a problem repeated in many files (e.g. 16 duplicate-heading
        # warnings) is visible as one row here even though the detail
        # section below is file-first and will show it once per file. No
        # deep links -- a cross-file pattern has no single section it
        # "belongs" to.
        lines.append("## Action summary")
        lines.append("")
        lines.append("| Priority | What to change | Occurrences | Files |")
        lines.append("|---|---|---:|---:|")
        for severity, _category, hint, items in _grouped_sections(findings):
            icon = SEVERITY_ICON_PLAIN.get(severity, "")
            what = hint or items[0].message
            n_files = len({f.location for f in items if f.location})
            lines.append(f"| {icon} {severity.capitalize()} | {what} | {len(items)} | {n_files} |")
        lines.append("")

        # Detail section: file-first, matching the order someone actually
        # fixes things in an editor. Within a file, same-fix findings still
        # collapse into one change/checklist instead of N separate cards.
        for location, items in by_location.items():
            lines.append(f"## {location}{_blame_suffix(location, blame)}")
            lines.append("")
            for _category, hint, group_items in _group_by_category_and_hint(items):
                guide_link = _guide_link_markdown(group_items[0])
                lines.extend(
                    _render_file_finding_group(
                        hint, group_items, github_base, guide_link, dirty_files
                    )
                )
                lines.append("")

    if ai_reviews:
        lines.append("## AI review")
        lines.append("")
        for label, text in ai_reviews.items():
            lines.append(f"### {label}")
            lines.append("")
            lines.append(text)
            lines.append("")

    return "\n".join(lines) + ("\n" if not findings and not ai_reviews else "")


def render_json(
    findings: list[Finding],
    title: str,
    metadata: LessonMetadata | None = None,
    ai_reviews: dict[str, str] | None = None,
) -> str:
    """Machine-readable report, e.g. for a caller's own CI step. `ai_reviews`
    (label -> review text or recorded failure), when given, is included in
    this same JSON payload rather than printed separately afterward, so a
    caller piping stdout doesn't get a JSON document followed by prose."""
    payload = {
        "title": title,
        "generated": datetime.now(UTC).isoformat(),
        "generated_by": {"name": "carpentries-workbench-checker", "version": __version__},
        "lesson": asdict(metadata) if metadata is not None else None,
        "summary": summarize(findings),
        "findings": [f.to_dict() for f in findings],
        "ai_reviews": ai_reviews or None,
    }
    # default=str: config.yaml's unquoted `created: 2026-01-01` parses as a
    # datetime.date, which json can't serialize on its own.
    return json.dumps(payload, indent=2, default=str)


# The "checker-report" Quarto format extension (checker/quarto/_extensions/,
# inside the package so it ships with installs) owns the report's actual look
# (theme, PDF margins, toc). Quarto only discovers an `_extensions/`
# directory that's a sibling of the .qmd being rendered, so
# _render_via_quarto copies it into the temp render directory each time.
_EXTENSION_NAME = "checker-report"
_EXTENSION_SRC = Path(__file__).resolve().parent / "quarto" / "_extensions" / _EXTENSION_NAME


def _render_via_quarto(
    markdown_text: str, out_path: Path, to: str, report_title: str
) -> Path | None:
    """Shared by render_html_via_quarto/render_pdf_via_quarto: write the report
    as a .qmd using the checker-report format extension, render it to `to`
    ("html"/"pdf"), and copy the result to out_path. Returns None if quarto
    isn't on PATH at all (caller should fall back to the plain markdown/
    terminal report, not fail). Raises RuntimeError if quarto is present but
    the render itself fails -- e.g. no LaTeX distribution for a PDF render --
    so that doesn't get silently swallowed and mistaken for "quarto missing"."""
    if shutil.which("quarto") is None:
        return None
    if not _EXTENSION_SRC.is_dir():
        raise RuntimeError(
            f"checker-report Quarto extension not found at {_EXTENSION_SRC} -- "
            "this is a broken install, not a missing dependency"
        )

    with tempfile.TemporaryDirectory() as tmp:
        # Resolve symlinks (macOS puts TemporaryDirectory() under /var, which
        # is itself a symlink to /private/var) before handing the path to
        # quarto -- otherwise quarto resolves cwd internally, computes the
        # output path relative to that resolved directory, and produces a
        # "../../../../private/..." path that doesn't match the unresolved
        # cwd we gave it, failing with a permission error on /private.
        tmp_dir = Path(tmp).resolve()
        shutil.copytree(_EXTENSION_SRC, tmp_dir / "_extensions" / _EXTENSION_NAME)
        qmd_path = tmp_dir / "report.qmd"
        quarto_format = f"{_EXTENSION_NAME}-{to}"
        # yaml.safe_dump, not an f-string, because report_title is a lesson's
        # actual title -- arbitrary text that can contain colons, quotes, or
        # unicode that would otherwise break the YAML front matter.
        front_matter = yaml.safe_dump(
            {"title": report_title, "format": {quarto_format: "default"}},
            sort_keys=False,
            allow_unicode=True,
        )
        qmd_path.write_text(f"---\n{front_matter}---\n\n" + markdown_text)
        result = subprocess.run(
            ["quarto", "render", str(qmd_path), "--to", quarto_format, "-o", out_path.name],
            cwd=tmp_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"quarto render failed: {result.stderr.strip()}")
        rendered = tmp_dir / out_path.name
        out_path.write_bytes(rendered.read_bytes())
    return out_path


def render_html_via_quarto(
    markdown_text: str, out_path: Path, report_title: str = "Lesson Check Report"
) -> Path | None:
    """Render a markdown report to HTML with Quarto, if it's installed. See
    `_render_via_quarto` for the None/RuntimeError contract."""
    return _render_via_quarto(markdown_text, out_path, "html", report_title)


def render_pdf_via_quarto(
    markdown_text: str, out_path: Path, report_title: str = "Lesson Check Report"
) -> Path | None:
    """Render a markdown report to PDF with Quarto, if it's installed and a
    LaTeX distribution is available (`quarto install tinytex`, or an existing
    MacTeX/TeX Live install on PATH). See `_render_via_quarto` for the
    None/RuntimeError contract -- a missing LaTeX engine surfaces as a
    RuntimeError with quarto's own error text, not a silent None, since
    quarto being on PATH doesn't guarantee PDF rendering works."""
    return _render_via_quarto(markdown_text, out_path, "pdf", report_title)
