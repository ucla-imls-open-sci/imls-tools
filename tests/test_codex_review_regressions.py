"""Regressions from the 2026-09-29 external (Codex) review; see
design/2026-09-29-codex-review-wbcheck.md. Each test is the review's
reproduction, asserting the corrected behavior."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from typer.testing import CliRunner

from checker.app import app
from checker.fix import AUTOFIX_CODES, apply_fix, changed_files, plan_autofixes
from checker.lesson_check import _check_headings, _code_fence_mask, read_lesson_metadata, run_checks

runner = CliRunner()
BLOCKS = ":::: questions\n- Q?\n::::\n\n:::: objectives\n- Explain it.\n::::\n\n:::: keypoints\n- K.\n::::\n"


def lesson(tmp_path: Path, body: str = "## A\n", config_tail: str = "episodes:\n- 01.md\n",
           objective: str = "Explain it.") -> Path:
    d = tmp_path / "l"
    (d / "episodes").mkdir(parents=True)
    (d / "learners").mkdir()
    (d / "learners" / "reference.md").write_text("g\n")
    (d / "config.yaml").write_text(
        "title: 'R'\ncontact: 'a@b.org'\ncreated: 2026-01-01\nsource: 'https://x'\nlife_cycle: alpha\n" + config_tail
    )
    (d / "episodes" / "01.md").write_text(
        f"---\ntitle: 'E'\nteaching: 20\nexercises: 10\n---\n{BLOCKS.replace('Explain it.', objective)}\n{body}"
    )
    return d


def _apply_all(d: Path, code: str) -> None:
    for fx in plan_autofixes(run_checks(d), d, AUTOFIX_CODES):
        if fx.finding.code == code:
            apply_fix(fx)


# 1. WB401 keeps everything after the opener, even with quotes/emphasis
def test_wb401_fix_keeps_quoted_and_emphasized_text(tmp_path):
    d = lesson(tmp_path, objective='Understand "git status" output and `--short` **flags**.')
    _apply_all(d, "WB401")
    assert '- Explain "git status" output and `--short` **flags**.' in (d / "episodes" / "01.md").read_text()


# 2. WB009 keeps config.yaml valid
def _unlisted(d: Path, name: str) -> None:
    (d / "episodes" / name).write_text((d / "episodes" / "01.md").read_text())


def test_wb009_fix_without_trailing_newline(tmp_path):
    d = lesson(tmp_path, config_tail="episodes:\n- 01.md")
    _unlisted(d, "02.md")
    _apply_all(d, "WB009")
    assert yaml.safe_load((d / "config.yaml").read_text())["episodes"] == ["01.md", "02.md"]


def test_wb009_fix_quotes_yaml_special_names(tmp_path):
    d = lesson(tmp_path)
    _unlisted(d, "[draft].md")
    _apply_all(d, "WB009")
    assert yaml.safe_load((d / "config.yaml").read_text())["episodes"] == ["01.md", "[draft].md"]


# 9. the reference-content safeguard survives --code filters and ignores
def test_wb009_filter_does_not_bypass_reference_safeguard(tmp_path):
    d = lesson(tmp_path)
    (d / "episodes" / "glossary.md").write_text("# Terms\n")
    runner.invoke(app, ["fix", str(d), "--suggest", "--code", "WB009"], input="y\ny\n")
    assert "glossary" not in (d / "config.yaml").read_text()
    (d / ".wbcheck.toml").write_text('[ignore]\ncodes = ["WB013"]\n')
    runner.invoke(app, ["fix", str(d), "--suggest"], input="y\ny\ny\n")
    assert "glossary" not in (d / "config.yaml").read_text()


# 4. --changed sees filenames with spaces and non-ASCII
def test_changed_files_with_spaces_and_unicode(tmp_path):
    d = lesson(tmp_path)
    subprocess.run("git init -q && git add . && git -c user.email=a@b -c user.name=a commit -qm i",
                   shell=True, cwd=d, check=True)
    (d / "episodes" / "a b.md").write_text("# H1\n")
    (d / "episodes" / "café.md").write_text("# H1\n")
    assert changed_files(d) == {"episodes/a b.md", "episodes/café.md"}
    result = runner.invoke(app, ["check", str(d), "--changed"])
    assert result.exit_code == 1  # the H1 errors in those files count


# 5. non-mapping YAML is a finding, not a crash
def test_config_yaml_list_is_a_finding_not_a_crash(tmp_path):
    d = lesson(tmp_path)
    (d / "config.yaml").write_text("- x\n")
    result = runner.invoke(app, ["check", str(d)])
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "WB003" in result.output


def test_malformed_citation_and_field_types_do_not_crash(tmp_path):
    d = lesson(tmp_path)
    (d / "CITATION.cff").write_text("- a\n")
    (d / "config.yaml").write_text("title: [1, 2]\ncarpentry: [lc]\nepisodes: 01.md\n")
    read_lesson_metadata(d)
    result = runner.invoke(app, ["check", str(d), "-q"])
    assert result.exception is None or isinstance(result.exception, SystemExit)


# 6a. code fences track character and length
def test_longer_fence_can_contain_shorter_fences():
    body = "````\n```\n# comment, not a heading\n```\n````\n## ok\n"
    assert [f.code for f in _check_headings(body, "e")] == []


def test_shorter_fence_does_not_close_longer_or_other_char():
    assert _code_fence_mask("```\n~~~\n# still code\n```\n# real H1\n") == [True, True, True, True, False]
    # ```` ... ``` (not a close) ... ```` closes: the H1 after it is real
    assert [f.code for f in _check_headings("````\n```\n````\n# H1\n", "e")] == ["WB210"]
    # a longer fence does close a shorter one (CommonMark), so this H1 is in a new block
    assert [f.code for f in _check_headings("```\n````\n```\n# H1\n", "e")] == []


# 6b. Pandoc attribute-syntax divs
def test_attribute_syntax_div_is_an_opening_fence(tmp_path):
    d = lesson(tmp_path)
    ep = d / "episodes" / "01.md"
    ep.write_text(ep.read_text().replace(":::: questions", "::: {#q .questions}").replace("- Q?\n::::", "- Q?\n:::"))
    codes = {f.code for f in run_checks(d)}
    assert not codes & {"WB202", "WB204", "WB201"}


# 6c. link/image syntax inside inline code is literal text
def test_image_syntax_in_inline_code_is_not_checked(tmp_path):
    d = lesson(tmp_path, body="Write `![alt](missing.png)` to add an image.\n")
    assert "WB302" not in {f.code for f in run_checks(d)}
