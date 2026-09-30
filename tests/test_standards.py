"""Detector corrections from the 2026-09-30 standards review
(design/2026-09-30-standards-audit.md, STD-01 to STD-12). Each fix has a
positive fixture (still reported) and exception fixtures (no longer
over-reported), so a regression in either direction shows up."""

from __future__ import annotations

from pathlib import Path

import pytest

from checker.ai_review import INSTRUCTIONS, build_glossary_block
from checker.lesson_check import (
    _check_contractions,
    _check_front_matter,
    _check_headings,
    _check_links,
    _check_objective_verbs,
    check_config,
    check_episode,
    is_minutes,
)
from checker.rules import RULES

BLOCKS = ":::: questions\n- Q?\n::::\n\n:::: objectives\n- Explain it.\n::::\n\n:::: keypoints\n- K.\n::::\n"


def codes(findings) -> list[str]:
    return sorted(f.code for f in findings)


@pytest.fixture
def lesson(tmp_path: Path) -> Path:
    (tmp_path / "episodes" / "fig").mkdir(parents=True)
    (tmp_path / "episodes" / "fig" / "plot.png").write_bytes(b"png")
    return tmp_path


# -- STD-01: image descriptions --------------------------------------------------------


@pytest.mark.parametrize("markup", [
    '![](fig/plot.png){alt="A bar chart showing counts"}',
    "![](fig/plot.png){alt='A bar chart showing counts'}",
    '![](fig/plot.png){alt=""}',  # Workbench's decorative-image marker
    "![](fig/plot.png){.wide alt='A chart'}",
    "![](fig/plot.png){alt='A long description\nthat wraps onto\nthree lines'}",
    "![A caption](fig/plot.png){alt='A chart'}",
    "![A caption](fig/plot.png)",  # caption is Pandoc's fallback alt
    "![](fig/plot.png){alt='a {braced} word'}",
    "`![](fig/plot.png)`",  # inline code is literal text
    '![](fig/plot.png){title="A \\"quoted\\" title" alt="A chart"}',  # alt after another quoted value
], ids=["double", "single", "decorative", "class-first", "multiline", "caption+alt", "caption",
        "brace-in-quotes", "inline-code", "alt-after-title"])
def test_described_or_decorative_images_are_not_wb301(lesson, markup):
    assert "WB301" not in codes(_check_links(markup, lesson, "e.md"))


@pytest.mark.parametrize("markup", [
    "![](fig/plot.png)",
    "![](fig/plot.png){width=50%}",
    '![](fig/plot.png){alt="never closed"',
    "![](fig/plot.png){title=\"Example alt='text'\"}",  # alt-like text inside another value
    '![](fig/plot.png){data-note="see alt=x" .wide}',
    '![](fig/plot.png){title="a \\" alt=x"}',  # escaped quote keeps alt=x inside the title
], ids=["bare", "other-attribute", "unclosed-attributes", "alt-in-title", "alt-in-data", "escaped-quote"])
def test_images_with_no_description_are_still_wb301(lesson, markup):
    findings = [f for f in _check_links(markup, lesson, "e.md") if f.code == "WB301"]
    assert len(findings) == 1
    assert "not that it describes the figure" in findings[0].hint  # presence, not adequacy


def test_missing_image_file_is_still_wb302_with_explicit_alt(lesson):
    assert codes(_check_links('![](fig/none.png){alt="A chart"}', lesson, "e.md")) == ["WB302"]


# -- STD-02 / STD-12: timings ------------------------------------------------------------


def episode(front: str, body: str = "") -> str:
    return f"---\ntitle: 'E'\n{front}\n---\n\n{BLOCKS}\n## Section\n\n{body}"


def write(lesson: Path, text: str) -> Path:
    path = lesson / "episodes" / "01.md"
    path.write_text(text)
    return path


def test_wb403_observes_zero_time_without_denying_assessment(lesson):
    discussion = "::: discussion\nCompare the two choices with your neighbour.\n:::\n"
    path = write(lesson, episode("teaching: 20\nexercises: 0", discussion))
    [finding] = [f for f in check_episode(path, lesson) if f.code == "WB403"]
    assert finding.message.startswith("`exercises` is 0")
    assert "nothing" not in finding.message
    assert finding.line == 4  # points at the `exercises:` field


@pytest.mark.parametrize("value", ["true", "false", ".nan", ".inf", "-5", "'15'"])
def test_invalid_timings_are_wb104_and_skip_dependent_checks(lesson, value):
    path = write(lesson, episode(f"teaching: 20\nexercises: {value}"))
    found = codes(check_episode(path, lesson))
    assert "WB104" in found
    assert "WB403" not in found  # `false` is not "zero exercise time"
    assert "WB105" not in found  # no duration sum from an invalid value


@pytest.mark.parametrize("value", [0, 5, 7.5, 12.0])
def test_zero_and_fractional_minutes_are_valid(value):
    assert is_minutes(value)
    assert not [f for f in _check_front_matter({"title": "t", "teaching": 20, "exercises": value}, "e.md")
                if f.code == "WB104"]


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -1, "10", [10]])
def test_non_minute_values_are_rejected(value):
    assert not is_minutes(value)


def test_negative_minutes_message_names_the_constraint():
    [f] = [f for f in _check_front_matter({"title": "t", "teaching": -5, "exercises": 5}, "e.md")
           if f.code == "WB104"]
    assert "finite, non-negative" in f.message


# -- STD-03: duplicate headings within a hierarchy ------------------------------------------


@pytest.mark.parametrize("body", [
    "## Alpha\n\n### Example\n\n## Beta\n\n### Example\n",
    "## Alpha\n\n### Example\n\n#### Detail\n\n### Other\n\n#### Detail\n",
    "## Alpha\n\n```\n## Alpha\n```\n",  # code fence
], ids=["separate-parents", "separate-grandparents", "code-fence"])
def test_repeats_in_different_hierarchies_are_fine(body):
    assert "WB212" not in codes(_check_headings(body, "e.md"))


@pytest.mark.parametrize("body", [
    "## Alpha\n\n### Example\n\n### Example\n",
    "## Setup\n\n## Setup\n",
    "## Alpha\n\n::: challenge\n\n### Example\n\n:::\n\n::: challenge\n\n### Example\n\n:::\n",
], ids=["siblings", "top-level", "component-headings-same-parent"])
def test_repeated_siblings_are_still_wb212(body):
    assert codes(_check_headings(body, "e.md")).count("WB212") == 1


def test_wb212_rationale_no_longer_claims_anchor_collisions():
    assert "anchor" not in RULES["WB212"].why


# -- STD-07: objective lists -----------------------------------------------------------------


@pytest.mark.parametrize("items", [
    "- Understand a\n- Explain b\n- Explain c",
    "* Understand a\n* Explain b\n* Explain c",
    "+ Understand a\n+ Explain b\n+ Explain c",
    "1. Understand a\n2. Explain b\n3. Explain c",
    "1) Understand a\n2) Explain b\n3) Explain c",
    "- Understand a,\n  which wraps\n- Explain b\n  - a nested note\n  - another\n- Explain c",
], ids=["dash", "star", "plus", "ordered-dot", "ordered-paren", "wrapped-and-nested"])
def test_objective_count_and_vague_opener_ignore_list_style(items):
    findings, count = _check_objective_verbs(f"::: objectives\n{items}\n:::\n", "e.md")
    assert count == 3
    assert codes(findings) == ["WB401"]


def test_nested_bullets_are_not_counted_or_checked():
    body = "::: objectives\n- Explain a\n  - Understand the detail\n  - Know the flag\n:::\n"
    findings, count = _check_objective_verbs(body, "e.md")
    assert count == 1 and findings == []


def test_plus_list_objectives_now_reach_wb402():
    body = "::: objectives\n" + "\n".join(f"+ Explain topic {i}" for i in range(5)) + "\n:::\n"
    findings, count = _check_objective_verbs(body, "e.md")
    assert count == 5 and codes(findings) == ["WB402"]


def test_objectives_in_code_or_other_divs_are_excluded():
    body = "::: callout\n- Understand x\n:::\n\n```\n::: objectives\n- Understand y\n:::\n```\n"
    assert _check_objective_verbs(body, "e.md") == ([], 0)


# -- STD-08: contractions in quoted material --------------------------------------------------


def test_blockquoted_data_values_do_not_trigger_wb404():
    body = "## Data\n\n> don't\n> don't\n> won't\n> can't\n> isn't\n\nThe column holds survey answers.\n"
    assert _check_contractions(body, "e.md") == []


def test_equivalent_author_prose_still_triggers_wb404():
    body = "## Data\n\nDon't worry. It's fine. We'll see. You're right. They're here.\n"
    [finding] = _check_contractions(body, "e.md")
    assert "author prose" in finding.message
    assert "wbcheck's own" in finding.hint  # the threshold is local, and says so


# -- STD-05: glossary alternatives and drafts ----------------------------------------------------


def test_wb010_says_local_file_and_accepts_linked_glossaries(tmp_path):
    (tmp_path / "episodes").mkdir()
    (tmp_path / "config.yaml").write_text("title: T\ncontact: a@b.c\nsource: https://x\ncreated: 2026-01-01\n")
    [finding] = [f for f in check_config(tmp_path) if f.code == "WB010"]
    assert "local glossary" in finding.message
    assert "linked external glossary" in finding.hint
    assert "Add learners/reference.md" not in finding.hint  # no demand for a duplicate


def test_wb009_hint_treats_unlisted_drafts_as_legitimate(tmp_path):
    (tmp_path / "episodes").mkdir()
    for name in ("01.md", "02-draft.md"):
        (tmp_path / "episodes" / name).write_text("x")
    (tmp_path / "config.yaml").write_text("episodes:\n- 01.md\n")
    [finding] = [f for f in check_config(tmp_path) if f.code == "WB009"]
    assert "draft" in finding.hint and "publishes" in finding.hint


def test_ai_glossary_context_does_not_assert_the_lesson_has_none():
    block = build_glossary_block("")
    assert "no glossary written" not in block and "linked external glossary" in block


# -- STD-09 / STD-04 / STD-11 wording -------------------------------------------------------------


def test_wb203_hint_does_not_demand_a_longer_closing_fence(lesson):
    path = write(lesson, episode("teaching: 20\nexercises: 10", "::::: callout\nText.\n"))
    [finding] = [f for f in check_episode(path, lesson) if f.code == "WB203"]
    assert "at least three colons" in finding.hint and "same or more" not in finding.hint


def test_config_rules_cite_the_config_page():
    assert RULES["WB001"].guides[0][1].endswith("editing.html#config-yaml")


def test_wb205_explains_it_compares_totals(lesson):
    body = "::: challenge\nA?\n:::\n\n::: challenge\nB?\n\n::: solution\nb\n:::\n\n:::\n"
    path = write(lesson, episode("teaching: 20\nexercises: 10", body))
    [finding] = [f for f in check_episode(path, lesson) if f.code == "WB205"]
    assert "totals" in finding.hint and "discussion" in finding.hint


def test_ai_rules_are_labelled_as_suggestions():
    for code in ("AI201", "AI202", "AI203", "AI204", "AI205", "AI206", "AI207", "AI208"):
        assert RULES[code].why.startswith("AI suggestion"), code


def test_ai_prompt_states_its_evidence_limits():
    assert "reviewed separately" not in INSTRUCTIONS  # no separate lesson-wide review runs
    assert "Nothing is executed" in INSTRUCTIONS
    assert "not rendered images" in INSTRUCTIONS
    assert "learner profiles" in INSTRUCTIONS
