"""Tests for the TUI (#28) and the .wbcheck.toml ignore file (#23).

The TUI is driven headlessly with Textual's Pilot inside asyncio.run(), so
no pytest async plugin is needed. gh and the editor are faked.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
import threading
from pathlib import Path

import pytest
from typer.testing import CliRunner

from checker import issues
from checker.app import app
from checker.ignore import IGNORE_FILENAME, IgnoreRules, add_ignored_ids, load_ignore
from checker.issues import draft_for_findings
from checker.report import Finding
from checker.results import Results, default_results_path, load, save
from checker.tui import FindingsApp, editor_command

runner = CliRunner()
BASE = "https://github.com/org/lesson/blob/0123456789abcdef0123456789abcdef01234567"

EPISODE = """---
title: 'Ep'
teaching: 15
exercises: 15
---
:::: questions
- What?
::::

:::: objectives
- Explain it.
::::

## Part

![](fig/missing.png)

## Part

:::: keypoints
- A point.
::::
"""


def make_lesson(tmp_path: Path) -> Path:
    lesson = tmp_path / "lesson"
    (lesson / "episodes").mkdir(parents=True)
    (lesson / "learners").mkdir()
    (lesson / "learners" / "reference.md").write_text("## Glossary\n")
    (lesson / "config.yaml").write_text(
        "title: 'Real'\ncontact: 'a@b.org'\ncreated: 2026-01-01\nsource: 'https://x.org'\n"
        "life_cycle: 'alpha'\nepisodes:\n- 01.md\n"
    )
    (lesson / "episodes" / "01.md").write_text(EPISODE)
    return lesson


def checked_lesson(tmp_path: Path) -> tuple[Path, Path]:
    lesson = make_lesson(tmp_path)
    runner.invoke(app, ["check", str(lesson), "--quiet"])
    path = default_results_path(lesson)
    results = load(path)
    results.github_base = BASE
    ai = Finding("warning", "ai", "Too terse.", location="episodes/01.md", line=14, hint="Expand.",
                 code="AI203", quote="## Part", source="ai", scope="pacing")
    results.findings.append(ai)
    save(results, path)
    return lesson, path


def run_app(path: Path, script):
    """Run `script(app, pilot)` against a headless FindingsApp."""

    async def main():
        tui = FindingsApp(load(path), path)
        async with tui.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            await script(tui, pilot)
            await pilot.pause()
        return tui

    return asyncio.run(main())


# -- ignore file -----------------------------------------------------------------


def test_ignore_rules_match_codes_paths_and_ids():
    f = Finding("warning", "links", "x", location="episodes/all_exercises.md", code="WB301")
    assert IgnoreRules(codes={"WB301"}).matches(f)
    assert IgnoreRules(paths=["episodes/all_*.md"]).matches(f)
    assert IgnoreRules(ids={f.id}).matches(f)
    assert not IgnoreRules(codes={"WB302"}, paths=["learners/*"]).matches(f)


def test_ignore_file_round_trip_and_bad_toml(tmp_path):
    add_ignored_ids(tmp_path, {"aaaaaaaaaaaa"})
    rules = add_ignored_ids(tmp_path, {"bbbbbbbbbbbb"})
    assert rules.ids == {"aaaaaaaaaaaa", "bbbbbbbbbbbb"}
    assert load_ignore(tmp_path).ids == rules.ids
    (tmp_path / IGNORE_FILENAME).write_text("[ignore\n")
    with pytest.raises(ValueError, match="not valid TOML"):
        load_ignore(tmp_path)


def test_check_respects_ignore_file_and_reports_count(tmp_path):
    lesson = make_lesson(tmp_path)
    (lesson / IGNORE_FILENAME).write_text('[ignore]\ncodes = ["WB212", "WB301"]\n')
    result = runner.invoke(app, ["check", str(lesson)])
    codes = {f.code for f in load(default_results_path(lesson)).findings}
    assert "WB212" not in codes and "WB301" not in codes and "WB302" in codes
    assert load(default_results_path(lesson)).ignored == 2
    assert "2 ignored via .wbcheck.toml" in " ".join(result.output.split())


def test_check_with_invalid_ignore_file_exits_two(tmp_path):
    lesson = make_lesson(tmp_path)
    (lesson / IGNORE_FILENAME).write_text("not = [toml")
    assert runner.invoke(app, ["check", str(lesson)]).exit_code == 2


# -- selection drafts --------------------------------------------------------------


def test_draft_for_findings_single_and_multi_file():
    r = Results(target="x", lesson_dir=None, github_base=BASE)
    a = Finding("warning", "links", "a", location="episodes/01.md", line=3, code="WB301")
    b = Finding("error", "links", "b", location="episodes/02.md", line=4, code="WB302")
    assert draft_for_findings(r, [a]).title == "episodes/01.md: 1 warning (WB301)"
    both = draft_for_findings(r, [a, b])
    assert both.title == "1 error, 1 warning across 2 files (WB301, WB302)"
    assert set(both.finding_ids) == {a.id, b.id}
    with pytest.raises(ValueError):
        draft_for_findings(r, [])


# -- editor ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("editor", "expected"),
    [
        ("nvim", ["nvim", "+12", "/l/e.md"]),
        ("code -w", ["code", "-w", "-g", "/l/e.md:12"]),
        ("/usr/local/bin/subl", ["/usr/local/bin/subl", "/l/e.md:12"]),
        ("emacs -nw", ["emacs", "-nw", "+12", "/l/e.md"]),
    ],
)
def test_editor_command(editor, expected):
    assert editor_command(editor, Path("/l/e.md"), 12) == expected


def test_editor_command_without_line():
    assert editor_command("vim", Path("/l/e.md"), None) == ["vim", "/l/e.md"]


# -- the app ---------------------------------------------------------------------


def test_tui_filters_by_severity_source_and_search(tmp_path):
    _, path = checked_lesson(tmp_path)
    seen = {}

    async def script(tui, pilot):
        total = len(tui.results.findings)
        seen["all"] = len(tui.visible) == total
        await pilot.press("a", "a")  # ai only
        seen["ai"] = [f.source for f in tui.visible]
        await pilot.press("escape", "slash", *"points", "enter")  # only WB302 says "points to a missing file"
        seen["search"] = {f.code for f in tui.visible}
        await pilot.press("escape", "s", "s")  # >= error
        seen["errors"] = {f.severity for f in tui.visible}

    run_app(path, script)
    assert seen["all"]
    assert seen["ai"] == ["ai"]
    assert seen["search"] == {"WB302"}
    assert seen["errors"] == {"error"}


def test_tui_tree_filters_to_a_code(tmp_path):
    _, path = checked_lesson(tmp_path)
    seen = {}

    async def script(tui, pilot):
        tree = tui.query_one("#sidebar")
        node = next(n for n in tree.root.children[0].children[0].children if str(n.label).startswith("WB212"))
        tree.select_node(node)
        await pilot.pause()
        seen["codes"] = {f.code for f in tui.visible}

    run_app(path, script)
    assert seen["codes"] == {"WB212"}


def test_tui_ignore_writes_toml_and_saves_results(tmp_path):
    lesson, path = checked_lesson(tmp_path)
    seen = {}

    async def script(tui, pilot):
        await pilot.press("space", "space")  # select the first two rows
        seen["ids"] = set(tui.selected)
        await pilot.press("i")

    run_app(path, script)
    assert len(seen["ids"]) == 2
    assert load_ignore(lesson).ids == seen["ids"]
    saved = load(path)
    assert not seen["ids"] & {f.id for f in saved.findings}
    assert saved.ignored >= 2


def test_tui_rerun_picks_up_edits_and_keeps_ai_findings(tmp_path):
    lesson, path = checked_lesson(tmp_path)
    (lesson / "episodes" / "01.md").write_text(EPISODE.replace("![](fig/missing.png)", "Plain text."))

    async def script(tui, pilot):
        await pilot.press("r")

    run_app(path, script)
    codes = {f.code for f in load(path).findings}
    assert "WB302" not in codes and "WB301" not in codes
    assert "AI203" in codes


def test_tui_open_editor_runs_editor_at_line(tmp_path, monkeypatch):
    lesson, path = checked_lesson(tmp_path)
    calls = []
    monkeypatch.setenv("EDITOR", "nvim")
    monkeypatch.delenv("VISUAL", raising=False)
    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):  # the editor is fake; git (used by the re-check) is real
        if cmd[0] == "git":
            return real_run(cmd, *args, **kwargs)
        calls.append(cmd)

    monkeypatch.setattr("checker.tui.subprocess.run", fake_run)

    async def script(tui, pilot):
        tui.suspend = contextlib.nullcontext  # headless drivers can't suspend
        seen_line = tui.current().line
        await pilot.press("o")
        calls.append(seen_line)

    run_app(path, script)
    cmd, line = calls
    assert cmd[0] == "nvim" and cmd[-1].startswith(str(lesson / "episodes"))
    assert (cmd[1] == f"+{line}") if line else len(cmd) == 2


class FakeGh:
    def __init__(self):
        self.bodies: list[str] = []

    def __call__(self, args, input_text=None):
        if args[:2] == ["issue", "list"]:
            return json.dumps([{"body": b} for b in self.bodies])
        if args[:2] == ["label", "list"]:
            return json.dumps([{"name": "wbcheck"}, {"name": "ai-suggested"}])
        if args[:2] == ["issue", "create"]:
            self.bodies.append(input_text)
            return f"https://github.com/org/lesson/issues/{len(self.bodies)}\n"
        return ""


def test_tui_file_selection_as_one_issue_after_confirm(tmp_path, monkeypatch):
    _, path = checked_lesson(tmp_path)
    gh = FakeGh()
    monkeypatch.setattr(issues, "_gh", gh)
    seen = {}

    async def script(tui, pilot):
        await pilot.press("space", "space", "c")
        await tui.workers.wait_for_complete()
        await pilot.pause()
        seen["modal"] = type(tui.screen).__name__
        await pilot.press("y")
        await pilot.pause()
        seen["busy_while_filing"] = tui._busy or bool(gh.bodies)
        await tui.workers.wait_for_complete()
        await pilot.pause()
        seen["selected_after"] = len(tui.selected)
        seen["busy_after"] = tui._busy

    run_app(path, script)
    assert seen["modal"] == "ConfirmIssues"
    assert len(gh.bodies) == 1
    assert len(issues.ID_MARKER_RE.findall(gh.bodies[0])) == 2
    assert seen["selected_after"] == 0
    assert seen["busy_while_filing"] and not seen["busy_after"]


def test_tui_file_issues_cancel_files_nothing(tmp_path, monkeypatch):
    _, path = checked_lesson(tmp_path)
    gh = FakeGh()
    monkeypatch.setattr(issues, "_gh", gh)

    async def script(tui, pilot):
        await pilot.press("c")
        await tui.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("n")

    run_app(path, script)
    assert gh.bodies == []


def test_tui_command_runs_check_first_when_no_results(tmp_path, monkeypatch):
    lesson = make_lesson(tmp_path)
    launched = {}
    monkeypatch.setattr("checker.tui.run", lambda results, path: launched.update(n=len(results.findings), p=path))
    result = runner.invoke(app, ["tui", str(lesson)])
    assert result.exit_code == 0, result.output
    assert launched["p"] == default_results_path(lesson)
    assert launched["n"] > 0


def test_tui_file_issues_reports_gh_failure(tmp_path, monkeypatch):
    _, path = checked_lesson(tmp_path)

    release = threading.Event()

    def broken(args, input_text=None):
        release.wait(5)  # hold the worker until the test has seen the busy state
        raise issues.GhError("not logged in")

    monkeypatch.setattr(issues, "_gh", broken)
    seen = {}

    async def script(tui, pilot):
        await pilot.press("c")
        seen["busy_during"] = tui._busy and tui.query_one("#table").loading
        release.set()
        await tui.workers.wait_for_complete()
        await pilot.pause()
        seen["busy_after"] = tui._busy
        seen["screen"] = type(tui.screen).__name__

    run_app(path, script)
    assert seen["busy_during"] is True
    assert seen["busy_after"] is False
    assert seen["screen"] != "ConfirmIssues"


def test_tui_file_issues_leaves_notes_out_unless_selected(tmp_path, monkeypatch):
    _, path = checked_lesson(tmp_path)
    results = load(path)
    results.findings.append(Finding("info", "config", "`life_cycle` is still `pre-alpha`",
                                    location="config.yaml", code="WB006"))
    save(results, path)
    gh = FakeGh()
    monkeypatch.setattr(issues, "_gh", gh)
    seen = {}

    async def script(tui, pilot):
        await pilot.press("c")
        await tui.workers.wait_for_complete()
        await pilot.pause()
        modal = tui.screen
        seen["notes_left"] = modal.notes_left
        seen["titles"] = [d.title for d in modal.drafts]
        await pilot.press("n")

    run_app(path, script)
    assert seen["notes_left"] >= 1
    assert not any(t.startswith("config.yaml") for t in seen["titles"])


# -- issue eligibility (#47) ---------------------------------------------------------


def _ai_id(path: Path) -> str:
    return next(f.id for f in load(path).findings if f.source == "ai")


def test_eligible_leaves_out_stale_and_filed():
    a = Finding("warning", "ai", "A", location="episodes/01.md", code="AI203", quote="x", source="ai")
    b = Finding("warning", "ai", "B", location="episodes/01.md", code="AI204", quote="y", source="ai")
    c = Finding("warning", "ai", "C", location="episodes/01.md", code="AI205", quote="z", source="ai", stale=True)
    fresh, skipped, stale = issues.eligible([a, b, c], {a.id})
    assert fresh == [b] and skipped == 1 and stale == 1


def test_tui_never_files_a_selected_stale_finding(tmp_path, monkeypatch):
    lesson, path = checked_lesson(tmp_path)
    ai_id = _ai_id(path)
    gh = FakeGh()
    monkeypatch.setattr(issues, "_gh", gh)
    seen = {}

    async def script(tui, pilot):
        # review -> edit -> re-check: the AI finding goes stale
        (lesson / "episodes" / "01.md").write_text(EPISODE + "\nMore text.\n")
        await pilot.press("r")
        await pilot.pause()
        seen["stale"] = tui._by_id(ai_id).stale
        tui.results.github_base = BASE  # the re-check found no git origin in tmp_path
        tui.selected = {ai_id}
        await pilot.press("c")
        await tui.workers.wait_for_complete()
        await pilot.pause()
        seen["screen"] = type(tui.screen).__name__
        if seen["screen"] == "ConfirmIssues":
            await pilot.press("y")
            await tui.workers.wait_for_complete()

    run_app(path, script)
    assert seen["stale"] is True
    assert seen["screen"] != "ConfirmIssues"
    assert gh.bodies == []


def test_tui_drops_findings_ignored_during_the_gh_lookup(tmp_path, monkeypatch):
    _, path = checked_lesson(tmp_path)
    gh = FakeGh()
    release = threading.Event()

    def slow(args, input_text=None):
        if args[:2] == ["issue", "list"]:
            release.wait(5)
        return gh(args, input_text)

    monkeypatch.setattr(issues, "_gh", slow)
    seen = {}

    async def script(tui, pilot):
        await pilot.press("space", "space")  # two findings selected
        first = sorted(tui.selected)[0]
        await pilot.press("c")
        tui.selected = {first}  # the user ignores `first` while gh is busy
        await pilot.press("i")
        release.set()
        await tui.workers.wait_for_complete()
        await pilot.pause()
        seen["ignored"] = first
        seen["drafted"] = (
            [f.id for d in tui.screen.drafts for f in d.findings]
            if type(tui.screen).__name__ == "ConfirmIssues" else []
        )
        await pilot.press("n")

    run_app(path, script)
    assert seen["ignored"] not in seen["drafted"]


def test_tui_confirm_counts_selected_findings_hidden_by_a_filter(tmp_path, monkeypatch):
    _, path = checked_lesson(tmp_path)
    ai_id = _ai_id(path)
    monkeypatch.setattr(issues, "_gh", FakeGh())
    seen = {}

    async def script(tui, pilot):
        tui.selected = {ai_id}
        await pilot.press("a")  # source filter: all -> mechanical hides the AI finding
        await pilot.pause()
        seen["visible"] = ai_id in {f.id for f in tui.visible}
        await pilot.press("c")
        await tui.workers.wait_for_complete()
        await pilot.pause()
        seen["hidden"] = getattr(tui.screen, "hidden", None)
        await pilot.press("n")

    run_app(path, script)
    assert seen["visible"] is False
    assert seen["hidden"] == 1
