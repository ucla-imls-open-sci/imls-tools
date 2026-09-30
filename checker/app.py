"""`wbcheck`: subcommand CLI built around a results file (issue #24).

    wbcheck check  <lesson>        fast mechanical checks -> <lesson>/.wbcheck/results.json
    wbcheck review <lesson>        add the AI narrative review to the same results file
    wbcheck report [<lesson>]      render saved results: terminal, --md, --html, --pdf, --json

Each step reads or writes the results file, so the slow AI pass runs
separately from the fast checks, and reports can be re-rendered without
re-checking. The older flag-based entry point (`pixi run check`,
checker/cli.py) still works unchanged during the transition.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text

from checker import __version__
from checker.cli import _read_glossary, _resolve_target
from checker.console import render_ai_reviews, render_findings, render_results
from checker.ignore import IgnoreRules, load_ignore
from checker.lesson_check import run_checks
from checker.report import (
    SEVERITY_ORDER,
    Finding,
    render_html_via_quarto,
    render_markdown,
    render_pdf_via_quarto,
)
from checker.results import Results, default_results_path, load

app = typer.Typer(
    name="wbcheck",
    help="Fast local checks for Carpentries Workbench lessons, with an optional AI review.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)

# Diagnostics go to stderr so stdout stays clean for piping a report.
err = Console(stderr=True, soft_wrap=True)


def _version_callback(value: bool) -> None:
    if value:
        print(f"wbcheck {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version.")
    ] = False,
) -> None:
    pass


def _load_ignore_or_exit(lesson_dir: Path) -> IgnoreRules:
    try:
        return load_ignore(lesson_dir)
    except ValueError as exc:
        err.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from exc


FAIL_ON = ("error", "warning", "info", "never")


def _fails(results: Results, fail_on: str) -> bool:
    """Whether any finding is at least as severe as `fail_on`."""
    if fail_on == "never":
        return False
    threshold = SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER.get(f.severity, 9) <= threshold for f in results.findings)


def _refresh(
    target: str, episode: str | None, blame: bool, results_override: Path | None
) -> tuple[Results, Path, tempfile.TemporaryDirectory | None, Path]:
    """Resolve `target`, bring its saved results up to date (see
    checker/refresh.py for the merge policy), and report anything notable.
    Returns the results, the lesson directory, the temp-clone handle (None
    for a local path; the caller cleans it up), and the results path."""
    from checker.refresh import normalize_target, refresh, results_path_for

    lesson_dir, tmp = _resolve_target(target)
    is_clone = tmp is not None
    path = results_path_for(normalize_target(target, lesson_dir, is_clone), lesson_dir, is_clone, results_override)
    try:
        results, notes = refresh(target, lesson_dir, is_clone, path, episode=episode, blame=blame)
    except ValueError as exc:  # invalid .wbcheck.toml
        if tmp is not None:
            tmp.cleanup()
        err.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from exc
    for message in notes.messages:
        err.print(f"[yellow]{message}[/]")
    if notes.replaced_target:
        err.print(f"[yellow]replaced saved results for a different lesson[/] ({notes.replaced_target})")
    if notes.stale:
        err.print(f"[yellow]{notes.stale} AI finding(s) are stale[/]: their file changed since the review; "
                  "re-run `wbcheck review` for those episodes")
    if results.scope == "partial":
        err.print("[dim]partial results: only the requested episode is up to date; run a full check to refresh "
                  "the rest[/]")
    if blame and not results.blame:
        err.print("[yellow]--blame found no authors[/] (is the lesson a git repo with history?)")
    return results, lesson_dir, tmp, path


@app.command()
def check(
    target: Annotated[str, typer.Argument(help="Lesson directory, or a git URL to clone and check.")] = ".",
    episode: Annotated[str | None, typer.Option(help="Only check this episode file (by filename).")] = None,
    blame: Annotated[bool, typer.Option(help="Record who last changed each file with findings.")] = False,
    results_path: Annotated[
        Path | None, typer.Option("--results", help="Where to save results (default: <lesson>/.wbcheck/results.json).")
    ] = None,
    show_source: Annotated[bool, typer.Option("--source", help="Show the source line under each finding.")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Save results without printing the report.")] = False,
    fail_on: Annotated[
        str,
        typer.Option(help="Exit 1 if any finding is at least this severe: error, warning, info, or never."),
    ] = "error",
    changed: Annotated[
        bool, typer.Option("--changed", help="Only show findings in files with uncommitted changes.")
    ] = False,
    since: Annotated[
        str | None, typer.Option(help="With --changed, also include files changed since this git ref (e.g. main).")
    ] = None,
) -> None:
    """Run the fast mechanical checks and save the results. Exits 1 on errors (see --fail-on).

    --changed narrows what's shown and what counts toward the exit code; the
    saved results still hold every finding, for the TUI, reports, and issues.
    """
    if fail_on not in FAIL_ON:
        err.print(f"[red]--fail-on must be one of {', '.join(FAIL_ON)}[/], got `{fail_on}`")
        raise typer.Exit(2)
    results, lesson_dir, tmp, path = _refresh(target, episode, blame, results_path)
    try:
        shown = _changed_view(results, lesson_dir, since) if (changed or since) else results
        if not quiet:
            render_results(Console(), shown, show_source=show_source)
        err.print(f"[dim]saved {path}[/]")
    finally:
        if tmp is not None:
            tmp.cleanup()
    raise typer.Exit(1 if _fails(shown, fail_on) else 0)


def _changed_view(results: Results, lesson_dir: Path, since: str | None) -> Results:
    """A copy of `results` holding only findings in changed files."""
    from dataclasses import replace

    from checker.fix import changed_files, only_changed

    try:
        changed = changed_files(lesson_dir, since)
    except ValueError as exc:
        err.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from exc
    if changed is None:
        err.print("[red]--changed needs the lesson to be a git repo[/]")
        raise typer.Exit(2)
    kept = only_changed(results.findings, changed)
    scope = f"changed since {since} or uncommitted" if since else "uncommitted changes"
    err.print(f"[dim]showing {len(kept)} of {len(results.findings)} finding(s): files with {scope} "
              f"({len(changed)} file(s))[/]")
    return replace(results, findings=kept)


AI_BACKENDS = ("ollama", "claude")  # mirrors checker.ai_review.BACKENDS, kept here so importing
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")  # the CLI never loads the AI stack


@app.command()
def review(
    target: Annotated[str, typer.Argument(help="Lesson directory, or a git URL to clone and review.")] = ".",
    episode: Annotated[str | None, typer.Option(help="Only review this episode file (by filename).")] = None,
    backend: Annotated[str, typer.Option(help=f"One of: {', '.join(AI_BACKENDS)}.")] = "ollama",
    model: Annotated[str | None, typer.Option(help="Override the backend's default model.")] = None,
    effort: Annotated[
        str, typer.Option(help=f"Claude effort: {', '.join(EFFORT_LEVELS)}. Ignored by ollama.")
    ] = "high",
    results_path: Annotated[
        Path | None, typer.Option("--results", help="Results file to add to (default: <lesson>/.wbcheck/results.json).")
    ] = None,
) -> None:
    """Add AI review findings (source "ai", codes AI2xx) to the results.

    Each finding quotes the episode verbatim; findings whose quote isn't in the
    episode are dropped. Re-reviewing an episode replaces its earlier AI
    findings. Uses saved results when present, otherwise runs `check` first.
    Costs time and, for claude, API usage.
    """
    if backend not in AI_BACKENDS:
        err.print(f"[red]unknown backend[/] `{backend}`, expected one of {', '.join(AI_BACKENDS)}")
        raise typer.Exit(2)
    if effort not in EFFORT_LEVELS:
        err.print(f"[red]unknown effort[/] `{effort}`, expected one of {', '.join(EFFORT_LEVELS)}")
        raise typer.Exit(2)
    from checker.ai_review import review_episode

    # Always refresh first (under a second): the review then works from
    # mechanical findings and file hashes that match the text it reads.
    results, lesson_dir, tmp, path = _refresh(target, None, False, results_path)
    try:
        episode_files = sorted(p for p in (lesson_dir / "episodes").glob("*") if p.suffix in (".md", ".Rmd"))
        if episode:
            episode_files = [p for p in episode_files if p.name == episode]
            if not episode_files:
                err.print(f"[red]no episode named[/] `{episode}` under episodes/")
                raise typer.Exit(2)
        glossary_text = _read_glossary(lesson_dir)

        reviewed: dict[str, list[Finding]] = {}
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
            console=err,
            transient=True,
        ) as progress:
            task = progress.add_task("AI review", total=len(episode_files))
            for p in episode_files:
                progress.update(task, description=f"AI review ({backend}): {p.name}")
                location = str(p.relative_to(lesson_dir))
                label = f"{p.name} ({backend})"
                mechanical = [f for f in results.findings if f.location == location and f.source != "ai"]
                try:
                    result = review_episode(
                        p.read_text(errors="replace"),
                        location,
                        mechanical,
                        backend,
                        model=model,
                        glossary_text=glossary_text,
                        effort=effort,
                    )
                except Exception as exc:  # noqa: BLE001 -- backend errors are unpredictable
                    err.print(f"[red]AI review failed for {p.name}:[/] {exc}")
                    results.ai_reviews[label] = f"(AI review failed: {exc})"
                else:
                    results.ai_reviews[label] = result.as_text()
                    reviewed[location] = result.findings
                    if result.dropped:
                        err.print(f"[yellow]{p.name}:[/] dropped {result.dropped} finding(s) with unverifiable quotes")
                progress.advance(task)

        # A successful re-review replaces that episode's earlier AI findings
        # (fresh, not stale); a failed one leaves them in place.
        from checker.refresh import merge_ai_review

        results = merge_ai_review(results, reviewed, lesson_dir, path)
        new_findings = [f for f in results.findings if f.source == "ai" and f.location in reviewed]

        console = Console()
        ai_only = Results(
            target=results.target,
            lesson_dir=results.lesson_dir,
            findings=[f for f in results.findings if f.source == "ai" and f.location in reviewed],
        )
        if ai_only.findings:
            render_findings(console, ai_only, show_source=False)
        render_ai_reviews(console, {k: v for k, v in results.ai_reviews.items() if k.endswith(f"({backend})")})
        err.print(f"[dim]{len(new_findings)} AI finding(s) · saved {path}[/]")
        failed = len(episode_files) - len(reviewed)
        if failed:
            # successes are saved above; still say the requested review is incomplete
            err.print(f"[red]{failed} of {len(episode_files)} episode review(s) failed[/]")
            raise typer.Exit(1)
    finally:
        if tmp is not None:
            tmp.cleanup()


def _quarto_render(kind: str, render, md_text: str, out: Path, title: str) -> Path | None:
    try:
        rendered = render(md_text, out, report_title=title)
    except RuntimeError as exc:
        err.print(f"[red]quarto render failed, skipping {kind}:[/] {exc}")
        return None
    if rendered is None:
        err.print(f"[yellow]quarto not found on PATH[/], skipping {kind} (install from https://quarto.org)")
        return None
    err.print(f"[dim]wrote {rendered}[/]")
    return rendered


@app.command()
def report(
    lesson: Annotated[Path, typer.Argument(help="Lesson directory whose saved results to render.")] = Path("."),
    results_path: Annotated[
        Path | None, typer.Option("--results", help="Results file (default: <lesson>/.wbcheck/results.json).")
    ] = None,
    md: Annotated[Path | None, typer.Option("--md", help="Write a markdown report here.")] = None,
    html: Annotated[Path | None, typer.Option("--html", help="Render an HTML report here (needs Quarto).")] = None,
    pdf: Annotated[Path | None, typer.Option("--pdf", help="Render a PDF report here (needs Quarto + LaTeX).")] = None,
    json_out: Annotated[Path | None, typer.Option("--json", help="Copy the results JSON here.")] = None,
    open_html: Annotated[bool, typer.Option("--open", help="Open the HTML report in a browser.")] = False,
    show_source: Annotated[bool, typer.Option("--source", help="Show the source line under each finding.")] = False,
) -> None:
    """Render saved results. With no output options, prints to the terminal."""
    path = results_path or default_results_path(lesson)
    if not path.exists():
        err.print(f"[red]no results at[/] {path}. Run [bold]wbcheck check {lesson}[/] first.")
        raise typer.Exit(2)
    try:
        results = load(path)
    except ValueError as exc:
        err.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from exc

    wrote_file = any(x is not None for x in (md, html, pdf, json_out))
    if not wrote_file:
        render_results(Console(), results, show_source=show_source)
        return

    md_text = render_markdown(
        results.findings,
        results.title,
        blame=results.blame,
        github_base=results.github_base,
        metadata=results.metadata,
        ai_reviews=results.ai_reviews or None,
        dirty_files=frozenset(results.dirty_files),
    )
    qmd_title = (
        f"{results.metadata.title} — Lesson Check Report"
        if results.metadata and results.metadata.title
        else results.title
    )
    if md is not None:
        md.write_text(md_text)
        err.print(f"[dim]wrote {md}[/]")
    if json_out is not None:
        json_out.write_text(results.to_json())
        err.print(f"[dim]wrote {json_out}[/]")
    rendered_html = None
    if html is not None:
        rendered_html = _quarto_render("HTML", render_html_via_quarto, md_text, html, qmd_title)
    if pdf is not None:
        _quarto_render("PDF", render_pdf_via_quarto, md_text, pdf, qmd_title)
    if open_html:
        if rendered_html is not None:
            webbrowser.open(rendered_html.resolve().as_uri())
        else:
            err.print("[yellow]--open:[/] no HTML report was rendered, nothing to open")


@app.command()
def issues(
    lesson: Annotated[Path, typer.Argument(help="Lesson directory whose saved results to file.")] = Path("."),
    results_path: Annotated[
        Path | None, typer.Option("--results", help="Results file (default: <lesson>/.wbcheck/results.json).")
    ] = None,
    repo: Annotated[
        str | None, typer.Option(help="owner/name to file in (default: the lesson's GitHub origin).")
    ] = None,
    group_by: Annotated[
        str,
        typer.Option(
            help="auto: one issue per rule when it appears in 3+ files, else per file; "
            "file: one issue per file; rule: one per code. AI findings group by file + scope."
        ),
    ] = "auto",
    min_severity: Annotated[str, typer.Option(help="Lowest severity to include: error, warning, or info.")] = "warning",
    source: Annotated[str, typer.Option(help="Which findings: all, mechanical, or ai.")] = "all",
    preview: Annotated[bool, typer.Option("--preview", help="Print each issue body, not just the titles.")] = False,
    create: Annotated[bool, typer.Option("--create", help="Actually file the issues with gh.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the confirmation prompt with --create.")] = False,
) -> None:
    """Group saved findings into pull-request-sized GitHub issues.

    Dry run by default: shows what would be filed. Findings already in an
    issue labelled `wbcheck` (open or closed) are skipped, so re-running is safe.
    """
    from rich.markdown import Markdown
    from rich.table import Table

    from checker.issues import GhError, create_issue, ensure_labels, filed_ids, plan_issues, repo_from_results

    if group_by not in ("auto", "file", "rule"):
        err.print(f"[red]--group-by must be auto, file, or rule[/], got `{group_by}`")
        raise typer.Exit(2)
    if min_severity not in ("error", "warning", "info"):
        err.print(f"[red]--min-severity must be error, warning, or info[/], got `{min_severity}`")
        raise typer.Exit(2)
    if source not in ("all", "mechanical", "ai"):
        err.print(f"[red]--source must be all, mechanical, or ai[/], got `{source}`")
        raise typer.Exit(2)

    path = results_path or default_results_path(lesson)
    if not path.exists():
        err.print(f"[red]no results at[/] {path}. Run [bold]wbcheck check {lesson}[/] first.")
        raise typer.Exit(2)
    try:
        results = load(path)
    except ValueError as exc:
        err.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from exc

    target_repo = repo or repo_from_results(results)
    already: set[str] = set()
    if target_repo:
        try:
            with err.status(f"Checking {target_repo} for already-filed findings…"):
                already = filed_ids(target_repo)
        except GhError as exc:
            if create:
                err.print(f"[red]can't read existing issues in {target_repo}:[/] {exc}")
                raise typer.Exit(1) from exc
            err.print(f"[yellow]couldn't check {target_repo} for already-filed findings:[/] {exc}")
    elif create:
        err.print("[red]no GitHub repo[/]: the lesson has no github.com origin; pass --repo owner/name")
        raise typer.Exit(2)

    drafts, skipped = plan_issues(results, group_by, min_severity, source, already)
    console = Console()
    where = target_repo or "(no repo)"
    if not drafts:
        note = f" ({skipped} finding(s) already filed)." if skipped else "."
        console.print(f"Nothing new to file in {where}{note}")
        return

    table = Table(title=f"{len(drafts)} issue(s) for {where}", title_justify="left", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Title")
    table.add_column("Items", justify="right")
    table.add_column("Labels", style="dim")
    for i, d in enumerate(drafts, 1):
        table.add_row(str(i), d.title, str(len(d.findings)), ", ".join(d.labels))
    console.print(table)
    if skipped:
        console.print(f"[dim]{skipped} finding(s) skipped, already in a wbcheck issue.[/]")
    stale = sum(1 for f in results.findings if f.stale)
    if stale:
        console.print(f"[dim]{stale} stale AI finding(s) left out; re-run `wbcheck review` to refresh them.[/]")
    dirty = sorted({f.location for d in drafts for f in d.findings if f.location in set(results.dirty_files)})
    if dirty:
        err.print(
            f"[yellow]{len(dirty)} file(s) had uncommitted changes at check time[/] "
            f"({', '.join(dirty)}); their items won't link to GitHub. Commit, push, and re-run "
            "`wbcheck check` first if you want links."
        )
    if preview:
        for i, d in enumerate(drafts, 1):
            console.rule(f"[bold]{i}. {d.title}", align="left")
            console.print(Markdown(d.body))

    if not create:
        err.print("[dim]dry run: nothing filed. Add --preview to read the bodies, --create to file them.[/]")
        return
    if not yes and not typer.confirm(f"File {len(drafts)} issue(s) in {target_repo}?", default=False):
        err.print("not filed")
        raise typer.Exit(1)
    assert target_repo is not None
    try:
        with err.status(f"Filing {len(drafts)} issue(s) in {target_repo}…") as status:
            ensure_labels(target_repo, {label for d in drafts for label in d.labels})
            for n, d in enumerate(drafts, 1):
                status.update(f"Filing {n}/{len(drafts)}: {d.title}")
                url = create_issue(target_repo, d)
                console.print(f"[green]filed[/] {url}  {d.title}")
    except GhError as exc:
        err.print(f"[red]gh failed:[/] {exc}")
        raise typer.Exit(1) from exc


@app.command()
def tui(
    lesson: Annotated[Path, typer.Argument(help="Lesson directory whose saved results to browse.")] = Path("."),
    results_path: Annotated[
        Path | None, typer.Option("--results", help="Results file (default: <lesson>/.wbcheck/results.json).")
    ] = None,
) -> None:
    """Browse and triage saved findings: filter, select, ignore, open in $EDITOR, file issues.

    Runs `check` first if there are no saved results for the lesson.
    """
    from checker.tui import run

    path = results_path or default_results_path(lesson)
    if not path.exists():
        if results_path is not None:
            err.print(f"[red]no results at[/] {path}")
            raise typer.Exit(2)
        err.print("[dim]no saved results, running checks first[/]")
        _, _, tmp, path = _refresh(str(lesson), None, False, None)
        if tmp is not None:
            tmp.cleanup()
    try:
        results = load(path)
    except ValueError as exc:
        err.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from exc
    run(results, path)


@app.command()
def fix(
    lesson: Annotated[Path, typer.Argument(help="Lesson directory to work through.")] = Path("."),
    code: Annotated[list[str] | None, typer.Option(help="Only these rule codes (repeatable).")] = None,
    file: Annotated[str | None, typer.Option(help="Only files matching this glob, e.g. 'episodes/0*'.")] = None,
    min_severity: Annotated[str, typer.Option(help="Lowest severity to include: error, warning, info.")] = "warning",
    source: Annotated[str, typer.Option(help="Which findings: all, mechanical, or ai.")] = "all",
    changed: Annotated[bool, typer.Option("--changed", help="Only files with uncommitted changes.")] = False,
    since: Annotated[
        str | None, typer.Option(help="Also files changed since this git ref (implies --changed).")
    ] = None,
    step: Annotated[bool, typer.Option("--step", help="One finding at a time, even in vim/nvim.")] = False,
    print_only: Annotated[
        bool, typer.Option("--print", help="Just print quickfix lines (path:line:col: msg), e.g. for `nvim -q`.")
    ] = False,
    apply: Annotated[
        bool, typer.Option("--apply", help="Offer the safe fixes (WB103, WB213), each as a diff.")
    ] = False,
    suggest: Annotated[
        bool,
        typer.Option("--suggest", help="Offer editorial suggestions (WB401 rewrites, WB009 episode list), "
                     "each confirmed individually."),
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="With --apply, apply the safe fixes without asking (never suggestions).")
    ] = False,
) -> None:
    """Work through findings in your editor, or apply the safe automatic fixes.

    Re-checks the lesson first. In vim/nvim ($VISUAL/$EDITOR), findings load
    into the quickfix list: `]q`/`:cnext` to move, `:copen` to see them all.
    Other editors open one finding at a time at its line. Either way, the
    lesson is re-checked afterwards and fixed findings are reported.

    --apply offers the safe fixes, where the edit is unambiguous and changes no
    meaning: the `exercise:` front-matter typo (WB103) and skipped heading
    levels (WB213). --suggest offers editorial ones, each confirmed on its own
    even with --yes: the objective rewrite (WB401) and adding an unlisted
    episode to config.yaml (WB009), which may be a draft left out on purpose.
    """
    import fnmatch
    import os

    from checker.fix import apply_fix, changed_files, plan_autofixes, quickfix_lines, uses_quickfix
    from checker.tui import editor_command

    if min_severity not in ("error", "warning", "info") or source not in ("all", "mechanical", "ai"):
        err.print("[red]--min-severity must be error/warning/info and --source all/mechanical/ai[/]")
        raise typer.Exit(2)
    lesson_dir = lesson.expanduser().resolve()
    if not (lesson_dir / "episodes").is_dir():
        err.print(f"[red]{lesson_dir} doesn't look like a lesson[/] (no episodes/)")
        raise typer.Exit(2)

    results, _, _, path = _refresh(str(lesson_dir), None, False, None)

    threshold = SEVERITY_ORDER[min_severity]
    todo = [
        f for f in results.findings
        if f.location
        and SEVERITY_ORDER.get(f.severity, 9) <= threshold
        and (source == "all" or f.source == source)
        and (not code or (f.code or f.category) in code)
        and (not file or fnmatch.fnmatch(f.location, file))
    ]
    if changed or since:
        try:
            changed_set = changed_files(lesson_dir, since)
        except ValueError as exc:
            err.print(f"[red]{exc}[/]")
            raise typer.Exit(2) from exc
        if changed_set is None:
            err.print("[red]--changed needs the lesson to be a git repo[/]")
            raise typer.Exit(2)
        todo = [f for f in todo if f.location in changed_set]
    todo.sort(key=lambda f: (f.location or "", f.line or 0))

    if print_only:
        for line in quickfix_lines(todo, lesson_dir):
            print(line)
        return
    if not todo:
        err.print("[green]Nothing to fix[/] with these filters.")
        return
    console = Console()

    if apply or suggest:
        from checker.fix import SAFE_FIX_CODES, SUGGESTION_CODES

        codes = (SAFE_FIX_CODES if apply else ()) + (SUGGESTION_CODES if suggest else ())
        fixes = plan_autofixes(todo, lesson_dir, codes)
        if not fixes:
            which = " or ".join(f for f, on in (("safe fix", apply), ("suggestion", suggest)) if on)
            err.print(f"None of the {len(todo)} finding(s) has a {which}; try `wbcheck fix` without flags.")
            return
        if yes and suggest:
            err.print("[dim]--yes applies safe fixes only; each suggestion still asks.[/]")
        from rich.syntax import Syntax

        applied = 0
        for n, fx in enumerate(fixes, 1):
            is_suggestion = fx.finding.code in SUGGESTION_CODES
            label = "suggestion" if is_suggestion else "fix"
            console.rule(f"[bold]{n}/{len(fixes)}  {fx.finding.code} {label}[/]  {fx.description}", align="left")
            try:
                console.print(Syntax(fx.diff(lesson_dir), "diff", theme="ansi_dark"))
            except ValueError as exc:
                err.print(f"[yellow]skipped:[/] {exc}")
                continue
            if is_suggestion:
                answer = typer.prompt("Apply this suggestion? [y]es / [n]o / [q]uit", default="n").strip().lower()[:1]
                if answer == "q":
                    break
                if answer != "y":
                    continue
            elif not yes:
                answer = typer.prompt("Apply? [y]es / [n]o / [a]ll safe fixes / [q]uit",
                                      default="y").strip().lower()[:1]
                if answer == "q":
                    break
                if answer == "a":
                    yes = True
                elif answer != "y":
                    continue
            try:
                apply_fix(fx)
                applied += 1
            except ValueError as exc:
                err.print(f"[yellow]skipped:[/] {exc}")
        err.print(f"[green]Applied {applied} fix(es).[/] Re-checking…")
        _report_progress(lesson_dir, {f.id for f in todo})
        return

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    before = {f.id for f in todo}
    if uses_quickfix(editor) and not step:
        qf = path.parent / "quickfix.txt"
        qf.write_text("\n".join(quickfix_lines(todo, lesson_dir)) + "\n")
        err.print(f"[dim]{len(todo)} finding(s) in the quickfix list: ]q or :cnext to move, :copen to list them[/]")
        subprocess.run([*editor.split(), "-q", str(qf)], check=False)
        _report_progress(lesson_dir, before)
        return

    for n, f in enumerate(todo, 1):
        console.rule(f"[bold]{n}/{len(todo)}[/]  {f.location}:{f.line or ''}", align="left")
        console.print(Text.assemble((f"{f.code or f.category}  ", "bold"), f.message))
        if f.quote:
            console.print(Text(f"“{f.quote}”", style="italic"))
        if f.hint:
            console.print(Text(f"Fix: {f.hint}", style="dim"))
        answer = typer.prompt("[enter] open  [s]kip  [q]uit", default="", show_default=False).strip().lower()[:1]
        if answer == "q":
            break
        if answer == "s":
            continue
        subprocess.run(editor_command(editor, lesson_dir / f.location, f.line), check=False)
        still = {x.id for x in run_checks(lesson_dir)}
        if f.source == "ai":
            console.print("[dim]AI finding: re-run `wbcheck review` to re-check it[/]")
        elif f.id in still:
            console.print("[yellow]✗ still reported[/]")
        else:
            console.print("[green]✔ fixed[/]")
    _report_progress(lesson_dir, before)


def _report_progress(lesson_dir: Path, before: set[str]) -> None:
    """Refresh (AI findings in edited files turn stale), and say how many of
    `before` are gone."""
    results, _, _, _ = _refresh(str(lesson_dir), None, False, None)
    now = {f.id for f in results.findings}
    gone = len(before - now)
    left = len(before & now)
    err.print(f"[green]{gone} fixed[/], {left} still reported, {len(results.findings)} finding(s) in the lesson now.")


INSTALL_ROOT = Path(__file__).resolve().parent.parent  # the checkout pixi installed from


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)


@app.command()
def update() -> None:
    """Update wbcheck: git pull its checkout, then refresh the pixi environment.

    For installs made with install.sh (a git checkout in ~/.local/share/wbcheck
    by default). Refuses if the checkout has uncommitted changes.
    """
    root = INSTALL_ROOT
    if not (root / ".git").exists() or not (root / "pixi.toml").exists():
        err.print(f"[red]{root} is not a git checkout with pixi.toml[/]; reinstall with install.sh")
        raise typer.Exit(2)
    if _git(["status", "--porcelain", "--untracked-files=no"], root).stdout.strip():
        err.print(f"[red]{root} has uncommitted changes[/]; commit or stash them, then re-run")
        raise typer.Exit(1)
    before = _git(["rev-parse", "--short", "HEAD"], root).stdout.strip()
    with err.status("Pulling the latest wbcheck…"):
        pulled = _git(["pull", "--ff-only", "--quiet"], root)
    if pulled.returncode != 0:
        err.print(f"[red]git pull failed:[/] {pulled.stderr.strip()}")
        raise typer.Exit(1)
    after = _git(["rev-parse", "--short", "HEAD"], root).stdout.strip()
    if before == after:
        err.print(f"Already up to date ({after}).")
        return
    with err.status("Refreshing the pixi environment…"):
        installed = subprocess.run(
            ["pixi", "install", "--manifest-path", str(root / "pixi.toml")],
            capture_output=True, text=True, timeout=900,
        )
    if installed.returncode != 0:
        err.print(f"[red]pixi install failed:[/] {installed.stderr.strip()[-500:]}")
        raise typer.Exit(1)
    err.print(f"[green]Updated[/] {before} → {after}. Run [bold]wbcheck --version[/] to confirm.")


def _doctor_rows() -> list[tuple[str, bool | None, str]]:
    """(check, ok, detail) rows; ok None means optional and not set up."""
    import os
    import shutil
    import sys
    import urllib.request

    rows: list[tuple[str, bool | None, str]] = [
        ("wbcheck", True, f"v{__version__} at {INSTALL_ROOT}"),
        ("python", True, sys.version.split()[0]),
    ]
    rows.append(("git", bool(shutil.which("git")), "needed to check git URLs, --blame, links, update"))

    if shutil.which("gh"):
        auth = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        rows.append(("gh (issues)", auth.returncode == 0,
                     "logged in" if auth.returncode == 0 else "run `gh auth login`"))
    else:
        rows.append(("gh (issues)", None, "install from https://cli.github.com to file issues"))

    rows.append(("quarto (--html/--pdf)", True if shutil.which("quarto") else None,
                 "found" if shutil.which("quarto") else "optional: https://quarto.org"))

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    rows.append(("editor (tui o, fix)", True if editor else None,
                 editor or "set $EDITOR (e.g. nvim); falls back to vi"))

    rows.append(("claude backend", True if os.environ.get("ANTHROPIC_API_KEY") else None,
                 "ANTHROPIC_API_KEY set" if os.environ.get("ANTHROPIC_API_KEY")
                 else "optional: set ANTHROPIC_API_KEY for `review --backend claude`"))

    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1) as resp:
            models = [m.get("name", "") for m in json.loads(resp.read()).get("models", [])]
        from checker.ai_review import DEFAULT_MODELS

        wanted = DEFAULT_MODELS["ollama"]
        have = wanted in models
        rows.append(("ollama backend", have,
                     f"server up, {wanted} pulled" if have
                     else f"server up; pull a model: `ollama pull {wanted}`"))
    except Exception:  # noqa: BLE001 -- any failure means "not running"
        rows.append(("ollama backend", None, "optional: `ollama serve` for local AI review"))
    return rows


@app.command()
def doctor() -> None:
    """Check what's installed and which optional features are ready."""
    from rich.table import Table

    table = Table(show_header=False, box=None, padding=(0, 1))
    for name, ok, detail in _doctor_rows():
        mark = "[green]✔[/]" if ok else ("[red]✖[/]" if ok is False else "[dim]–[/]")
        table.add_row(mark, name, Text(detail, style="dim"))
    Console().print(table)


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    sys.exit(main())
