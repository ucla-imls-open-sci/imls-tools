"""Finding identity across message rewording (STD-06, design/2026-09-30-*).

Golden IDs in tests/fixtures/identity_golden_0.2.1.json were produced by
wbcheck 0.2.1 (main at 9032b05) on tests/fixtures/identity_lesson, before
any message wording changed; identity_results_v2_0.2.1.json is that
version's saved results file. A finding that still exists after a wording
change or a detector fix must keep its 0.2.1 ID, so `.wbcheck.toml` ignores
and hidden issue markers keep working. A finding the fixed detector no
longer reports (a former false positive) must not hand its ID to another.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from checker import issues
from checker.app import app
from checker.lesson_check import run_checks
from checker.report import Finding, legacy_anchor
from checker.results import RESULTS_VERSION, Results, ResultsFormatError, default_results_path, load, save

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
LESSON = FIXTURES / "identity_lesson"
GOLDEN = json.loads((FIXTURES / "identity_golden_0.2.1.json").read_text())
GOLDEN_IDS = {g["id"] for g in GOLDEN}

# 0.2.1 findings the corrected detectors no longer report, by (code, line):
# the explicit alt="" decorative image (STD-01), the `### Example` repeated
# under a *different* parent (STD-03), and the nested `- Know ...` bullet,
# which explains its parent objective rather than being one (STD-07).
RETIRED = {("WB301", 29), ("WB212", 25), ("WB401", 13)}


def lesson_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "lesson"
    shutil.copytree(LESSON, dest)
    return dest


def test_fresh_check_keeps_every_surviving_0_2_1_id():
    now = {f.id: f for f in run_checks(LESSON)}
    for g in GOLDEN:
        if (g["code"], g["line"]) in RETIRED:
            assert g["id"] not in now, f"{g['code']} line {g['line']} should no longer be reported"
        else:
            assert g["id"] in now, f"{g['code']} line {g['line']} lost its 0.2.1 ID"
            assert now[g["id"]].code == g["code"]


def test_retired_ids_are_not_reused_by_other_findings():
    retired = {g["id"] for g in GOLDEN if (g["code"], g["line"]) in RETIRED}
    assert retired.isdisjoint({f.id for f in run_checks(LESSON)})


def test_ids_are_unique_within_a_run():
    ids = [f.id for f in run_checks(LESSON)]
    assert len(ids) == len(set(ids))


def test_legacy_anchor_reproduces_the_old_hash():
    old = Finding("warning", "objectives", "3 objective(s) declared but exercises: 0 -- nothing "
                  "in this episode formally assesses them", location="episodes/a.md", code="WB403")
    reworded = Finding("warning", "objectives", "completely different wording", location="episodes/a.md",
                       code="WB403", identity_anchor=legacy_anchor(old.message))
    assert reworded.id == old.id
    # a legacy occurrence number maps onto the old occurrence suffix
    old.occurrence = 2
    reworded.identity_anchor = legacy_anchor(old.message, 2)
    assert reworded.id == old.id


def test_changing_file_or_rule_still_changes_the_id():
    base = Finding("warning", "x", "msg", location="episodes/a.md", code="WB403", identity_anchor="a")
    other_file = Finding("warning", "x", "msg", location="episodes/b.md", code="WB403", identity_anchor="a")
    other_rule = Finding("warning", "x", "msg", location="episodes/a.md", code="WB401", identity_anchor="a")
    assert len({base.id, other_file.id, other_rule.id}) == 3


# -- saved results -----------------------------------------------------------------


def test_version_2_results_from_0_2_1_load_with_their_ids():
    results = load(FIXTURES / "identity_results_v2_0.2.1.json")
    assert {f.id for f in results.findings} == GOLDEN_IDS
    # anchors are frozen from the stored wording, so they survive re-serialization
    assert all(f.identity_anchor for f in results.findings if f.source != "ai")


def test_version_3_round_trip_keeps_ids_and_anchors(tmp_path):
    fresh = run_checks(LESSON)
    path = tmp_path / "results.json"
    save(Results(target="x", lesson_dir=None, findings=fresh), path)
    data = json.loads(path.read_text())
    assert data["version"] == RESULTS_VERSION == 3
    loaded = load(path)
    assert [f.id for f in loaded.findings] == [f.id for f in fresh]
    assert [f.identity_anchor for f in loaded.findings] == [f.identity_anchor for f in fresh]


def test_non_string_identity_anchor_is_a_format_error(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"version": 3, "target": "x", "findings": [
        {"severity": "warning", "category": "c", "message": "m", "identity_anchor": 5}]}))
    with pytest.raises(ResultsFormatError):
        load(path)


def test_future_versions_are_rejected_clearly(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"version": 4, "target": "x", "findings": []}))
    with pytest.raises(ResultsFormatError, match="version 4 is not supported"):
        load(path)


# -- ignores and filed issues keyed on 0.2.1 IDs -------------------------------------


@pytest.mark.parametrize("golden", [g for g in GOLDEN if (g["code"], g["line"]) not in RETIRED],
                         ids=lambda g: f"{g['code']}-{g['line']}")
def test_old_id_ignore_applies_without_any_saved_results(tmp_path, golden):
    lesson = lesson_copy(tmp_path)
    (lesson / ".wbcheck.toml").write_text(f'[ignore]\nids = ["{golden["id"]}"]\n')
    assert not default_results_path(lesson).exists()
    runner.invoke(app, ["check", str(lesson), "-q"])
    results = load(default_results_path(lesson))
    assert golden["id"] not in {f.id for f in results.findings}
    assert results.ignored == 1


def test_old_issue_markers_open_or_closed_prevent_refiling(tmp_path, monkeypatch):
    lesson = lesson_copy(tmp_path)
    runner.invoke(app, ["check", str(lesson), "-q"])
    results = load(default_results_path(lesson))
    # bodies of issues filed by 0.2.1; `gh issue list --state all` returns closed ones too
    bodies = [f"<!-- wbcheck:id={g['id']} -->" for g in GOLDEN]
    monkeypatch.setattr(issues, "_gh", lambda args, input_text=None: json.dumps([{"body": b} for b in bodies]))
    already = issues.filed_ids("org/lesson")
    drafts, skipped = issues.plan_issues(results, min_severity="info", already_filed=already)
    assert drafts == []
    assert skipped == len(results.findings)


# -- fixes and partial refresh with old and new findings ------------------------------


def test_fix_planning_works_from_a_0_2_1_results_file(tmp_path):
    from checker.fix import AUTOFIX_CODES, plan_autofixes

    lesson = lesson_copy(tmp_path)
    old = load(FIXTURES / "identity_results_v2_0.2.1.json")
    planned = {fix.finding.code for fix in plan_autofixes(old.findings, lesson, AUTOFIX_CODES)}
    assert {"WB009", "WB401"} <= planned  # message-parsing (WB009) and line-based (WB401) handlers


def test_fix_planning_works_from_fresh_findings(tmp_path):
    from checker.fix import AUTOFIX_CODES, plan_autofixes

    lesson = lesson_copy(tmp_path)
    planned = {fix.finding.code for fix in plan_autofixes(run_checks(lesson), lesson, AUTOFIX_CODES)}
    assert {"WB009", "WB401"} <= planned


def test_partial_refresh_keeps_0_2_1_ids(tmp_path):
    lesson = lesson_copy(tmp_path)
    runner.invoke(app, ["check", str(lesson), "-q"])
    runner.invoke(app, ["check", str(lesson), "--episode", "01-intro.md", "-q"])
    saved = {f.id for f in load(default_results_path(lesson)).findings}
    surviving = {g["id"] for g in GOLDEN if (g["code"], g["line"]) not in RETIRED}
    assert surviving <= saved


# -- WB401 occurrence slots (review REV-01) --------------------------------------------
# 0.2.1 IDs for these bodies at episodes/a.md, from main at 9032b05.

NESTED_THEN_TOP = "- Explain the workflow\n  - Understand data\n- Understand data"
PLUS_THEN_DASH = "+ Understand data\n\n- Understand data"
OLD_NESTED, OLD_TOP = "cc83a9a971e1", "3c4e43f7ac85"  # 0.2.1: nested line 3, top-level line 4


def objective_findings(items: str):
    from checker.lesson_check import _check_objective_verbs
    from checker.report import assign_occurrences

    findings, _ = _check_objective_verbs(f"::: objectives\n{items}\n:::\n", "episodes/a.md")
    return {f.line: f.id for f in assign_occurrences(findings)}


def test_dropping_a_nested_objective_does_not_move_its_id():
    assert objective_findings(NESTED_THEN_TOP) == {4: OLD_TOP}


def test_a_newly_recognized_plus_objective_cannot_take_a_legacy_id():
    ids = objective_findings(PLUS_THEN_DASH)
    assert ids[4] == OLD_NESTED  # 0.2.1 reported only line 4, with this ID
    assert ids[2] not in {OLD_NESTED, OLD_TOP}


@pytest.mark.parametrize(("items", "ignored", "expected"), [
    (NESTED_THEN_TOP, OLD_NESTED, {OLD_TOP}),  # ignoring the old nested item hides nothing now
    (PLUS_THEN_DASH, OLD_NESTED, None),  # ignoring line 4's old ID still hides line 4, not line 2
])
def test_old_wb401_ignores_apply_to_the_right_finding(tmp_path, items, ignored, expected):
    lesson = lesson_copy(tmp_path)
    episode = (lesson / "episodes" / "a.md")
    episode.write_text(f"---\ntitle: 'A'\nteaching: 20\nexercises: 10\n---\n\n"
                       f":::: questions\n- Q?\n::::\n\n::: objectives\n{items}\n:::\n\n:::: keypoints\n- K.\n::::\n")
    (lesson / ".wbcheck.toml").write_text(f'[ignore]\nids = ["{ignored}"]\n')
    runner.invoke(app, ["check", str(lesson), "-q"])
    wb401 = [f for f in load(default_results_path(lesson)).findings
             if f.code == "WB401" and f.location == "episodes/a.md"]
    if expected is not None:
        assert {f.id for f in wb401} == expected
    else:
        assert len(wb401) == 1 and wb401[0].id not in {OLD_NESTED, OLD_TOP}  # the `+` line survives
