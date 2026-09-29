"""Unified CLI: fast mechanical checks, plus an optional AI narrative review.

    pixi run check <path-or-git-url> [options]

See README.md for the full flag reference and model recommendations.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

from checker.lesson_check import (
    GLOSSARY_PLACEHOLDER_FINGERPRINT,
    read_lesson_metadata,
    resolve_glossary_path,
    run_checks,
)
from checker.report import (
    render_html_via_quarto,
    render_json,
    render_markdown,
    render_pdf_via_quarto,
    render_terminal,
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _resolve_target(target: str) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    if target.startswith(("http://", "https://", "git@")):
        tmp = tempfile.TemporaryDirectory(prefix="carpentries-workbench-checker-")
        dest = Path(tmp.name) / "lesson"
        result = subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", target, str(dest)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            tmp.cleanup()
            raise SystemExit(f"failed to clone {target}: {result.stderr.strip()}")
        return dest, tmp
    path = Path(target).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"path not found: {path}")
    return path, None


def _write_or_print(text: str, output: str | None):
    if output:
        Path(output).write_text(text)
        print(f"wrote {output}", file=sys.stderr)
    else:
        print(text)


def _read_glossary(lesson_dir: Path) -> str:
    """The lesson's glossary content (learners/reference.md, or the legacy
    root-level reference.md, via the same resolver check_config()/
    check_support_files() use), empty string if missing or still the
    sandpaper scaffold placeholder -- feeding placeholder text to the AI
    review as if it were "the current glossary" would make it think existing
    terms are covered when nothing has actually been written yet. Using the
    same resolver as the other glossary checks matters: a legacy-path lesson
    with a real glossary must not read as empty here just because this
    function checked a different path than the one that actually exists."""
    glossary_path = resolve_glossary_path(lesson_dir)
    if glossary_path is None:
        return ""
    text = (lesson_dir / glossary_path).read_text(errors="replace")
    if GLOSSARY_PLACEHOLDER_FINGERPRINT in text.lower():
        return ""
    return text


_BLAME_TIMEOUT_SECONDS = 5
_BLAME_FIELD_SEP = "\x1f"  # ASCII unit separator -- won't collide with real author names


def _blame_map(lesson_dir: Path, findings: list) -> dict[str, str]:
    """Last author to change each finding's file, via `git log -1`.

    Turns a flat findings report into something closer to what filing GitHub
    issues per-owner needs: who to assign each file's fixes to. This is a
    routing hint (most recent activity), not an ownership claim -- a small
    formatting fix from someone who isn't the file's primary author still
    "wins" here, which is fine for "who'd remember this file's current
    state" but wrong for "who wrote most of it." Best-effort: a lesson_dir
    that isn't a git repo, a `git log` failure or timeout on one file, or
    a file with no commit history just means that location gets no
    annotation, not a crash.

    Uses `%aN` (author name, `.mailmap`-canonicalized) rather than `%an`
    (raw commit author), so the same person committing under different
    names/emails still attributes consistently.
    """
    locations = sorted({f.location for f in findings if f.location})
    blame: dict[str, str] = {}
    for location in locations:
        try:
            result = subprocess.run(
                [
                    "git", "log", "-1",
                    f"--format=%aN{_BLAME_FIELD_SEP}%ad{_BLAME_FIELD_SEP}%h",
                    "--date=short",
                    "--", location,
                ],
                cwd=lesson_dir,
                capture_output=True,
                text=True,
                timeout=_BLAME_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            continue
        if result.returncode != 0 or not result.stdout.strip():
            continue
        parts = result.stdout.strip().split(_BLAME_FIELD_SEP)
        if len(parts) != 3:
            continue
        author, date, short_sha = parts
        if author:
            blame[location] = f"{author}, {date}, {short_sha}"
    return blame


_GITHUB_REMOTE_RE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)(?P<org>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$"
)


def _github_blob_base(lesson_dir: Path) -> str | None:
    """`https://github.com/org/repo/blob/<current-sha>`, for turning
    location:line references in the markdown report into real clickable
    links. None if lesson_dir isn't a git repo, has no `origin` remote, that
    remote isn't github.com, or either git call fails/times out -- callers
    fall back to plain `path:line` text in every one of those cases, this
    is a pure enhancement, never required."""
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=lesson_dir,
            capture_output=True,
            text=True,
            timeout=_BLAME_TIMEOUT_SECONDS,
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=lesson_dir,
            capture_output=True,
            text=True,
            timeout=_BLAME_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return None
    if remote.returncode != 0 or sha.returncode != 0:
        return None
    match = _GITHUB_REMOTE_RE.match(remote.stdout.strip())
    if not match:
        return None
    return f"https://github.com/{match['org']}/{match['repo']}/blob/{sha.stdout.strip()}"


def _dirty_files(lesson_dir: Path) -> set[str]:
    """Paths (relative to `lesson_dir`) with uncommitted changes -- staged,
    unstaged, or untracked. Checks run against the working tree, but
    `_github_blob_base` links point at HEAD, so a finding on one of these
    paths would send the reader to a version of the file that doesn't
    contain what was actually checked. Empty set (not an error) if
    lesson_dir isn't a git repo or the call fails/times out."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--no-renames"],
            cwd=lesson_dir,
            capture_output=True,
            text=True,
            timeout=_BLAME_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return set()
    if result.returncode != 0:
        return set()
    # Porcelain format: 2 status chars, a space, then the path.
    return {line[3:] for line in result.stdout.splitlines() if len(line) > 3}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse args, run checks, render/write the report,
    optionally run the AI review. Returns 1 if any error-level finding was
    reported, 0 otherwise."""
    parser = argparse.ArgumentParser(description="Carpentries Workbench lesson checker")
    parser.add_argument("target", help="local lesson directory, or a git URL to clone and check")
    parser.add_argument("--episode", help="only check this one episode file (by filename)")
    parser.add_argument(
        "--format",
        choices=("terminal", "markdown", "json"),
        default=None,
        help="default: terminal when writing to stdout, inferred from --output's "
        "extension (.json -> json, .md/.markdown -> markdown, anything else -> "
        "markdown) when --output is given",
    )
    parser.add_argument("--output", help="write the report here instead of stdout")
    parser.add_argument(
        "--blame",
        action="store_true",
        help="annotate each file's findings with who last changed it, date, and short "
        "SHA (git log -1), "
        "useful for splitting a report into per-owner follow-up issues; requires "
        "lesson_dir to be a git repo, silently skipped otherwise",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="also render the markdown report to HTML with Quarto, if installed",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="open the rendered HTML report in your default browser (requires --html)",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="also render the markdown report to PDF with Quarto, if installed -- also "
        "needs a LaTeX distribution (`quarto install tinytex`, or an existing MacTeX/TeX "
        "Live on PATH); good for sharing with someone who doesn't want a repo checkout",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="also run an AI review of style/pedagogy (costs time and, for claude, API "
        "usage); `wbcheck review` saves the same review as structured findings",
    )
    parser.add_argument("--backend", choices=("ollama", "claude"), default="ollama")
    parser.add_argument("--model", help="override the default model for --backend")
    args = parser.parse_args(argv)

    # Infer the format from --output's extension when --format wasn't given
    # explicitly, so `--output report.md` doesn't silently save the
    # terminal renderer's raw ANSI escape codes -- an explicit --format
    # always wins over this inference.
    if args.format:
        resolved_format = args.format
    elif args.output:
        suffix = Path(args.output).suffix.lower().lstrip(".")
        resolved_format = {"json": "json", "md": "markdown", "markdown": "markdown"}.get(
            suffix, "markdown"
        )
    else:
        resolved_format = "terminal"

    lesson_dir, tmp = _resolve_target(args.target)
    try:
        findings = run_checks(lesson_dir, episode_filter=args.episode)
        title = f"Lesson Check Report — {args.target}"
        blame = _blame_map(lesson_dir, findings) if args.blame else None
        if args.blame and not blame:
            print(
                "--blame found no authors -- is lesson_dir a git repo with commit "
                "history for these files?",
                file=sys.stderr,
            )

        # Computed once, reused across every output format: who/what the
        # report is for, and (for markdown/html) how to link back to source.
        metadata = read_lesson_metadata(lesson_dir)
        github_base = _github_blob_base(lesson_dir)
        dirty_files = frozenset(_dirty_files(lesson_dir)) if github_base else frozenset()

        # Run AI review before rendering, not after, so its output can be
        # folded into whichever report format(s) get written below instead
        # of only ever landing on stdout. A per-episode failure (backend
        # down, API error, ...) is recorded as that episode's review text
        # rather than raised, so one bad episode doesn't cost the mechanical
        # results that were already computed.
        ai_reviews: dict[str, str] = {}
        if args.ai:
            from checker.ai_review import format_review_text, review_episode

            episodes_dir = lesson_dir / "episodes"
            episode_files = sorted(
                p for p in episodes_dir.glob("*") if p.suffix in (".md", ".Rmd")
            )
            if args.episode:
                episode_files = [p for p in episode_files if p.name == args.episode]
            glossary_text = _read_glossary(lesson_dir)
            for path in episode_files:
                relative_location = str(path.relative_to(lesson_dir))
                episode_findings = [f for f in findings if f.location == relative_location]
                label = f"{path.name} ({args.backend})"
                print(f"running AI review: {label}...", file=sys.stderr)
                try:
                    result = review_episode(
                        path.read_text(errors="replace"),
                        relative_location,
                        episode_findings,
                        args.backend,
                        model=args.model,
                        glossary_text=glossary_text,
                    )
                    ai_reviews[label] = format_review_text(result)
                except Exception as exc:  # noqa: BLE001 -- backend errors are unpredictable
                    print(f"AI review failed for {path.name}: {exc}", file=sys.stderr)
                    ai_reviews[label] = f"(AI review failed: {exc})"

        if resolved_format == "terminal":
            report_text = render_terminal(
                findings, title, blame=blame, metadata=metadata, ai_reviews=ai_reviews or None
            )
        elif resolved_format == "markdown":
            report_text = render_markdown(
                findings,
                title,
                blame=blame,
                github_base=github_base,
                metadata=metadata,
                ai_reviews=ai_reviews or None,
                dirty_files=dirty_files,
            )
        else:
            report_text = render_json(
                findings, title, metadata=metadata, ai_reviews=ai_reviews or None
            )

        # Terminal-format ANSI escapes are only useful on a live terminal --
        # strip them when writing to a file or when stdout itself has been
        # redirected/piped, regardless of format (a no-op for markdown/json,
        # which never contain them).
        if args.output or not sys.stdout.isatty():
            report_text = _ANSI_RE.sub("", report_text)

        _write_or_print(report_text, args.output)

        rendered_html = None
        if args.html or args.pdf:
            md_text = render_markdown(
                findings,
                title,
                blame=blame,
                github_base=github_base,
                metadata=metadata,
                ai_reviews=ai_reviews or None,
                dirty_files=dirty_files,
            )
            # The document title Quarto puts in the browser tab / PDF cover --
            # distinct from `title` above, which is the in-body H1 and already
            # includes the target path; this is what identifies the lesson at
            # a glance when the report's shared as a standalone file.
            qmd_title = f"{metadata.title} — Lesson Check Report" if metadata.title else title

            if args.html:
                out_path = (
                    Path(args.output).with_suffix(".html") if args.output else Path("report.html")
                )
                try:
                    rendered_html = render_html_via_quarto(md_text, out_path, report_title=qmd_title)
                except RuntimeError as exc:
                    print(f"quarto render failed, skipping HTML output: {exc}", file=sys.stderr)
                else:
                    if rendered_html is None:
                        print(
                            "quarto not found on PATH -- skipping HTML render "
                            "(install from https://quarto.org, or use --format markdown)",
                            file=sys.stderr,
                        )
                    else:
                        print(f"wrote {rendered_html}", file=sys.stderr)

            if args.pdf:
                pdf_out_path = (
                    Path(args.output).with_suffix(".pdf") if args.output else Path("report.pdf")
                )
                try:
                    rendered_pdf = render_pdf_via_quarto(md_text, pdf_out_path, report_title=qmd_title)
                except RuntimeError as exc:
                    print(f"quarto render failed, skipping PDF output: {exc}", file=sys.stderr)
                else:
                    if rendered_pdf is None:
                        print(
                            "quarto not found on PATH -- skipping PDF render "
                            "(install from https://quarto.org, or use --format markdown)",
                            file=sys.stderr,
                        )
                    else:
                        print(f"wrote {rendered_pdf}", file=sys.stderr)

        if args.open:
            if rendered_html is not None:
                webbrowser.open(rendered_html.resolve().as_uri())
            elif args.html:
                print("--open: no HTML file was rendered, nothing to open", file=sys.stderr)
            else:
                print("--open has no effect without --html", file=sys.stderr)

        error_count = sum(1 for f in findings if f.severity == "error")
        return 1 if error_count else 0
    finally:
        if tmp is not None:
            tmp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
