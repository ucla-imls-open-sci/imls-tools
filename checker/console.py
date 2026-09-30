"""Rich terminal rendering for `wbcheck`: findings grouped by file, with the
rule code as a clickable link to its guide section (in terminals that
support OSC 8 hyperlinks), and optional source excerpts at each finding's
line.

All finding/hint text goes through `Text` objects rather than console
markup, since hints routinely contain literal brackets (`[CLDT]`,
`[Carpentries Lab]`) that Rich would otherwise parse as style tags.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.rule import Rule as RichRule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from checker import __version__
from checker.report import Finding, _lesson_metadata_lines, summarize
from checker.results import Results

SEVERITY_STYLE = {"error": "bold red", "warning": "yellow", "info": "blue"}
SEVERITY_ICON = {"error": "✖", "warning": "▲", "info": "●"}


def _code_text(f: Finding) -> Text:
    label = f.code or f.category
    guides = f.guides
    style = f"bold link {guides[0][1]}" if guides else "bold"
    return Text(label, style=style)


def _source_excerpt(lesson_dir: Path | None, f: Finding, context: int = 1) -> Syntax | None:
    """The finding's line with `context` lines around it, or None when the
    lesson isn't on disk (a checked temp clone) or the finding has no line."""
    if lesson_dir is None or f.location is None or f.line is None:
        return None
    path = lesson_dir / f.location
    if not path.is_file():
        return None
    lines = path.read_text(errors="replace").splitlines()
    if not 1 <= f.line <= len(lines):
        return None
    start = max(1, f.line - context)
    end = min(len(lines), f.line + context)
    snippet = "\n".join(lines[start - 1 : end])
    return Syntax(
        snippet,
        "markdown",
        line_numbers=True,
        start_line=start,
        highlight_lines={f.line},
        word_wrap=True,
        theme="ansi_dark",
    )


def render_header(console: Console, results: Results) -> None:
    """Title, lesson identity, and severity counts."""
    console.print(Text(results.title, style="bold"))
    for line in _lesson_metadata_lines(results.metadata):
        console.print(Text(line, style="dim"))
    counts = summarize(results.findings)
    summary = Text.assemble(
        (f"wbcheck v{__version__} · ", "dim"),
        (f"{counts['error']} error(s)", SEVERITY_STYLE["error"] if counts["error"] else "dim"),
        (", ", "dim"),
        (f"{counts['warning']} warning(s)", SEVERITY_STYLE["warning"] if counts["warning"] else "dim"),
        (", ", "dim"),
        (f"{counts['info']} note(s)", SEVERITY_STYLE["info"] if counts["info"] else "dim"),
    )
    if results.ignored:
        summary.append(f" · {results.ignored} ignored via .wbcheck.toml", style="dim")
    console.print(summary)


def render_findings(console: Console, results: Results, show_source: bool = False) -> None:
    """Every finding, grouped by file in severity/line order."""
    if not results.findings:
        console.print(Text("✔ No issues found", style="bold green"))
        return
    lesson_dir = Path(results.lesson_dir) if results.lesson_dir else None
    by_location: dict[str, list[Finding]] = {}
    for f in sorted(results.findings, key=Finding.sort_key):
        by_location.setdefault(f.location or "general", []).append(f)

    for location, items in by_location.items():
        heading = Text(location, style="bold")
        author = (results.blame or {}).get(location)
        if author:
            heading.append(f"  last change: {author}", style="dim")
        console.print()
        console.print(RichRule(heading, align="left", style="dim"))
        # A grid keeps wrapped messages/hints indented under the message
        # column instead of wrapping back to the left margin.
        grid = Table.grid(padding=(0, 1))
        grid.add_column(no_wrap=True)  # severity icon
        grid.add_column(no_wrap=True)  # rule code
        grid.add_column(no_wrap=True, justify="right")  # line
        grid.add_column(ratio=1)  # message, hint, source
        for f in sorted(items, key=lambda x: (x.line if x.line is not None else -1, x.severity)):
            style = SEVERITY_STYLE.get(f.severity, "")
            body: list = [Text(f.message)]
            if f.stale:
                body.append(Text("stale: the file changed after this AI review; re-run `wbcheck review`",
                                 style="yellow"))
            if f.quote:
                body.append(Text(f"“{f.quote}”", style="italic"))
            if f.hint:
                body.append(Text(f.hint, style="dim"))
            if show_source:
                excerpt = _source_excerpt(lesson_dir, f)
                if excerpt is not None:
                    body.append(excerpt)
            grid.add_row(
                Text(f" {SEVERITY_ICON.get(f.severity, '?')}", style=style),
                _code_text(f),
                Text(str(f.line) if f.line is not None else "", style="dim"),
                Group(*body),
            )
        console.print(grid)


def render_ai_reviews(console: Console, reviews: dict[str, str]) -> None:
    """AI narrative reviews, rendered as markdown."""
    if not reviews:
        return
    console.print()
    console.print(RichRule(Text("AI review", style="bold"), align="left"))
    for label, text in reviews.items():
        console.print(Group(Text(label, style="bold"), Markdown(text)))
        console.print()


def render_results(console: Console, results: Results, show_source: bool = False) -> None:
    """Header, findings, then AI reviews."""
    render_header(console, results)
    render_findings(console, results, show_source=show_source)
    render_ai_reviews(console, results.ai_reviews)
