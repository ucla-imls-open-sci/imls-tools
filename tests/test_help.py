"""Rule metadata, offline help, and shared explanations (DES-01/02 in
design/2026-09-30-rule-schema-help-proposal.md)."""

from __future__ import annotations

import ast
import asyncio
import re
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from checker.ai_review import AREA_CODES
from checker.app import app
from checker.fix import SAFE_FIX_CODES, SUGGESTION_CODES, fix_capability
from checker.help import render_markdown, render_text, rule_help, search
from checker.issues import plan_issues
from checker.report import Finding
from checker.report import render_markdown as report_markdown
from checker.results import Results, save
from checker.rules import (
    APPLIES_TO,
    AUTHORITIES,
    DETECTIONS,
    REFERENCES,
    RULES,
    SEVERITIES,
    TOPICS,
)

runner = CliRunner()
LESSON_CHECK_SRC = Path(__file__).resolve().parent.parent / "checker" / "lesson_check.py"


# -- registry validation --------------------------------------------------------------


@pytest.mark.parametrize("code", sorted(RULES))
def test_rule_metadata_is_complete_and_valid(code):
    r = RULES[code]
    assert r.topic in TOPICS and r.authority in AUTHORITIES and r.detection in DETECTIONS
    assert r.default_severity in SEVERITIES
    assert r.applies_to and set(r.applies_to) <= set(APPLIES_TO)
    for field in (r.title, r.checks, r.why, r.response, r.severity_reason):
        assert field.strip(), f"{code}: empty required text"
    assert all(key in REFERENCES for key in r.references), code
    assert all(rel in RULES and rel != code for rel in r.related), code
    if r.detection in ("heuristic", "ai-assisted"):
        assert r.limitations, f"{code}: a proxy or AI rule must say what it can't see"
    if r.authority != "checker-policy":
        assert r.references, f"{code}: an external authority needs a source"


def test_every_reference_is_used_and_well_formed():
    used = {key for r in RULES.values() for key in r.references}
    assert used == set(REFERENCES), set(REFERENCES) ^ used
    for key, ref in REFERENCES.items():
        assert ref.url.startswith("https://"), key
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ref.checked_on), key
        assert ref.supports.strip() and ref.section.strip(), key
        assert ref.revision is None or re.fullmatch(r"[0-9a-f]{40}", ref.revision), key


def _emitted_severities() -> dict[str, set[str]]:
    """code -> severities passed to Finding(...) in lesson_check.py."""
    out: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(LESSON_CHECK_SRC.read_text())):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding":
            code = next(kw.value.value for kw in node.keywords if kw.arg == "code")
            severity = node.args[0]
            assert isinstance(severity, ast.Constant), f"{code}: severity isn't a literal"
            out.setdefault(code, set()).add(severity.value)
    return out


def test_default_severity_matches_what_each_check_emits():
    for code, severities in _emitted_severities().items():
        assert severities == {RULES[code].default_severity}, code


def test_ai_area_codes_and_rules_agree():
    assert set(AREA_CODES.values()) == {c for c in RULES if c.startswith("AI")}


def test_wb012_is_labelled_operational():
    assert RULES["WB012"].topic == "operations" and RULES["WB012"].applies_to == ("invocation",)


def test_fix_capability_comes_from_the_fix_handlers():
    for code in RULES:
        expected = ("conditional-automatic" if code in SAFE_FIX_CODES
                    else "editorial" if code in SUGGESTION_CODES else "none")
        assert fix_capability(code) == expected
        assert rule_help(code).fix == expected


# -- help content -----------------------------------------------------------------------


def test_help_has_every_section_and_plain_urls():
    text = render_text(rule_help("WB403"))
    for heading in ("What it checks", "Why it matters", "What to do", "When keeping it is reasonable",
                    "Limits of this check", "Severity", "Automatic fix", "Sources"):
        assert heading in text
    assert "warning" in text  # the severity word, not only color
    assert "https://carpentries.github.io/lesson-development-training/formative-assessment.html#assessments" in text
    assert "live page, unpinned" in text and "revision d3ee510983b7" in text


def test_search_and_topic_filter():
    assert [r.code for r in search("decorative")] == ["WB301"]
    assert all(r.topic == "accessibility" for r in search(topic="accessibility"))
    with pytest.raises(ValueError):
        search(topic="nonsense")


# -- CLI --------------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["WB403", "wb403", "objectives-not-assessed"])
def test_explain_accepts_codes_and_names(query):
    result = runner.invoke(app, ["explain", query])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("WB403  ")


def test_explain_unknown_code_exits_two_with_a_suggestion():
    result = runner.invoke(app, ["explain", "WB999"])
    assert result.exit_code == 2
    assert "WB009" in result.output and "wbcheck rules" in result.output


def test_rules_lists_and_filters():
    result = runner.invoke(app, ["rules"])
    assert result.exit_code == 0 and len(result.output.splitlines()) == len(RULES)
    result = runner.invoke(app, ["rules", "--topic", "prose"])
    assert {line.split()[0] for line in result.output.splitlines()} == {"WB404", "AI205"}
    assert runner.invoke(app, ["rules", "--topic", "nope"]).exit_code == 2


def test_help_imports_nothing_optional():
    """Rule help works in a core install: no AI SDKs, network clients, or UI
    frameworks get imported."""
    code = (
        "import sys; import checker.help as h; h.render_text(h.rule_help('WB403')); "
        "print(','.join(m for m in ('anthropic', 'ollama', 'textual', 'httpx', 'requests', 'langchain') "
        "if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""


# -- one explanation, every view ------------------------------------------------------------


def _wb403() -> Finding:
    return Finding("warning", "objectives", "`exercises` is 0 in the front matter, and this episode declares "
                   "1 objective(s)", location="episodes/01.md", line=4, hint="Check it.", code="WB403")


def test_markdown_report_appends_each_rule_once():
    findings = [_wb403(), _wb403()]
    findings[1].location = "episodes/02.md"
    text = report_markdown(findings, "Report")
    assert text.count("### WB403: objectives declared but no exercise time") == 1
    assert RULES["WB403"].response in text
    assert "<https://carpentries.github.io/lesson-development-training/formative-assessment.html#assessments>" in text
    assert "warning" in text.split("## Rule explanations")[0]  # severity word next to each finding


def test_issue_body_uses_the_same_explanation():
    results = Results(target="x", lesson_dir=None, findings=[_wb403()])
    [draft] = plan_issues(results)[0]
    assert RULES["WB403"].why in draft.body and RULES["WB403"].response in draft.body
    assert f"Keep in mind: {RULES['WB403'].exceptions[0]}" in draft.body
    assert "<!-- wbcheck:id=" in draft.body


def _tui_detail(tmp_path: Path, finding: Finding) -> str:
    """The TUI detail pane's text for `finding`, rendered by a console of
    our own (not the app's captured output) at a fixed, generous width, with
    whitespace collapsed, so assertions test content rather than wrapping."""
    import io

    from rich.console import Console

    from checker.tui import FindingsApp

    path = tmp_path / "results.json"
    save(Results(target="x", lesson_dir=None, findings=[finding]), path)
    seen = {}

    async def main():
        tui = FindingsApp(Results.from_json(path.read_text()), path)
        async with tui.run_test(size=(160, 50)) as pilot:
            await pilot.pause()
            buffer = io.StringIO()
            Console(file=buffer, width=400, color_system=None).print(tui.query_one("#detail-body").content)
            seen["detail"] = buffer.getvalue()

    asyncio.run(main())
    return " ".join(seen["detail"].split())


def test_tui_detail_shows_the_same_explanation(tmp_path):
    detail = _tui_detail(tmp_path, _wb403())
    assert " ".join(RULES["WB403"].why.split()) in detail
    assert "wbcheck explain WB403" in detail
    # the full source URL is visible text, not only a terminal hyperlink
    assert "https://carpentries.github.io/lesson-development-training/formative-assessment.html#assessments" in detail


def test_tui_detail_shows_the_findings_own_severity(tmp_path):
    ai_info = Finding("info", "ai", "Consider checking the example.", location="episodes/a.md", line=3,
                      code="AI208", quote="2 + 2", source="ai")
    detail = _tui_detail(tmp_path, ai_info)
    assert "info AI208" in detail  # the occurrence's severity, as a word
    assert "default severity warning" in detail  # the rule default, labelled as such
    assert "warning AI208" not in detail


def test_check_output_names_severity_and_points_at_explain(tmp_path):
    (tmp_path / "episodes").mkdir()
    (tmp_path / "config.yaml").write_text("title: T\ncontact: a@b.c\nsource: https://x\ncreated: 2026-01-01\n")
    result = runner.invoke(app, ["check", str(tmp_path)])
    assert "info" in result.output  # WB010's severity word
    assert "wbcheck explain WB010" in result.output


def test_unknown_or_codeless_findings_still_render():
    f = Finding("warning", "custom", "a legacy finding with no code", location="episodes/01.md")
    assert rule_help(None) is None
    assert "a legacy finding" in report_markdown([f], "R")
    assert "## Rule explanations" not in report_markdown([f], "R")


def test_markdown_help_escapes_nothing_it_shouldnt():
    # rule text with backticks and quotes survives as literal markdown
    md = render_markdown(rule_help("WB301"))
    assert '`{alt="..."}`' not in md  # we never rewrite the rule text
    assert 'alt=\\"\\"' not in md and '`{alt=""}`' in md
