"""`wbcheck tui`: browse and triage saved findings in the terminal (#28).

    ┌ files / codes ─┐┌ findings ─────────────────────────────────┐
    │ All (85)       ││ ● sev  code   file              line  msg │
    │ ▸ episodes/03  ││                                           │
    │   AI202 (3)    │├ detail ───────────────────────────────────┤
    │ ▸ config.yaml  ││ message · quote · fix · guides · source   │
    └────────────────┘└───────────────────────────────────────────┘

Keys: enter on the tree filters to a file or code; space selects findings;
i ignores them (written to .wbcheck.toml); o opens the file at the line in
$EDITOR; c files issues (the selection as one issue, or the visible findings
grouped as `wbcheck issues` would); s / a cycle severity and source filters;
/ searches; r re-runs the mechanical checks; q quits.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from rich.console import Group
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Static, Tree

from checker import issues as issues_mod
from checker.console import SEVERITY_ICON, SEVERITY_STYLE, _source_excerpt
from checker.ignore import add_ignored_ids
from checker.report import SEVERITY_ORDER, Finding
from checker.results import Results, save

SEVERITY_FILTERS = ("info", "warning", "error")  # minimum severity shown
SOURCE_FILTERS = ("all", "mechanical", "ai")


def editor_command(editor: str, path: Path, line: int | None) -> list[str]:
    """argv to open `path` at `line` in `editor` (a $VISUAL/$EDITOR value,
    possibly with arguments)."""
    parts = shlex.split(editor) or ["vi"]
    name = Path(parts[0]).name
    if line is None:
        return [*parts, str(path)]
    if name in ("code", "code-insiders", "cursor", "windsurf", "codium"):
        return [*parts, "-g", f"{path}:{line}"]
    if name in ("subl", "zed", "hx", "helix", "mate"):
        return [*parts, f"{path}:{line}"]
    return [*parts, f"+{line}", str(path)]  # vi/vim/nvim/nano/emacs/micro/kak


class ConfirmIssues(ModalScreen[bool]):
    """Lists the issues about to be filed; y files, n/escape cancels."""

    BINDINGS = [Binding("y", "confirm", "File them"), Binding("n,escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    ConfirmIssues { align: center middle; }
    #confirm { width: 90%; max-width: 110; height: auto; max-height: 80%;
               border: thick $warning; background: $surface; padding: 1 2; }
    """

    SHOW_ITEMS = 8  # per issue; the rest are summarized

    def __init__(
        self, repo: str, drafts: list[issues_mod.IssueDraft], skipped: int, notes_left: int = 0,
        stale: int = 0, hidden: int = 0,
    ) -> None:
        super().__init__()
        self.repo = repo
        self.drafts = drafts
        self.skipped = skipped
        self.notes_left = notes_left
        self.stale = stale
        self.hidden = hidden

    def compose(self) -> ComposeResult:
        lines = Text.assemble((f"File {len(self.drafts)} issue(s) in {self.repo}?\n\n", "bold"))
        for d in self.drafts:
            lines.append(f"• {d.title}  ", style="")
            lines.append(f"[{len(d.findings)} item(s); {', '.join(d.labels)}]\n", style="dim")
            for f in d.findings[: self.SHOW_ITEMS]:
                where = f"{f.location or 'lesson'}{f':{f.line}' if f.line else ''}"
                lines.append(f"    {f.code or f.category} {where}  {' '.join(f.message.split())[:70]}\n", style="dim")
            if len(d.findings) > self.SHOW_ITEMS:
                lines.append(f"    … and {len(d.findings) - self.SHOW_ITEMS} more\n", style="dim")
        if self.hidden:
            lines.append(f"\n{self.hidden} selected finding(s) are hidden by the current filter and included.\n",
                         style="yellow")
        if self.stale:
            lines.append(f"\n{self.stale} stale AI finding(s) left out; re-run `wbcheck review` first.\n",
                         style="dim")
        if self.skipped:
            lines.append(f"\n{self.skipped} finding(s) skipped, already in a wbcheck issue.\n", style="dim")
        if self.notes_left:
            lines.append(f"\n{self.notes_left} note(s) left out; select notes with space to file them.\n",
                         style="dim")
        lines.append("\ny: file them    n: cancel", style="bold")
        yield VerticalScroll(Static(lines), id="confirm")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class FindingsApp(App):
    """Interactive browser over a Results file."""

    TITLE = "wbcheck"
    CSS = """
    #sidebar { width: 36; border-right: solid $primary-darken-2; }
    #main { width: 1fr; }
    #search { display: none; }
    #search.visible { display: block; }
    #table { height: 1fr; }
    #detail { height: 40%; border-top: solid $primary-darken-2; padding: 0 1; }
    """
    BINDINGS = [
        Binding("space", "toggle_select", "Select"),
        Binding("i", "ignore", "Ignore"),
        Binding("o", "open_editor", "Open"),
        Binding("c", "file_issues", "File issues"),
        Binding("s", "cycle_severity", "Severity"),
        Binding("a", "cycle_source", "Source"),
        Binding("slash", "search", "Search"),
        Binding("r", "rerun", "Re-check"),
        Binding("escape", "clear_filters", "Clear filters", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, results: Results, results_path: Path) -> None:
        super().__init__()
        self.results = results
        self.results_path = results_path
        self.lesson_dir = Path(results.lesson_dir) if results.lesson_dir else None
        self.selected: set[str] = set()
        self.file_filter: str | None = None
        self.code_filter: str | None = None
        self.min_severity = "info"
        self.source_filter = "all"
        self.search_text = ""
        self._busy = False

    # -- layout ----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Tree("All findings", id="sidebar")
            with Vertical(id="main"):
                yield Input(placeholder="search message, quote, file, code (esc to clear)", id="search")
                yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
                yield VerticalScroll(Static(id="detail-body"), id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#table", DataTable)
        table.add_column(" ", key="sel", width=1)
        table.add_column("sev", key="sev", width=3)
        table.add_column("code", key="code", width=6)
        table.add_column("file", key="file", width=24)
        table.add_column("line", key="line", width=5)
        table.add_column("message", key="msg")
        self.refresh_all()
        table.focus()

    # -- data ------------------------------------------------------------------

    @property
    def visible(self) -> list[Finding]:
        """Findings passing every active filter, in severity/file/line order."""
        needle = self.search_text.casefold()
        threshold = SEVERITY_ORDER[self.min_severity]
        out = []
        for f in sorted(self.results.findings, key=Finding.sort_key):
            if SEVERITY_ORDER.get(f.severity, 9) > threshold:
                continue
            if self.source_filter != "all" and f.source != self.source_filter:
                continue
            if self.file_filter and f.location != self.file_filter:
                continue
            if self.code_filter and (f.code or f.category) != self.code_filter:
                continue
            if needle:
                hay = " ".join(x or "" for x in (f.message, f.quote, f.location, f.code, f.hint)).casefold()
                if needle not in hay:
                    continue
            out.append(f)
        return out

    def _by_id(self, finding_id: str) -> Finding | None:
        return next((f for f in self.results.findings if f.id == finding_id), None)

    def current(self) -> Finding | None:
        """The finding under the table cursor."""
        table = self.query_one("#table", DataTable)
        if table.row_count == 0:
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return self._by_id(str(row_key.value))

    def targets(self) -> list[Finding]:
        """Selected findings, or the current one if nothing is selected."""
        if self.selected:
            return [f for f in self.results.findings if f.id in self.selected]
        current = self.current()
        return [current] if current else []

    # -- rendering ---------------------------------------------------------------

    def refresh_all(self) -> None:
        """Rebuild tree, table, and detail from current results and filters."""
        self._build_tree()
        self._fill_table()
        self._update_detail()
        filters = [f"≥{self.min_severity}", self.source_filter]
        if self.file_filter:
            filters.append(self.file_filter)
        if self.code_filter:
            filters.append(self.code_filter)
        if self.search_text:
            filters.append(f"/{self.search_text}")
        sel = f" · {len(self.selected)} selected" if self.selected else ""
        self.sub_title = f"{len(self.visible)}/{len(self.results.findings)} shown · {' '.join(filters)}{sel}"

    def _build_tree(self) -> None:
        tree = self.query_one("#sidebar", Tree)
        tree.clear()
        tree.root.set_label(f"All findings ({len(self.results.findings)})")
        tree.root.data = (None, None)
        by_file: dict[str, list[Finding]] = {}
        for f in self.results.findings:
            by_file.setdefault(f.location or "lesson", []).append(f)
        # folder -> file -> code, so long paths like episodes/03-... fit the sidebar
        dirs: dict[str, object] = {}
        for location in sorted(by_file, key=lambda loc: ("/" in loc, loc)):
            items = by_file[location]
            worst = min(items, key=lambda f: SEVERITY_ORDER.get(f.severity, 9)).severity
            style = SEVERITY_STYLE.get(worst, "")
            folder, _, name = location.rpartition("/")
            parent = tree.root
            if folder:
                if folder not in dirs:
                    dirs[folder] = tree.root.add(f"{folder}/", data=(None, None), expand=True)
                parent = dirs[folder]  # type: ignore[assignment]
            node = parent.add(Text(f"{name} ({len(items)})", style=style), data=(location, None))
            codes: dict[str, int] = {}
            for f in items:
                codes[f.code or f.category] = codes.get(f.code or f.category, 0) + 1
            for code in sorted(codes):
                node.add_leaf(f"{code} ({codes[code]})", data=(location, code))
        tree.root.expand()

    def _fill_table(self) -> None:
        table = self.query_one("#table", DataTable)
        keep = self.current()
        table.clear()
        for f in self.visible:
            style = SEVERITY_STYLE.get(f.severity, "")
            table.add_row(
                "●" if f.id in self.selected else "",
                Text(SEVERITY_ICON.get(f.severity, "?"), style=style),
                Text(f.code or f.category, style="bold"),
                Path(f.location).name if f.location else "",
                str(f.line) if f.line is not None else "",
                Text(f"[stale] {f.message}", style="dim") if f.stale else f.message,
                key=f.id,
            )
        if keep is not None and keep.id in {f.id for f in self.visible}:
            table.move_cursor(row=table.get_row_index(keep.id))

    def _update_detail(self) -> None:
        body = self.query_one("#detail-body", Static)
        f = self.current()
        if f is None:
            body.update(Text("No findings match the current filters.", style="dim"))
            return
        parts: list = [
            Text.assemble(
                (f"{SEVERITY_ICON.get(f.severity, '')} {f.code or f.category}  ", SEVERITY_STYLE.get(f.severity, "")),
                (f"{f.location or ''}{':' + str(f.line) if f.line else ''}", "dim"),
                (f"  [{f.source}{' · ' + f.scope if f.scope else ''}]", "dim"),
            ),
            Text(f.message, style="bold"),
        ]
        if f.quote:
            parts.append(Text(f"“{f.quote}”", style="italic"))
        if f.stale:
            parts.append(Text("stale: the file changed after this AI review; re-run `wbcheck review`", style="yellow"))
        if f.hint:
            parts.append(Text(f"Fix: {f.hint}"))
        for label, url in f.guides:
            parts.append(Text(f"Guide: {label}", style=f"link {url} underline"))
        excerpt = _source_excerpt(self.lesson_dir, f, context=2)
        if excerpt is not None:
            parts.append(excerpt)
        parts.append(Text(f"id {f.id}", style="dim"))
        body.update(Group(*parts))

    # -- events ------------------------------------------------------------------

    @on(DataTable.RowHighlighted, "#table")
    def _row_highlighted(self) -> None:
        self._update_detail()

    @on(Tree.NodeSelected, "#sidebar")
    def _node_selected(self, event: Tree.NodeSelected) -> None:
        self.file_filter, self.code_filter = event.node.data or (None, None)
        self.refresh_all()
        self.query_one("#table", DataTable).focus()

    @on(Input.Changed, "#search")
    def _search_changed(self, event: Input.Changed) -> None:
        self.search_text = event.value
        self._fill_table()
        self._update_detail()

    @on(Input.Submitted, "#search")
    def _search_submitted(self) -> None:
        self.refresh_all()
        self.query_one("#table", DataTable).focus()

    # -- actions -----------------------------------------------------------------

    def action_toggle_select(self) -> None:
        f = self.current()
        if f is None:
            return
        self.selected.symmetric_difference_update({f.id})
        table = self.query_one("#table", DataTable)
        table.update_cell(f.id, "sel", "●" if f.id in self.selected else "")
        row = table.cursor_row
        if row < table.row_count - 1:
            table.move_cursor(row=row + 1)
        self.refresh_all()

    def action_cycle_severity(self) -> None:
        self.min_severity = SEVERITY_FILTERS[(SEVERITY_FILTERS.index(self.min_severity) + 1) % 3]
        self.refresh_all()

    def action_cycle_source(self) -> None:
        self.source_filter = SOURCE_FILTERS[(SOURCE_FILTERS.index(self.source_filter) + 1) % 3]
        self.refresh_all()

    def action_search(self) -> None:
        search = self.query_one("#search", Input)
        search.add_class("visible")
        search.focus()

    def action_clear_filters(self) -> None:
        search = self.query_one("#search", Input)
        search.value = ""
        search.remove_class("visible")
        self.file_filter = self.code_filter = None
        self.search_text = ""
        self.min_severity, self.source_filter = "info", "all"
        self.refresh_all()
        self.query_one("#table", DataTable).focus()

    def action_ignore(self) -> None:
        if self.lesson_dir is None:
            self.notify("Checked from a temporary clone, no lesson directory to write .wbcheck.toml to.",
                        severity="error")
            return
        targets = self.targets()
        if not targets:
            return
        ids = {f.id for f in targets}
        add_ignored_ids(self.lesson_dir, ids)
        self.results.findings = [f for f in self.results.findings if f.id not in ids]
        self.results.ignored += len(ids)
        self.selected -= ids
        save(self.results, self.results_path)
        self.refresh_all()
        self.notify(f"Ignored {len(ids)} finding(s) in .wbcheck.toml")

    def action_open_editor(self) -> None:
        f = self.current()
        if f is None or not f.location or self.lesson_dir is None:
            self.notify("No file on disk for this finding.", severity="warning")
            return
        path = self.lesson_dir / f.location
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
        with self.suspend():
            subprocess.run(editor_command(editor, path, f.line), check=False)
        # Back from the editor: re-check so a fixed finding drops off the list.
        if not self._recheck():
            return
        if f.source == "ai":
            self.notify("Re-checked. AI findings need `wbcheck review` to re-check.")
        elif self._by_id(f.id) is None:
            self.notify(f"✔ fixed: {f.code or f.category} {f.location}", timeout=4)
        else:
            self.notify(f"✗ still reported: {f.code or f.category}", severity="warning", timeout=4)

    def action_rerun(self) -> None:
        if self._recheck():
            mechanical = sum(1 for f in self.results.findings if f.source != "ai")
            self.notify(f"Re-checked: {mechanical} mechanical finding(s)")

    def _recheck(self) -> bool:
        """Re-run the mechanical checks, keep AI findings, save, and redraw.
        False (with a notification) if that isn't possible."""
        if self.lesson_dir is None:
            self.notify("Checked from a temporary clone, can't re-run here.", severity="error")
            return False
        from checker.refresh import refresh

        # the shared refresh: fresh mechanical findings and git context, AI
        # findings kept (and marked stale if their file changed), IDs stable
        try:
            self.results, notes = refresh(self.results.target, self.lesson_dir, False, self.results_path)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return False
        if notes.stale:
            self.notify(f"{notes.stale} AI finding(s) are stale: their file changed since the review",
                        severity="warning")
        self.selected &= {f.id for f in self.results.findings}
        self.refresh_all()
        return True

    def action_file_issues(self) -> None:
        repo = issues_mod.repo_from_results(self.results)
        if repo is None:
            self.notify("The lesson has no GitHub origin; use `wbcheck issues --repo` instead.", severity="error")
            return
        if self._busy:
            self.notify("Still talking to GitHub, one moment.", severity="warning")
            return
        selection = [f.id for f in self.targets()] if self.selected else None
        self._set_busy(f"Checking {repo} for already-filed findings…")
        self._plan_issues(repo, selection)

    # gh calls block for a second or more each, so they run in a worker thread
    # and report back through call_from_thread; the table shows a loading
    # indicator and the subtitle says what's happening meanwhile.

    def _set_busy(self, message: str | None) -> None:
        self._busy = message is not None
        self.query_one("#table", DataTable).loading = self._busy
        if message:
            self.sub_title = message
        else:
            self.refresh_all()

    def _gh_failed(self, exc: Exception) -> None:
        self._set_busy(None)
        self.notify(f"gh: {exc}", severity="error", timeout=10)

    @work(thread=True, exclusive=True, group="gh")
    def _plan_issues(self, repo: str, selection: list[str] | None) -> None:
        try:
            already = issues_mod.filed_ids(repo)
        except issues_mod.GhError as exc:
            self.call_from_thread(self._gh_failed, exc)
            return
        self.call_from_thread(self._confirm_issues, repo, already, selection)

    def _confirm_issues(self, repo: str, already: set[str], selection: list[str] | None) -> None:
        """Plan against the results as they are now, not as they were when
        `c` was pressed: anything ignored, re-checked away, or unselected
        during the gh lookup drops out."""
        self._set_busy(None)
        visible = self.visible
        notes_left = hidden = 0
        if selection is not None:
            current = {f.id: f for f in self.results.findings}
            picked = [current[i] for i in selection if i in current and i in self.selected]
            fresh, skipped, stale = issues_mod.eligible(picked, already)
            visible_ids = {f.id for f in visible}
            hidden = sum(1 for f in fresh if f.id not in visible_ids)
            drafts = [issues_mod.draft_for_findings(self.results, fresh)] if fresh else []
        else:
            subset = Results(
                target=self.results.target, lesson_dir=self.results.lesson_dir, findings=visible,
                github_base=self.results.github_base, dirty_files=self.results.dirty_files,
                generated=self.results.generated,
            )
            # Notes are informational: never file them unless explicitly selected.
            min_sev = "error" if self.min_severity == "error" else "warning"
            drafts, skipped = issues_mod.plan_issues(subset, min_severity=min_sev, already_filed=already)
            threshold = SEVERITY_ORDER[min_sev]
            stale = sum(1 for f in visible if f.stale and SEVERITY_ORDER.get(f.severity, 9) <= threshold)
            notes_left = sum(1 for f in visible if f.severity == "info")
        if not drafts:
            left = [f"{skipped} already filed"]
            if stale:
                left.append(f"{stale} stale, re-run `wbcheck review`")
            if notes_left:
                left.append(f"{notes_left} note(s) not filed unless selected")
            self.notify(f"Nothing new to file ({'; '.join(left)}).")
            return

        def _answer(confirmed: bool | None) -> None:
            if confirmed:
                self._set_busy(f"Filing {len(drafts)} issue(s) in {repo}…")
                self._create_issues(repo, drafts)

        self.push_screen(ConfirmIssues(repo, drafts, skipped, notes_left, stale=stale, hidden=hidden), _answer)

    @work(thread=True, exclusive=True, group="gh")
    def _create_issues(self, repo: str, drafts: list[issues_mod.IssueDraft]) -> None:
        urls: list[str] = []
        try:
            issues_mod.ensure_labels(repo, {label for d in drafts for label in d.labels})
            for n, draft in enumerate(drafts, 1):
                self.call_from_thread(self._progress, f"Filing {n}/{len(drafts)}: {draft.title}")
                urls.append(issues_mod.create_issue(repo, draft))
        except issues_mod.GhError as exc:
            done = f" after filing {len(urls)}" if urls else ""
            self.call_from_thread(self._gh_failed, RuntimeError(f"{exc}{done}"))
            return
        self.call_from_thread(self._issues_filed, urls)

    def _progress(self, message: str) -> None:
        self.sub_title = message

    def _issues_filed(self, urls: list[str]) -> None:
        self.selected.clear()
        self._set_busy(None)
        self.notify("Filed:\n" + "\n".join(urls), timeout=15)


def run(results: Results, results_path: Path) -> None:
    """Launch the TUI."""
    FindingsApp(results, results_path).run()
