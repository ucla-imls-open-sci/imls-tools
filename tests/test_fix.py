"""Tests for fixing findings locally: `wbcheck fix` (quickfix, step, --apply,
--print), `check --changed`, the safe automatic fixes, and the TUI
re-checking after the editor returns."""

from __future__ import annotations

import asyncio
import contextlib
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from checker.app import app
from checker.fix import apply_fix, changed_files, plan_autofixes, quickfix_lines, uses_quickfix
from checker.lesson_check import run_checks
from checker.results import default_results_path, load

runner = CliRunner()

BODY = """:::: questions
- What?
::::

:::: objectives
- Understand the difference between copy and sync.
::::

## Part one

#### Too deep

:::: keypoints
- Point.
::::
"""


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_lesson(tmp_path: Path, git: bool = False, front: str = "teaching: 15\nexercises: 15") -> Path:
    lesson = tmp_path / "lesson"
    (lesson / "episodes").mkdir(parents=True)
    (lesson / "learners").mkdir()
    (lesson / "learners" / "reference.md").write_text("## Glossary\n")
    (lesson / "config.yaml").write_text(
        "title: 'Real'\ncontact: 'a@b.org'\ncreated: 2026-01-01\nsource: 'https://x.org'\n"
        "life_cycle: 'alpha'\nepisodes:\n- 01.md\n"
    )
    (lesson / "episodes" / "01.md").write_text(f"---\ntitle: 'Ep'\n{front}\n---\n{BODY}")
    if git:
        _git("init", "-q", "-b", "main", cwd=lesson)
        _git("config", "user.email", "t@example.org", cwd=lesson)
        _git("config", "user.name", "T", cwd=lesson)
        _git("add", ".", cwd=lesson)
        _git("commit", "-q", "-m", "init", cwd=lesson)
    return lesson


def codes(lesson: Path) -> list[str]:
    return sorted(f.code for f in run_checks(lesson))


# -- automatic fixes ---------------------------------------------------------------


def test_autofix_heading_jump_and_objective(tmp_path):
    lesson = make_lesson(tmp_path)
    fixes = plan_autofixes(run_checks(lesson), lesson)
    assert {f.finding.code for f in fixes} == {"WB213", "WB401"}
    for fx in fixes:
        assert fx.diff(lesson).startswith("--- a/episodes/01.md")
        apply_fix(fx)
    text = (lesson / "episodes" / "01.md").read_text()
    assert "### Too deep" in text
    assert "- Explain the difference between copy and sync." in text
    assert "WB213" not in codes(lesson) and "WB401" not in codes(lesson)


def test_autofix_exercise_typo(tmp_path):
    lesson = make_lesson(tmp_path, front="teaching: 15\nexercise: 10")
    [fx] = plan_autofixes([f for f in run_checks(lesson) if f.code == "WB103"], lesson)
    apply_fix(fx)
    assert "exercises: 10" in (lesson / "episodes" / "01.md").read_text()
    assert "WB103" not in codes(lesson)


def test_autofix_unlisted_episodes_appended_in_name_order(tmp_path):
    lesson = make_lesson(tmp_path)
    for name in ("03.md", "02.md"):
        (lesson / "episodes" / name).write_text((lesson / "episodes" / "01.md").read_text())
    fixes = plan_autofixes([f for f in run_checks(lesson) if f.code == "WB009"], lesson)
    for fx in fixes:
        apply_fix(fx)
    assert (lesson / "config.yaml").read_text().endswith("episodes:\n- 01.md\n- 02.md\n- 03.md\n")
    assert "WB009" not in codes(lesson)


def test_autofix_skips_unlisted_file_that_looks_misplaced(tmp_path):
    lesson = make_lesson(tmp_path)
    (lesson / "episodes" / "glossary.md").write_text("# Terms\n")
    fixes = plan_autofixes(run_checks(lesson), lesson)
    assert not [f for f in fixes if f.finding.code == "WB009"]


def test_autofix_refuses_a_line_that_changed(tmp_path):
    lesson = make_lesson(tmp_path)
    [fx] = [f for f in plan_autofixes(run_checks(lesson), lesson) if f.finding.code == "WB213"]
    ep = lesson / "episodes" / "01.md"
    ep.write_text(ep.read_text().replace("#### Too deep", "#### Edited meanwhile"))
    with pytest.raises(ValueError, match="changed since the check"):
        apply_fix(fx)


# -- changed files and quickfix ------------------------------------------------------


def test_changed_files_working_tree_and_since(tmp_path):
    lesson = make_lesson(tmp_path, git=True)
    assert changed_files(lesson) == set()
    (lesson / "episodes" / "02.md").write_text("new")
    ep = lesson / "episodes" / "01.md"
    ep.write_text(ep.read_text() + "\nmore\n")
    assert changed_files(lesson) == {"episodes/01.md", "episodes/02.md"}
    _git("checkout", "-q", "-b", "work", cwd=lesson)
    _git("add", ".", cwd=lesson)
    _git("commit", "-q", "-m", "work", cwd=lesson)
    assert changed_files(lesson) == set()
    assert changed_files(lesson, since="main") == {"episodes/01.md", "episodes/02.md"}
    with pytest.raises(ValueError):
        changed_files(lesson, since="no-such-ref")


def test_changed_files_outside_git_is_none(tmp_path):
    assert changed_files(make_lesson(tmp_path)) is None


def test_quickfix_lines_and_editor_detection(tmp_path):
    lesson = make_lesson(tmp_path)
    lines = quickfix_lines(run_checks(lesson), lesson)
    assert any(line.startswith(f"{lesson}/episodes/01.md:16:1: [WB213] ") for line in lines)
    assert uses_quickfix("nvim") and uses_quickfix("/opt/homebrew/bin/vim -p")
    assert not uses_quickfix("code -w") and not uses_quickfix("nano")


# -- CLI -------------------------------------------------------------------------------


def test_check_changed_limits_output_and_exit(tmp_path):
    lesson = make_lesson(tmp_path, git=True)
    result = runner.invoke(app, ["check", str(lesson), "--changed", "--fail-on", "warning"])
    assert result.exit_code == 0  # nothing changed, so nothing counts
    assert "showing 0 of" in result.output
    assert len(load(default_results_path(lesson)).findings) >= 2  # saved results keep everything
    ep = lesson / "episodes" / "01.md"
    ep.write_text(ep.read_text() + "\n")
    result = runner.invoke(app, ["check", str(lesson), "--changed", "--fail-on", "warning"])
    assert result.exit_code == 1 and "WB213" in result.output


def test_check_changed_requires_git(tmp_path):
    assert runner.invoke(app, ["check", str(make_lesson(tmp_path)), "--changed"]).exit_code == 2


def test_fix_print_emits_quickfix_lines(tmp_path):
    lesson = make_lesson(tmp_path)
    result = runner.invoke(app, ["fix", str(lesson), "--print", "--code", "WB213"])
    assert result.exit_code == 0
    assert result.stdout.strip().endswith("[WB213] heading `#### Too deep` on line 16 jumps from level 2 to level 4  "
                                          "Fix: Use level 3 here, or add the missing level-3 heading above it. "
                                          "Skipped levels break screen-reader navigation.")


def _fake_editor(monkeypatch, on_open):
    """Replace the editor (anything not git) with `on_open(cmd)`."""
    real = subprocess.run

    def run(cmd, *args, **kwargs):
        if cmd and Path(cmd[0]).name in ("git",):
            return real(cmd, *args, **kwargs)
        on_open(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("checker.app.subprocess.run", run)


def _fix_heading(lesson):
    ep = lesson / "episodes" / "01.md"
    ep.write_text(ep.read_text().replace("#### Too deep", "### Too deep"))


def test_fix_quickfix_mode_for_nvim(tmp_path, monkeypatch):
    lesson = make_lesson(tmp_path)
    monkeypatch.setenv("EDITOR", "nvim")
    monkeypatch.delenv("VISUAL", raising=False)
    opened = []
    _fake_editor(monkeypatch, lambda cmd: (opened.append(cmd), _fix_heading(lesson)))
    result = runner.invoke(app, ["fix", str(lesson)])
    assert result.exit_code == 0, result.output
    [cmd] = opened
    assert cmd[:2] == ["nvim", "-q"] and cmd[2].endswith(".wbcheck/quickfix.txt")
    assert "1 fixed" in result.output


def test_fix_step_mode_for_other_editors(tmp_path, monkeypatch):
    lesson = make_lesson(tmp_path)
    monkeypatch.setenv("EDITOR", "nano")
    monkeypatch.delenv("VISUAL", raising=False)
    opened = []
    _fake_editor(monkeypatch, lambda cmd: (opened.append(cmd), _fix_heading(lesson)))
    # two findings (WB401 on line 11, WB213 on line 16): skip the first, open the second
    result = runner.invoke(app, ["fix", str(lesson)], input="s\n\n")
    assert result.exit_code == 0, result.output
    assert opened == [["nano", "+16", str(lesson / "episodes" / "01.md")]]
    assert "✔ fixed" in result.output
    assert "1 fixed, 1 still reported" in result.output


def test_fix_apply_yes_applies_all_safe_fixes(tmp_path):
    lesson = make_lesson(tmp_path)
    result = runner.invoke(app, ["fix", str(lesson), "--apply", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Applied 2 fix(es)" in result.output
    assert "2 fixed" in result.output


def test_fix_apply_prompts_and_respects_no(tmp_path):
    lesson = make_lesson(tmp_path)
    before = (lesson / "episodes" / "01.md").read_text()
    result = runner.invoke(app, ["fix", str(lesson), "--apply"], input="n\nn\n")
    assert "Applied 0 fix(es)" in result.output
    assert (lesson / "episodes" / "01.md").read_text() == before


def test_fix_rejects_non_lesson_and_reports_nothing_to_do(tmp_path):
    assert runner.invoke(app, ["fix", str(tmp_path)]).exit_code == 2
    lesson = make_lesson(tmp_path)
    result = runner.invoke(app, ["fix", str(lesson), "--code", "WB999"])
    assert result.exit_code == 0 and "Nothing to fix" in result.output


# -- TUI -------------------------------------------------------------------------------


def test_tui_open_rechecks_and_reports_fixed(tmp_path, monkeypatch):
    from checker.tui import FindingsApp

    lesson = make_lesson(tmp_path)
    runner.invoke(app, ["check", str(lesson), "-q"])
    path = default_results_path(lesson)
    monkeypatch.setenv("EDITOR", "nvim")
    monkeypatch.setattr("checker.tui.subprocess.run", lambda cmd, check: _fix_heading(lesson))
    seen = {}

    async def main():
        tui = FindingsApp(load(path), path)
        async with tui.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            tui.suspend = contextlib.nullcontext
            table = tui.query_one("#table")
            row = next(i for i, f in enumerate(tui.visible) if f.code == "WB213")
            table.move_cursor(row=row)
            await pilot.press("o")
            await pilot.pause()
            seen["codes"] = {f.code for f in tui.results.findings}

    asyncio.run(main())
    assert "WB213" not in seen["codes"]
    assert "WB213" not in {f.code for f in load(path).findings}
