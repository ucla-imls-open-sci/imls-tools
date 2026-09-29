"""Tests for v0.2.0 quick wins: version sync, shell completion, --fail-on,
auto issue grouping, and the heading-level-jump check (WB213)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from typer.testing import CliRunner

from checker import __version__
from checker.app import app
from checker.issues import plan_issues
from checker.lesson_check import _check_headings
from checker.report import Finding
from checker.results import Results

runner = CliRunner()
ROOT = Path(__file__).resolve().parent.parent


def test_version_matches_pixi_workspace_and_cli():
    pixi = tomllib.loads((ROOT / "pixi.toml").read_text())
    assert pixi["workspace"]["version"] == __version__
    assert runner.invoke(app, ["--version"]).output.strip() == f"wbcheck {__version__}"


def test_shell_completion_is_offered():
    assert "--install-completion" in runner.invoke(app, ["--help"]).output


# -- --fail-on -----------------------------------------------------------------

WARNING_ONLY = """---
title: 'Ep'
teaching: 15
exercises: 15
---
:::: questions
- What?
::::

:::: objectives
- Understand it.
::::

## Part

:::: challenge
Try.
:::: solution
Done.
::::
::::

:::: keypoints
- Point.
::::
"""


def _lesson(tmp_path: Path, episode: str) -> Path:
    lesson = tmp_path / "lesson"
    (lesson / "episodes").mkdir(parents=True)
    (lesson / "learners").mkdir()
    (lesson / "learners" / "reference.md").write_text("## Glossary\n")
    (lesson / "config.yaml").write_text(
        "title: 'Real'\ncontact: 'a@b.org'\ncreated: 2026-01-01\nsource: 'https://x.org'\n"
        "life_cycle: 'alpha'\nepisodes:\n- 01.md\n"
    )
    (lesson / "episodes" / "01.md").write_text(episode)
    return lesson


def test_fail_on_thresholds(tmp_path):
    lesson = _lesson(tmp_path, WARNING_ONLY)  # one WB401 warning, no errors
    assert runner.invoke(app, ["check", str(lesson), "-q"]).exit_code == 0
    assert runner.invoke(app, ["check", str(lesson), "-q", "--fail-on", "warning"]).exit_code == 1
    assert runner.invoke(app, ["check", str(lesson), "-q", "--fail-on", "info"]).exit_code == 1
    assert runner.invoke(app, ["check", str(lesson), "-q", "--fail-on", "bogus"]).exit_code == 2


def test_fail_on_never_ignores_errors(tmp_path):
    lesson = _lesson(tmp_path, "## no front matter or blocks\n")
    assert runner.invoke(app, ["check", str(lesson), "-q"]).exit_code == 1
    assert runner.invoke(app, ["check", str(lesson), "-q", "--fail-on", "never"]).exit_code == 0


# -- auto grouping ---------------------------------------------------------------


def _f(code, location, line=3, source="mechanical", scope=None):
    return Finding("warning", "x", f"{code} at {location}", location=location, line=line, code=code,
                   source=source, scope=scope, quote="some quoted text" if source == "ai" else None)


def test_auto_grouping_sweeps_rules_seen_in_three_files():
    findings = [_f("WB401", f"episodes/0{i}.md") for i in range(1, 4)] + [
        _f("WB212", "episodes/01.md"), _f("WB301", "episodes/02.md"), _f("WB301", "episodes/03.md"),
    ]
    drafts, _ = plan_issues(Results(target="x", lesson_dir=None, findings=findings))
    titles = sorted(d.title for d in drafts)
    assert "WB401 objective opens with a hard-to-assess verb (3 in 3 files)" in titles
    # WB301 is only in 2 files: stays per file, alongside the other per-file finding
    assert "episodes/01.md: 1 warning (WB212)" in titles
    assert "episodes/02.md: 1 warning (WB301)" in titles
    assert len(drafts) == 4


def test_auto_grouping_leaves_ai_findings_by_scope():
    findings = [_f("AI205", f"episodes/0{i}.md", source="ai", scope="tone") for i in range(1, 4)]
    drafts, _ = plan_issues(Results(target="x", lesson_dir=None, findings=findings))
    assert all("AI review" in d.title for d in drafts)


def test_file_grouping_still_available():
    findings = [_f("WB401", f"episodes/0{i}.md") for i in range(1, 4)]
    drafts, _ = plan_issues(Results(target="x", lesson_dir=None, findings=findings), group_by="file")
    assert len(drafts) == 3


# -- WB213 heading level jumps -------------------------------------------------------


def _codes(body):
    return [f.code for f in _check_headings(body, "ep.md")]


def test_heading_jump_h2_to_h4_is_flagged_with_line():
    [f] = [f for f in _check_headings("## A\n\ntext\n\n#### Deep\n", "ep.md") if f.code == "WB213"]
    assert f.line == 5
    assert "Use level 3 here" in f.hint


def test_heading_steps_and_step_backs_are_fine():
    assert "WB213" not in _codes("## A\n### B\n#### C\n## D\n### E\n")


def test_div_titles_are_part_of_the_outline():
    # h2, then a callout's h3, then h4: no level skipped in the rendered page
    assert "WB213" not in _codes("## A\n\n:::: checklist\n### Box\n::::\n\n#### Sub\n")
    # a callout titled h4 directly under h2 does skip h3 on the rendered page
    assert "WB213" in _codes("## A\n\n:::: callout\n#### Note title\n::::\n")
