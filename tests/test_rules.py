"""Tests for the rule registry and finding identity (issue #23).

Rule codes and finding IDs are what issue filing, suppression, and re-run
dedupe key on, so these pin the properties those depend on: every check has
a registered code, codes are well-formed and unique, and a finding's ID
survives edits that only move it around.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from checker.lesson_check import run_checks
from checker.report import Finding, render_json, render_markdown, render_terminal
from checker.rules import RULES

LESSON_CHECK_SRC = Path(__file__).resolve().parent.parent / "checker" / "lesson_check.py"

# Rules with no external guide on purpose: WB012 is a CLI usage error
# (--episode named a missing file), not a lesson-quality rule.
RULES_WITHOUT_GUIDES = {"WB012"}


def _finding_codes_in_source() -> list[str | None]:
    """The `code=` value of every `Finding(...)` call in lesson_check.py."""
    tree = ast.parse(LESSON_CHECK_SRC.read_text())
    codes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding":
            code = next(
                (kw.value.value for kw in node.keywords
                 if kw.arg == "code" and isinstance(kw.value, ast.Constant)),
                None,
            )
            codes.append(code if isinstance(code, str) else None)
    return codes


# -- registry integrity ------------------------------------------------------


def test_rule_codes_are_well_formed():
    for code, rule in RULES.items():
        assert code == rule.code
        assert re.fullmatch(r"WB[0-4]\d\d|AI2\d\d", code), code


def test_rule_names_are_unique_kebab_case():
    names = [rule.name for rule in RULES.values()]
    assert len(names) == len(set(names))
    for name in names:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), name


def test_every_finding_in_lesson_check_has_a_registered_code():
    codes = _finding_codes_in_source()
    assert codes, "found no Finding(...) calls, has lesson_check.py moved?"
    missing = [c for c in codes if c is None]
    assert not missing, f"{len(missing)} Finding(...) call(s) without code="
    unregistered = sorted({c for c in codes if c is not None and c not in RULES})
    assert not unregistered, unregistered


def test_every_registered_rule_is_used_by_exactly_one_check():
    codes = [c for c in _finding_codes_in_source() if c is not None]
    mechanical_rules = sorted(c for c in RULES if c.startswith("WB"))
    assert sorted(codes) == mechanical_rules, "a rule is unused, or two checks share a code"


def test_every_rule_cites_an_https_guide():
    for code, rule in RULES.items():
        if code in RULES_WITHOUT_GUIDES:
            continue
        assert rule.guides, f"{code} has no guide citation"
        for label, url in rule.guides:
            assert label
            assert url.startswith("https://"), (code, url)


# -- finding IDs ------------------------------------------------------------


def test_id_ignores_line_references():
    a = Finding("warning", "headings", "heading `Setup` on line 12 duplicates the one on line 4",
                location="episodes/01.md", code="WB212")
    b = Finding("warning", "headings", "heading `Setup` on line 30 duplicates the one on line 9",
                location="episodes/01.md", code="WB212", line=30)
    assert a.id == b.id


def test_id_ignores_counts_outside_quoted_spans():
    a = Finding("info", "style", "7 contractions found (5.2 per 1,000 words)",
                location="episodes/01.md", code="WB404")
    b = Finding("info", "style", "11 contractions found (8.9 per 1,000 words)",
                location="episodes/01.md", code="WB404")
    assert a.id == b.id


def test_id_keeps_digits_inside_backticks_and_quotes():
    a = Finding("error", "config", "config.yaml lists episode `03-data.md` but it does not exist",
                location="config.yaml", code="WB007")
    b = Finding("error", "config", "config.yaml lists episode `04-data.md` but it does not exist",
                location="config.yaml", code="WB007")
    assert a.id != b.id
    c = Finding("error", "boilerplate", '`keypoints` still has placeholder bullet text: "keypoint1"',
                location="episodes/01.md", code="WB112")
    d = Finding("error", "boilerplate", '`keypoints` still has placeholder bullet text: "keypoint2"',
                location="episodes/01.md", code="WB112")
    assert c.id != d.id


def test_id_differs_by_file_and_code():
    message = "image has no alt text: `fig/a.png`"
    a = Finding("warning", "links", message, location="episodes/01.md", code="WB301")
    assert a.id != Finding("warning", "links", message, location="episodes/02.md", code="WB301").id
    assert a.id != Finding("warning", "links", message, location="episodes/01.md", code="WB302").id


def test_ids_stable_when_lines_are_inserted_above(tmp_path):
    lesson_dir = tmp_path / "lesson"
    (lesson_dir / "episodes").mkdir(parents=True)
    (lesson_dir / "config.yaml").write_text(
        "title: 'Real'\ncontact: 'a@b.org'\ncreated: 2026-01-01\nsource: 'https://x.org'\n"
    )
    body = (
        ":::: questions\n- What?\n::::\n\n:::: objectives\n- Explain it.\n::::\n\n"
        "## Part\n\n## Part\n\n![](fig/missing.png)\n\n:::: keypoints\n- keypoint1\n::::\n"
    )
    episode = lesson_dir / "episodes" / "01.md"
    episode.write_text(f"---\ntitle: 'Ep'\nteaching: 15\nexercises: 15\n---\n{body}")
    before = {(f.code, f.id) for f in run_checks(lesson_dir)}
    episode.write_text(f"---\ntitle: 'Ep'\nteaching: 15\nexercises: 15\n---\nIntro.\n\nMore.\n\n{body}")
    after = {(f.code, f.id) for f in run_checks(lesson_dir)}
    assert {"WB212", "WB301", "WB302", "WB112"} <= {code for code, _ in before}
    assert before == after


# -- rendering ---------------------------------------------------------------


def test_json_findings_carry_code_id_and_guides():
    f = Finding("warning", "links", "image on line 3 has no alt text: `fig/a.png`",
                location="episodes/01.md", line=3, code="WB301")
    payload = json.loads(render_json([f], "Report"))
    out = payload["findings"][0]
    assert out["code"] == "WB301"
    assert out["id"] == f.id
    assert out["source"] == "mechanical"
    assert out["guides"][0]["url"].endswith("reviewer_guide.md#accessibility")


def test_terminal_shows_code_and_rule_specific_guide():
    f = Finding("info", "style", "7 contractions found", location="episodes/01.md", code="WB404")
    text = render_terminal([f], "Report")
    assert "[WB404]" in text
    assert "reviewer_guide.md#accessibility" in text


def test_markdown_shows_code_and_all_rule_guides():
    f = Finding("warning", "links", 'generic link text "here"', location="episodes/01.md", code="WB303")
    text = render_markdown([f], "Report")
    assert "`WB303`" in text
    assert "reviewer_guide.md#accessibility" in text
    assert "lesson-development-training/aio.html#accessibility" in text


def test_codeless_finding_falls_back_to_category_guide():
    f = Finding("warning", "divs", "unrecognized div", location="episodes/01.md")
    assert f.guides[0][1] == "https://carpentries.github.io/sandpaper-docs/component-guide.html"


def test_json_serializes_yaml_date_in_metadata():
    # Regression: an unquoted `created: 2026-01-01` in config.yaml is a
    # datetime.date after yaml.safe_load, and crashed --format json.
    import datetime

    from checker.report import LessonMetadata

    metadata = LessonMetadata(title="T", created=datetime.date(2026, 1, 1))  # type: ignore[arg-type]
    payload = json.loads(render_json([], "Report", metadata=metadata))
    assert payload["lesson"]["created"] == "2026-01-01"


def test_repeated_identical_findings_get_distinct_ids():
    from checker.report import assign_occurrences

    findings = assign_occurrences([
        Finding("warning", "headings", "heading `Exercise:` on line 40 duplicates the one on line 3",
                location="episodes/01.md", line=40, code="WB212"),
        Finding("warning", "headings", "heading `Exercise:` on line 13 duplicates the one on line 3",
                location="episodes/01.md", line=13, code="WB212"),
    ])
    assert findings[0].id != findings[1].id
    # numbered in file order, not list order
    assert findings[1].occurrence == 0 and findings[0].occurrence == 1


def test_run_checks_ids_are_unique(tmp_path):
    lesson_dir = tmp_path / "lesson"
    (lesson_dir / "episodes").mkdir(parents=True)
    (lesson_dir / "config.yaml").write_text("title: 'Real'\ncontact: 'a@b.org'\ncreated: 2026-01-01\n")
    body = "## Exercise\n\n## Exercise\n\n## Exercise\n\n## Exercise\n"
    (lesson_dir / "episodes" / "01.md").write_text(f"---\ntitle: 'Ep'\nteaching: 15\nexercises: 15\n---\n{body}")
    findings = run_checks(lesson_dir)
    assert len([f for f in findings if f.code == "WB212"]) == 3
    assert len({f.id for f in findings}) == len(findings)
