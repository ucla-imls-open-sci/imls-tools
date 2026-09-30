"""Tests for the `wbcheck` subcommand CLI and its results file (issue #24)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from checker.app import app
from checker.report import Finding
from checker.results import Results, default_results_path, load, save

runner = CliRunner()

CLEAN_BODY = """\
:::: questions
- What is this?
::::

:::: objectives
- Explain the thing.
::::

## A heading

Some content.

:::: challenge
Try it.
:::: solution
Done.
::::
::::

:::: keypoints
- A point.
::::
"""


def make_lesson(tmp_path: Path, body: str = CLEAN_BODY) -> Path:
    lesson_dir = tmp_path / "lesson"
    (lesson_dir / "episodes").mkdir(parents=True)
    (lesson_dir / "learners").mkdir()
    (lesson_dir / "learners" / "reference.md").write_text("## Glossary\n\nTerm\n: Definition.\n")
    (lesson_dir / "config.yaml").write_text(
        "title: 'Real'\ncontact: 'a@b.org'\ncreated: 2026-01-01\nsource: 'https://x.org'\n"
        "life_cycle: 'alpha'\nepisodes:\n- 01.md\n"
    )
    (lesson_dir / "episodes" / "01.md").write_text(f"---\ntitle: 'Ep'\nteaching: 15\nexercises: 15\n---\n{body}")
    return lesson_dir


# -- results file --------------------------------------------------------------


def test_results_round_trip_preserves_findings_and_ids(tmp_path):
    f = Finding("warning", "headings", "heading `X` on line 4 duplicates the one on line 2",
                location="episodes/01.md", line=4, code="WB212", occurrence=1)
    results = Results(target="lesson", lesson_dir=str(tmp_path), findings=[f],
                      github_base="https://github.com/o/r/blob/abc", dirty_files=["episodes/01.md"],
                      ai_reviews={"01.md (ollama)": "Looks fine."})
    path = save(results, default_results_path(tmp_path))
    loaded = load(path)
    assert loaded.findings[0] == f
    assert loaded.findings[0].id == f.id
    assert loaded.github_base == results.github_base
    assert loaded.dirty_files == ["episodes/01.md"]
    assert loaded.ai_reviews == results.ai_reviews


def test_save_writes_self_ignoring_gitignore(tmp_path):
    path = save(Results(target="x", lesson_dir=None), default_results_path(tmp_path))
    assert (path.parent / ".gitignore").read_text().strip().endswith("*")


def test_load_rejects_unknown_version(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"version": 999, "target": "x"}))
    result = runner.invoke(app, ["report", str(tmp_path), "--results", str(path)])
    assert result.exit_code == 2
    assert "not supported" in result.output


# -- check ---------------------------------------------------------------------


def test_check_clean_lesson_exits_zero_and_saves_results(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    result = runner.invoke(app, ["check", str(lesson_dir)])
    assert result.exit_code == 0, result.output
    assert "No issues found" in result.output
    saved = load(default_results_path(lesson_dir))
    assert saved.findings == []
    assert saved.lesson_dir == str(lesson_dir)


def test_check_with_errors_exits_one_and_shows_codes(tmp_path):
    lesson_dir = make_lesson(tmp_path, body="## Only a heading\n")
    result = runner.invoke(app, ["check", str(lesson_dir)])
    assert result.exit_code == 1
    assert "WB204" in result.output
    assert any(f.code == "WB204" for f in load(default_results_path(lesson_dir)).findings)


def test_check_results_override_and_quiet(tmp_path):
    lesson_dir = make_lesson(tmp_path, body="## Only a heading\n")
    out = tmp_path / "elsewhere" / "r.json"
    result = runner.invoke(app, ["check", str(lesson_dir), "--results", str(out), "--quiet"])
    assert result.exit_code == 1
    assert "WB204" not in result.stdout
    assert out.exists()
    assert not default_results_path(lesson_dir).exists()


def test_report_keeps_bracketed_hint_text(tmp_path):
    # Hint text with literal brackets must not be eaten as Rich markup tags.
    f = Finding("warning", "objectives", "vague [objective]", location="episodes/01.md",
                hint="[CLDT] see [bold]not markup[/bold]", code="WB401")
    save(Results(target="x", lesson_dir=None, findings=[f]), default_results_path(tmp_path))
    result = runner.invoke(app, ["report", str(tmp_path)])
    assert "vague [objective]" in result.output
    assert "[CLDT] see [bold]not markup[/bold]" in result.output


def test_check_source_shows_the_offending_line(tmp_path):
    lesson_dir = make_lesson(tmp_path, body=CLEAN_BODY + "\n# Big heading\n")
    result = runner.invoke(app, ["check", str(lesson_dir), "--source"])
    assert "WB210" in result.output
    assert "# Big heading" in result.output


# -- report --------------------------------------------------------------------


def test_report_without_results_exits_two(tmp_path):
    result = runner.invoke(app, ["report", str(tmp_path)])
    assert result.exit_code == 2
    assert "wbcheck check" in result.output


def test_report_renders_saved_results_to_terminal(tmp_path):
    lesson_dir = make_lesson(tmp_path, body="## Only a heading\n")
    runner.invoke(app, ["check", str(lesson_dir), "--quiet"])
    result = runner.invoke(app, ["report", str(lesson_dir)])
    assert result.exit_code == 0
    assert "WB204" in result.output


def test_report_writes_markdown_and_json(tmp_path):
    lesson_dir = make_lesson(tmp_path, body="## Only a heading\n")
    runner.invoke(app, ["check", str(lesson_dir), "--quiet"])
    md, js = tmp_path / "r.md", tmp_path / "r.json"
    result = runner.invoke(app, ["report", str(lesson_dir), "--md", str(md), "--json", str(js)])
    assert result.exit_code == 0, result.output
    assert "`WB204`" in md.read_text()
    assert json.loads(js.read_text())["findings"][0]["id"]


def test_report_html_when_quarto_missing_warns(tmp_path, monkeypatch):
    lesson_dir = make_lesson(tmp_path)
    runner.invoke(app, ["check", str(lesson_dir), "--quiet"])
    monkeypatch.setattr("checker.app.render_html_via_quarto", lambda *a, **k: None)
    result = runner.invoke(app, ["report", str(lesson_dir), "--html", str(tmp_path / "r.html"), "--open"])
    assert result.exit_code == 0
    assert "quarto not found" in result.output
    assert "nothing to open" in result.output


# -- review --------------------------------------------------------------------


def _fake_result(location, quote="Some content."):
    from checker.ai_review import ReviewResult

    return ReviewResult(
        summary="**Objectives** look assessable.",
        findings=[
            Finding("warning", "ai", "Too terse for novices.", location=location, line=13,
                    hint="Add a worked example.", code="AI203", quote=quote, source="ai", scope="pacing")
        ],
    )


def test_review_adds_structured_ai_findings_to_saved_results(tmp_path, monkeypatch):
    lesson_dir = make_lesson(tmp_path)
    runner.invoke(app, ["check", str(lesson_dir), "--quiet"])
    calls = []

    def fake_review(text, location, mechanical, backend, model=None, glossary_text="", effort="high"):
        calls.append((location, backend, glossary_text, effort))
        return _fake_result(location)

    monkeypatch.setattr("checker.ai_review.review_episode", fake_review)
    result = runner.invoke(app, ["review", str(lesson_dir), "--backend", "claude", "--effort", "medium"])
    assert result.exit_code == 0, result.output
    location, backend, glossary, effort = calls[0]
    assert (location, backend, effort) == ("episodes/01.md", "claude", "medium")
    assert "Term" in glossary
    saved = load(default_results_path(lesson_dir))
    [f] = [f for f in saved.findings if f.source == "ai"]
    assert (f.code, f.scope, f.quote) == ("AI203", "pacing", "Some content.")
    assert saved.ai_reviews["01.md (claude)"].startswith("**Objectives**")
    assert "AI203" in result.output


def test_review_replaces_earlier_ai_findings_for_the_episode(tmp_path, monkeypatch):
    lesson_dir = make_lesson(tmp_path)
    monkeypatch.setattr("checker.ai_review.review_episode", lambda *a, **k: _fake_result(a[1], quote="first"))
    runner.invoke(app, ["review", str(lesson_dir)])
    monkeypatch.setattr("checker.ai_review.review_episode", lambda *a, **k: _fake_result(a[1], quote="second"))
    runner.invoke(app, ["review", str(lesson_dir)])
    quotes = [f.quote for f in load(default_results_path(lesson_dir)).findings if f.source == "ai"]
    assert quotes == ["second"]


def test_review_failure_keeps_earlier_ai_findings(tmp_path, monkeypatch):
    lesson_dir = make_lesson(tmp_path)
    monkeypatch.setattr("checker.ai_review.review_episode", lambda *a, **k: _fake_result(a[1], quote="kept"))
    runner.invoke(app, ["review", str(lesson_dir)])

    def boom(*args, **kwargs):
        raise ConnectionError("ollama not running")

    monkeypatch.setattr("checker.ai_review.review_episode", boom)
    result = runner.invoke(app, ["review", str(lesson_dir)])
    assert result.exit_code == 1  # the requested review didn't complete
    assert "1 of 1 episode review(s) failed" in result.output
    saved = load(default_results_path(lesson_dir))
    assert saved.ai_reviews["01.md (ollama)"].startswith("(AI review failed: ollama not running")
    assert [f.quote for f in saved.findings if f.source == "ai"] == ["kept"]


def test_review_rejects_unknown_effort(tmp_path):
    result = runner.invoke(app, ["review", str(make_lesson(tmp_path)), "--effort", "extreme"])
    assert result.exit_code == 2


def test_review_rejects_unknown_backend(tmp_path):
    result = runner.invoke(app, ["review", str(make_lesson(tmp_path)), "--backend", "codex"])
    assert result.exit_code == 2


def test_review_unmatched_episode_is_an_error(tmp_path, monkeypatch):
    lesson_dir = make_lesson(tmp_path)
    monkeypatch.setattr("checker.ai_review.review_episode", lambda *a, **k: _fake_result(a[1]))
    result = runner.invoke(app, ["review", str(lesson_dir), "--episode", "nope.md"])
    assert result.exit_code == 2
    assert "no episode named" in result.output
