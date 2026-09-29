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

import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from checker import __version__
from checker.cli import _blame_map, _dirty_files, _github_blob_base, _read_glossary, _resolve_target
from checker.console import render_ai_reviews, render_findings, render_results
from checker.lesson_check import read_lesson_metadata, run_checks
from checker.report import (
    Finding,
    assign_occurrences,
    render_html_via_quarto,
    render_markdown,
    render_pdf_via_quarto,
)
from checker.results import Results, default_results_path, load, save

app = typer.Typer(
    name="wbcheck",
    help="Fast local checks for Carpentries Workbench lessons, with an optional AI review.",
    no_args_is_help=True,
    add_completion=False,
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


def _results_path_for(lesson_dir: Path, is_clone: bool, override: Path | None) -> Path:
    """Explicit --results wins; a temporary clone saves under the current
    directory (the clone is deleted after the run); otherwise inside the
    lesson."""
    if override is not None:
        return override
    return default_results_path(Path.cwd() if is_clone else lesson_dir)


def _run_check(
    target: str, episode: str | None, blame: bool
) -> tuple[Results, Path, tempfile.TemporaryDirectory | None]:
    """Run the mechanical checks. Returns the results, the lesson directory,
    and the temp-clone handle (None for a local path) for the caller to
    clean up."""
    lesson_dir, tmp = _resolve_target(target)
    findings = run_checks(lesson_dir, episode_filter=episode)
    github_base = _github_blob_base(lesson_dir)
    results = Results(
        target=target,
        lesson_dir=None if tmp is not None else str(lesson_dir),
        findings=findings,
        metadata=read_lesson_metadata(lesson_dir),
        blame=_blame_map(lesson_dir, findings) if blame else None,
        github_base=github_base,
        dirty_files=sorted(_dirty_files(lesson_dir)) if github_base else [],
    )
    if blame and not results.blame:
        err.print("[yellow]--blame found no authors[/] (is the lesson a git repo with history?)")
    return results, lesson_dir, tmp


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
) -> None:
    """Run the fast mechanical checks and save the results. Exits 1 if any error was found."""
    results, lesson_dir, tmp = _run_check(target, episode, blame)
    try:
        path = save(results, _results_path_for(lesson_dir, tmp is not None, results_path))
        if not quiet:
            render_results(Console(), results, show_source=show_source)
        err.print(f"[dim]saved {path}[/]")
    finally:
        if tmp is not None:
            tmp.cleanup()
    raise typer.Exit(1 if results.error_count else 0)


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

    lesson_dir, tmp = _resolve_target(target)
    try:
        path = _results_path_for(lesson_dir, tmp is not None, results_path)
        if path.exists():
            results = load(path)
        else:
            err.print("[dim]no saved results, running checks first[/]")
            if tmp is not None:
                tmp.cleanup()
            results, lesson_dir, tmp = _run_check(target, episode, blame=False)

        episode_files = sorted(p for p in (lesson_dir / "episodes").glob("*") if p.suffix in (".md", ".Rmd"))
        if episode:
            episode_files = [p for p in episode_files if p.name == episode]
        glossary_text = _read_glossary(lesson_dir)

        new_findings: list[Finding] = []
        reviewed: set[str] = set()
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
                    new_findings.extend(result.findings)
                    reviewed.add(location)
                    if result.dropped:
                        err.print(f"[yellow]{p.name}:[/] dropped {result.dropped} finding(s) with unverifiable quotes")
                progress.advance(task)

        # A successful re-review supersedes that episode's earlier AI findings;
        # a failed one leaves them in place.
        results.findings = [
            f for f in results.findings if not (f.source == "ai" and f.location in reviewed)
        ] + new_findings
        assign_occurrences(results.findings)
        save(results, path)

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
        str, typer.Option(help="file: one issue per file (AI: per file + scope); rule: one per code.")
    ] = "file",
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

    if group_by not in ("file", "rule"):
        err.print(f"[red]--group-by must be file or rule[/], got `{group_by}`")
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
    results = load(path)

    target_repo = repo or repo_from_results(results)
    already: set[str] = set()
    if target_repo:
        try:
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
        ensure_labels(target_repo, {label for d in drafts for label in d.labels})
        for d in drafts:
            url = create_issue(target_repo, d)
            console.print(f"[green]filed[/] {url}  {d.title}")
    except GhError as exc:
        err.print(f"[red]gh failed:[/] {exc}")
        raise typer.Exit(1) from exc


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    sys.exit(main())
