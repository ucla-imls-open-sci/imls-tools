"""Command-sequence tests for the saved-results lifecycle (Codex review
items 3, 7, 8): one refresh policy across check, review, fix, and the TUI;
target identity; partial scope; stale AI findings; stable IDs."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from checker import app as app_mod
from checker.ai_review import ReviewResult
from checker.app import app
from checker.issues import plan_issues
from checker.refresh import normalize_target
from checker.report import Finding
from checker.results import default_results_path, load

runner = CliRunner()
BLOCKS = ":::: questions\n- Q?\n::::\n\n:::: objectives\n- Explain it.\n::::\n\n:::: keypoints\n- K.\n::::\n"


def episode(body: str = "## A\n\nSome content here.\n") -> str:
    return f"---\ntitle: 'E'\nteaching: 20\nexercises: 10\n---\n{BLOCKS}\n{body}"


def make_lesson(root: Path, name: str = "l", episodes: dict[str, str] | None = None) -> Path:
    d = root / name
    (d / "episodes").mkdir(parents=True)
    (d / "learners").mkdir()
    (d / "learners" / "reference.md").write_text("g\n")
    eps = episodes or {"01.md": episode()}
    (d / "config.yaml").write_text(
        "title: 'R'\ncontact: 'a@b.org'\ncreated: 2026-01-01\nsource: 'https://x'\nlife_cycle: alpha\n"
        "episodes:\n" + "".join(f"- {n}\n" for n in eps)
    )
    for n, t in eps.items():
        (d / "episodes" / n).write_text(t)
    return d


def fake_review(quote="Some content here.", message="Too terse for novices."):
    def review(text, location, mechanical, backend, model=None, glossary_text="", effort="high"):
        return ReviewResult(summary="ok", findings=[
            Finding("warning", "ai", message, location=location, line=15, hint="Expand.",
                    code="AI203", quote=quote, source="ai", scope="pacing")
        ])
    return review


def ai(results):
    return [f for f in results.findings if f.source == "ai"]


# -- 7: one merge policy -----------------------------------------------------------


def test_check_after_review_keeps_ai_findings(tmp_path, monkeypatch):
    d = make_lesson(tmp_path)
    monkeypatch.setattr("checker.ai_review.review_episode", fake_review())
    runner.invoke(app, ["review", str(d)])
    runner.invoke(app, ["check", str(d), "-q"])
    [f] = ai(load(default_results_path(d)))
    assert not f.stale


def test_editing_a_reviewed_file_marks_its_ai_findings_stale(tmp_path, monkeypatch):
    d = make_lesson(tmp_path)
    monkeypatch.setattr("checker.ai_review.review_episode", fake_review())
    runner.invoke(app, ["review", str(d)])
    ep = d / "episodes" / "01.md"
    ep.write_text(ep.read_text() + "\nAn edit.\n")
    result = runner.invoke(app, ["check", str(d), "-q"])
    assert "stale" in result.output
    saved = load(default_results_path(d))
    [f] = ai(saved)
    assert f.stale
    # stale findings are never filed, and the report says so
    assert not [x for d_ in plan_issues(saved)[0] for x in d_.findings if x.source == "ai"]
    report = runner.invoke(app, ["report", str(d)])
    assert "stale: the file changed after this AI review" in " ".join(report.output.split())
    # re-reviewing makes it fresh again
    runner.invoke(app, ["review", str(d)])
    assert not ai(load(default_results_path(d)))[0].stale


def test_episode_check_merges_into_full_results(tmp_path):
    d = make_lesson(tmp_path, episodes={"01.md": episode(), "02.md": episode("# H1 in 02\n")})
    runner.invoke(app, ["check", str(d), "-q"])
    runner.invoke(app, ["check", str(d), "-q", "--episode", "01.md"])
    saved = load(default_results_path(d))
    assert saved.scope == "full"
    assert any(f.code == "WB210" and f.location == "episodes/02.md" for f in saved.findings)


def test_episode_check_goes_partial_when_other_files_changed(tmp_path):
    d = make_lesson(tmp_path, episodes={"01.md": episode(), "02.md": episode()})
    runner.invoke(app, ["check", str(d), "-q"])
    (d / "episodes" / "02.md").write_text(episode("# new H1\n"))
    result = runner.invoke(app, ["check", str(d), "-q", "--episode", "01.md"])
    assert load(default_results_path(d)).scope == "partial"
    assert "partial results" in result.output


def test_review_after_partial_check_has_every_episode_checked(tmp_path, monkeypatch):
    d = make_lesson(tmp_path, episodes={"01.md": episode(), "02.md": episode("# H1 in 02\n")})
    runner.invoke(app, ["check", str(d), "-q", "--episode", "01.md"])  # partial, no prior results
    monkeypatch.setattr("checker.ai_review.review_episode", fake_review())
    runner.invoke(app, ["review", str(d), "--episode", "01.md"])
    saved = load(default_results_path(d))
    assert saved.scope == "full"
    assert any(f.code == "WB210" and f.location == "episodes/02.md" for f in saved.findings)


# -- 3: target identity -------------------------------------------------------------


def _as_clone(monkeypatch, mapping: dict[str, Path]):
    monkeypatch.setattr(app_mod, "_resolve_target",
                        lambda target: (mapping[target], SimpleNamespace(cleanup=lambda: None)))


def test_normalize_target_matches_https_and_ssh_forms(tmp_path):
    forms = ["https://github.com/Org/Repo.git", "git@github.com:Org/Repo.git", "https://GitHub.com/Org/Repo/",
             "ssh://git@github.com/Org/Repo"]
    assert {normalize_target(t, tmp_path, True) for t in forms} == {"github.com/Org/Repo"}


def test_different_urls_get_separate_results(tmp_path, monkeypatch):
    a = make_lesson(tmp_path, "a", {"01.md": episode("# H1 in A\n")})
    b = make_lesson(tmp_path, "b")
    _as_clone(monkeypatch, {"https://github.com/org/A": a, "https://github.com/org/B": b})
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    runner.invoke(app, ["check", "https://github.com/org/A", "-q"])
    runner.invoke(app, ["check", "https://github.com/org/B", "-q"])
    folders = sorted(p.name for p in (work / ".wbcheck").iterdir() if p.is_dir())
    assert folders == ["github.com_org_A", "github.com_org_B"]
    b_results = load(work / ".wbcheck" / "github.com_org_B" / "results.json")
    assert b_results.target_id == "github.com/org/B"
    assert not any(f.code == "WB210" for f in b_results.findings)


def test_results_for_another_target_are_replaced_not_merged(tmp_path, monkeypatch):
    a = make_lesson(tmp_path, "a")
    b = make_lesson(tmp_path, "b")
    shared = tmp_path / "shared.json"
    monkeypatch.setattr("checker.ai_review.review_episode", fake_review())
    runner.invoke(app, ["review", str(a), "--results", str(shared)])
    assert ai(load(shared))
    result = runner.invoke(app, ["check", str(b), "-q", "--results", str(shared)])
    assert "replaced saved results for a different lesson" in result.output
    saved = load(shared)
    assert saved.target_id == str(b.resolve()) and not ai(saved)


def test_same_url_new_revision_marks_changed_files_stale(tmp_path, monkeypatch):
    d = make_lesson(tmp_path, "repo")
    _as_clone(monkeypatch, {"https://github.com/org/R": d})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("checker.ai_review.review_episode", fake_review())
    runner.invoke(app, ["review", "https://github.com/org/R"])
    (d / "episodes" / "01.md").write_text(episode("## A\n\nSome content here, revised upstream.\n"))
    runner.invoke(app, ["check", "https://github.com/org/R", "-q"])
    [f] = ai(load(tmp_path / ".wbcheck" / "github.com_org_R" / "results.json"))
    assert f.stale


# -- 8: stable IDs -------------------------------------------------------------------


def test_ignoring_one_duplicate_does_not_move_its_id_to_a_sibling(tmp_path):
    d = make_lesson(tmp_path, episodes={"01.md": episode("## Dup\n\n## Dup\n\n## Dup\n")})
    runner.invoke(app, ["check", str(d), "-q"])
    dups = [f for f in load(default_results_path(d)).findings if f.code == "WB212"]
    first, second = dups[0], dups[1]
    (d / ".wbcheck.toml").write_text(f'[ignore]\nids = ["{first.id}"]\n')
    runner.invoke(app, ["check", str(d), "-q"])
    ids = [f.id for f in load(default_results_path(d)).findings if f.code == "WB212"]
    assert first.id not in ids
    assert second.id in ids


def test_reworded_ai_finding_on_same_quote_keeps_its_id(tmp_path, monkeypatch):
    d = make_lesson(tmp_path)
    monkeypatch.setattr("checker.ai_review.review_episode", fake_review(message="Too terse for novices."))
    runner.invoke(app, ["review", str(d)])
    first = ai(load(default_results_path(d)))[0].id
    monkeypatch.setattr("checker.ai_review.review_episode",
                        fake_review(message="This paragraph moves too fast for beginners."))
    runner.invoke(app, ["review", str(d)])
    assert ai(load(default_results_path(d)))[0].id == first


# -- #49: AI IDs survive ignoring a sibling ------------------------------------------------


def _two_same_anchor_findings(text, location, mechanical, backend, model=None, glossary_text="", effort="high"):
    return ReviewResult(summary="ok", findings=[
        Finding("warning", "ai", msg, location=location, line=15, hint="Fix.",
                code="AI203", quote="Some content here.", source="ai", scope="pacing")
        for msg in ("Too terse.", "No example.")
    ])


def test_ignoring_one_same_anchor_ai_finding_keeps_the_other(tmp_path, monkeypatch):
    d = make_lesson(tmp_path)
    monkeypatch.setattr("checker.ai_review.review_episode", _two_same_anchor_findings)
    runner.invoke(app, ["review", str(d)])
    first, second = sorted(ai(load(default_results_path(d))), key=lambda f: f.occurrence)
    assert first.id != second.id
    (d / ".wbcheck.toml").write_text(f'[ignore]\nids = ["{first.id}"]\n')
    for _ in range(3):
        assert runner.invoke(app, ["check", str(d), "-q"]).exit_code in (0, 1)
        assert [f.id for f in ai(load(default_results_path(d)))] == [second.id]


def test_rereview_numbers_new_findings_without_touching_other_episodes(tmp_path, monkeypatch):
    d = make_lesson(tmp_path, episodes={"01.md": episode(), "02.md": episode()})
    monkeypatch.setattr("checker.ai_review.review_episode", _two_same_anchor_findings)
    runner.invoke(app, ["review", str(d)])
    before = {f.id for f in ai(load(default_results_path(d))) if f.location == "episodes/02.md"}
    runner.invoke(app, ["review", str(d), "--episode", "01.md"])
    after = ai(load(default_results_path(d)))
    assert {f.id for f in after if f.location == "episodes/02.md"} == before
    assert len({f.id for f in after}) == len(after) == 4


def test_colliding_saved_ai_ids_are_renumbered():
    from checker.refresh import _keep_ai_ids

    same = [Finding("warning", "ai", m, location="episodes/01.md", code="AI203", quote="q", source="ai")
            for m in ("a", "b")]  # both occurrence 0, as an older results file would have them
    assert same[0].id == same[1].id
    kept = _keep_ai_ids(same)
    assert len({f.id for f in kept}) == 2


# -- compatibility -------------------------------------------------------------------


def test_version_1_results_files_still_load(tmp_path):
    d = make_lesson(tmp_path)
    runner.invoke(app, ["check", str(d), "-q"])
    path = default_results_path(d)
    data = json.loads(path.read_text())
    data["version"] = 1
    for key in ("target_id", "revision", "scope", "file_hashes"):
        data.pop(key)
    path.write_text(json.dumps(data))
    old = load(path)
    assert old.scope == "full" and old.target_id is None
    result = runner.invoke(app, ["check", str(d), "-q"])
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert load(path).target_id == str(d.resolve())


@pytest.mark.parametrize("cmd", [["check", "-q"], ["tui"]])
def test_commands_write_target_identity(tmp_path, monkeypatch, cmd):
    d = make_lesson(tmp_path)
    monkeypatch.setattr("checker.tui.run", lambda results, path: None)
    runner.invoke(app, [cmd[0], str(d), *cmd[1:]])
    saved = load(default_results_path(d))
    assert saved.target_id == str(d.resolve()) and saved.file_hashes


# -- #48: invocation scope vs saved scope ----------------------------------------------


def test_episode_check_shows_and_fails_on_that_episode_only(tmp_path):
    d = make_lesson(tmp_path, episodes={"01.md": episode(), "02.md": episode("# Top level\n\ntext\n")})
    assert runner.invoke(app, ["check", str(d), "-q"]).exit_code == 1  # 02.md has an H1 error
    result = runner.invoke(app, ["check", str(d), "--episode", "01.md"])
    assert result.exit_code == 0, result.output
    assert "02.md" not in result.output
    saved = load(default_results_path(d))
    assert any(f.location == "episodes/02.md" for f in saved.findings)  # still saved


def test_partial_results_are_labelled_in_reports(tmp_path):
    d = make_lesson(tmp_path, episodes={"01.md": episode(), "02.md": episode("# Top level\n\ntext\n")})
    runner.invoke(app, ["check", str(d), "--episode", "01.md", "-q"])  # no full results yet
    assert load(default_results_path(d)).scope == "partial"
    terminal = runner.invoke(app, ["report", str(d)]).output
    assert "Partial results" in terminal and "No issues found" not in terminal
    md = tmp_path / "r.md"
    runner.invoke(app, ["report", str(d), "--md", str(md)])
    text = md.read_text()
    assert "Partial results" in text and "All checks passed" not in text
