"""Tests for turning saved results into GitHub issues (issue #21).

gh is never called for real: `checker.issues._gh` is replaced with a fake
that records calls and serves canned `issue list` / `label list` output.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from checker import issues
from checker.app import app
from checker.issues import ID_MARKER_RE, plan_issues, repo_from_results
from checker.report import Finding
from checker.results import Results, default_results_path, save

runner = CliRunner()
BASE = "https://github.com/org/lesson/blob/0123456789abcdef0123456789abcdef01234567"


def _results(findings: list[Finding], **kwargs) -> Results:
    return Results(target="lesson", lesson_dir=None, findings=findings, github_base=BASE,
                   generated="2026-09-29T12:00:00+00:00", **kwargs)


def _mech(code="WB301", location="episodes/01.md", line=3, severity="warning", msg=None):
    return Finding(severity, "links", msg or f"{code} problem on line {line}", location=location,
                   line=line, hint="Do the fix.", code=code)


def _ai(scope, location="episodes/01.md", line=10, quote="Simply run it"):
    return Finding("warning", "ai", f"AI problem ({scope}, {quote})", location=location, line=line,
                   hint="Rewrite.", code="AI205", quote=quote, source="ai", scope=scope)


# -- planning ------------------------------------------------------------------


def test_repo_from_results():
    assert repo_from_results(_results([])) == "org/lesson"
    assert repo_from_results(Results(target="x", lesson_dir=None)) is None


def test_group_by_file_one_issue_per_file_with_counts_and_codes():
    drafts, skipped = plan_issues(_results([
        _mech("WB301", line=3), _mech("WB212", line=9), _mech("WB304", location="episodes/02.md", severity="error"),
    ]))
    assert skipped == 0
    titles = [d.title for d in drafts]
    # errors first
    assert titles[0] == "episodes/02.md: 1 error (WB304)"
    assert titles[1] == "episodes/01.md: 2 warnings (WB212, WB301)"
    assert all(d.labels == ["wbcheck"] for d in drafts)


def test_group_by_rule_one_issue_per_code_across_files():
    drafts, _ = plan_issues(_results([
        _mech("WB301", location="episodes/01.md"), _mech("WB301", location="episodes/02.md"), _mech("WB212"),
    ]), group_by="rule")
    titles = sorted(d.title for d in drafts)
    assert "WB301 image has no alt text (2 in 2 files)" in titles
    assert "WB212 duplicate heading text (1 in 1 file)" in titles


def test_ai_findings_group_by_scope_and_fold_singletons():
    drafts, _ = plan_issues(_results([
        _ai("objectives", line=5, quote="aaaaaaaa"), _ai("objectives", line=6, quote="bbbbbbbb"),
        _ai("tone", line=7), _ai("glossary", line=8, quote="cccccccc"),
        _mech("WB301"),
    ]))
    titles = {d.title: d for d in drafts}
    assert "episodes/01.md: objectives (AI review, 2 suggestion(s))" in titles
    other = titles["episodes/01.md: other suggestions (AI review, 2 suggestion(s))"]
    assert other.labels == ["wbcheck", "ai-suggested"]
    assert "episodes/01.md: 1 warning (WB301)" in titles


def test_min_severity_and_source_filters():
    findings = [_mech(severity="info"), _mech("WB212", severity="warning"), _ai("tone")]
    assert sum(len(d.findings) for d in plan_issues(_results(findings))[0]) == 2
    assert sum(len(d.findings) for d in plan_issues(_results(findings), min_severity="info")[0]) == 3
    only_ai = plan_issues(_results(findings), source="ai")[0]
    assert [f.source for d in only_ai for f in d.findings] == ["ai"]


def test_body_embeds_every_id_links_lines_and_explains_rules():
    findings = [_mech("WB301", line=3), _mech("WB212", line=9)]
    [draft] = plan_issues(_results(findings))[0]
    assert sorted(ID_MARKER_RE.findall(draft.body)) == sorted(f.id for f in findings)
    assert f"({BASE}/episodes/01.md#L3)" in draft.body
    assert "### Why these matter" in draft.body and "**WB301** image has no alt text" in draft.body
    assert "at commit `0123456789ab`" in draft.body


def test_ai_body_carries_quote_and_verification_note():
    [draft] = plan_issues(_results([_ai("tone"), _ai("tone", line=11, quote="just type")]))[0]
    assert "> Simply run it" in draft.body
    assert "[!NOTE]" in draft.body and "AI review" in draft.body


def test_dirty_files_are_not_linked():
    [draft] = plan_issues(_results([_mech()], dirty_files=["episodes/01.md"]))[0]
    assert "uncommitted, not yet on GitHub" in draft.body
    assert BASE not in draft.body.split("### To fix")[1].split("### Why")[0]


def test_already_filed_findings_are_skipped():
    a, b = _mech("WB301", line=3), _mech("WB212", line=9)
    drafts, skipped = plan_issues(_results([a, b]), already_filed={a.id})
    assert skipped == 1
    assert [f.id for d in drafts for f in d.findings] == [b.id]
    assert plan_issues(_results([a]), already_filed={a.id}) == ([], 1)


# -- CLI with a fake gh ----------------------------------------------------------


class FakeGh:
    def __init__(self, existing_bodies=(), labels=()):
        self.calls: list[tuple[list[str], str | None]] = []
        self.existing = [{"body": b} for b in existing_bodies]
        self.labels = [{"name": n} for n in labels]
        self.created = 0

    def __call__(self, args, input_text=None):
        self.calls.append((args, input_text))
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.existing)
        if args[:2] == ["label", "list"]:
            return json.dumps(self.labels)
        if args[:2] == ["issue", "create"]:
            self.created += 1
            self.existing.append({"body": input_text})
            return f"https://github.com/org/lesson/issues/{self.created}\n"
        return ""


@pytest.fixture
def lesson_with_results(tmp_path):
    lesson = tmp_path / "lesson"
    save(_results([_mech("WB301", line=3), _mech("WB304", location="episodes/02.md", severity="error")]),
         default_results_path(lesson))
    return lesson


def test_issues_dry_run_lists_without_creating(lesson_with_results, monkeypatch):
    gh = FakeGh()
    monkeypatch.setattr(issues, "_gh", gh)
    result = runner.invoke(app, ["issues", str(lesson_with_results)])
    assert result.exit_code == 0, result.output
    assert "2 issue(s) for org/lesson" in result.output
    assert "dry run" in result.output
    assert not any(args[:2] == ["issue", "create"] for args, _ in gh.calls)


def test_issues_preview_prints_bodies(lesson_with_results, monkeypatch):
    monkeypatch.setattr(issues, "_gh", FakeGh())
    result = runner.invoke(app, ["issues", str(lesson_with_results), "--preview"])
    assert "To fix" in result.output and "Why these matter" in result.output


def test_issues_create_files_labels_then_is_idempotent(lesson_with_results, monkeypatch):
    gh = FakeGh()
    monkeypatch.setattr(issues, "_gh", gh)
    result = runner.invoke(app, ["issues", str(lesson_with_results), "--create", "--yes"])
    assert result.exit_code == 0, result.output
    assert gh.created == 2
    label_creates = [args for args, _ in gh.calls if args[:2] == ["label", "create"]]
    assert [a[2] for a in label_creates] == ["wbcheck"]
    create = next(args for args, _ in gh.calls if args[:2] == ["issue", "create"])
    assert create[create.index("--repo") + 1] == "org/lesson"
    # second run finds its own markers and files nothing
    again = runner.invoke(app, ["issues", str(lesson_with_results), "--create", "--yes"])
    assert again.exit_code == 0
    assert "Nothing new to file" in again.output and "2 finding(s) already filed" in again.output
    assert gh.created == 2


def test_issues_create_asks_for_confirmation(lesson_with_results, monkeypatch):
    gh = FakeGh()
    monkeypatch.setattr(issues, "_gh", gh)
    result = runner.invoke(app, ["issues", str(lesson_with_results), "--create"], input="n\n")
    assert result.exit_code == 1
    assert gh.created == 0


def test_issues_create_without_repo_is_an_error(tmp_path):
    lesson = tmp_path / "lesson"
    save(Results(target="x", lesson_dir=None, findings=[_mech()]), default_results_path(lesson))
    result = runner.invoke(app, ["issues", str(lesson), "--create", "--yes"])
    assert result.exit_code == 2
    assert "--repo" in result.output


def test_issues_repo_override_and_bad_options(lesson_with_results, monkeypatch):
    gh = FakeGh()
    monkeypatch.setattr(issues, "_gh", gh)
    runner.invoke(app, ["issues", str(lesson_with_results), "--repo", "me/fork"])
    list_call = next(args for args, _ in gh.calls if args[:2] == ["issue", "list"])
    assert list_call[list_call.index("--repo") + 1] == "me/fork"
    assert runner.invoke(app, ["issues", str(lesson_with_results), "--group-by", "x"]).exit_code == 2
    assert runner.invoke(app, ["issues", str(lesson_with_results), "--min-severity", "x"]).exit_code == 2


def test_issues_dry_run_survives_gh_failure(lesson_with_results, monkeypatch):
    def broken(args, input_text=None):
        raise issues.GhError("not logged in")

    monkeypatch.setattr(issues, "_gh", broken)
    result = runner.invoke(app, ["issues", str(lesson_with_results)])
    assert result.exit_code == 0
    assert "couldn't check org/lesson" in result.output
