"""Unit tests for the mechanical lesson checks.

A few of these are regression tests for real bugs found while hardening this
tool against actual lessons (see PR history): code fences hiding literal
`:::`/`#` text from the checks, a blank `episodes:` config field being a
valid "include everything" signal rather than an omission, and Workbench's
episodes/fig/-relative image path convention.
"""

from __future__ import annotations

from pathlib import Path

from checker.lesson_check import (
    _check_boilerplate,
    _check_contractions,
    _check_divs,
    _check_front_matter,
    _check_headings,
    _check_links,
    _check_objective_verbs,
    _check_placeholder_bullets,
    _looks_misplaced,
    _unlisted_episode_files,
    check_config,
    check_episode,
    check_support_files,
    read_lesson_metadata,
    resolve_glossary_path,
    run_checks,
)
from checker.report import Finding

VALID_EPISODE_BODY = """\
:::::: questions
- What is this?
::::::

:::::: objectives
- Learn things.
::::::

## A heading

Some content.

:::::: keypoints
- A point.
::::::
"""


def make_lesson(tmp_path: Path, config_extra: str = "", episodes: dict[str, str] | None = None) -> Path:
    lesson_dir = tmp_path / "lesson"
    (lesson_dir / "episodes").mkdir(parents=True)
    (lesson_dir / "config.yaml").write_text(
        "title: 'Real Title'\n"
        "contact: 'team@example.org'\n"
        "created: 2026-01-01\n"
        "source: 'https://example.org'\n"
        f"{config_extra}\n"
    )
    for name, body in (episodes or {}).items():
        (lesson_dir / "episodes" / name).write_text(body)
    return lesson_dir


def episode_text(front_matter: str = "title: 'Ep'\nteaching: 15\nexercises: 15", body: str = VALID_EPISODE_BODY) -> str:
    return f"---\n{front_matter}\n---\n{body}"


# -- config.yaml -------------------------------------------------------------


def test_config_placeholder_values_are_errors(tmp_path):
    lesson_dir = tmp_path / "lesson"
    (lesson_dir / "episodes").mkdir(parents=True)
    (lesson_dir / "config.yaml").write_text(
        "title: 'Lesson Title'\ncontact: 'team@carpentries.org'\ncreated: 2026-01-01\n"
    )
    findings = check_config(lesson_dir)
    messages = [f.message for f in findings]
    assert any("title" in m and "placeholder" in m for m in messages)
    assert any("contact" in m and "placeholder" in m for m in messages)


def test_config_missing_episode_on_disk_is_error(tmp_path):
    lesson_dir = make_lesson(tmp_path, config_extra="episodes:\n- ghost.md\n")
    findings = check_config(lesson_dir)
    assert any(f.severity == "error" and "ghost.md" in f.message for f in findings)


def test_config_blank_episodes_field_does_not_warn_about_unlisted_files(tmp_path):
    # A blank `episodes:` is documented Workbench behavior: sandpaper includes
    # every file automatically. This must not produce "unlisted" warnings.
    lesson_dir = make_lesson(
        tmp_path, config_extra="episodes:\n", episodes={"01-intro.md": episode_text()}
    )
    findings = check_config(lesson_dir)
    assert not any("not listed" in f.message for f in findings)


def test_config_explicit_list_missing_a_file_warns_unlisted(tmp_path):
    lesson_dir = make_lesson(
        tmp_path,
        config_extra="episodes:\n- 01-intro.md\n",
        episodes={"01-intro.md": episode_text(), "02-extra.md": episode_text()},
    )
    findings = check_config(lesson_dir)
    assert any("02-extra.md" in f.message and "not listed" in f.message for f in findings)


# -- front matter --------------------------------------------------------


def test_front_matter_missing_required_fields():
    findings = _check_front_matter({"title": "Ep"}, "ep.md")
    categories = {f.message for f in findings}
    assert any("teaching" in m for m in categories)
    assert any("exercises" in m for m in categories)


def test_front_matter_episode_length_outside_range_is_info():
    findings = _check_front_matter({"title": "Ep", "teaching": 5, "exercises": 5}, "ep.md")
    assert any(f.severity == "info" and "outside the 20-60 min" in f.message for f in findings)


def test_front_matter_episode_length_in_range_is_silent():
    findings = _check_front_matter({"title": "Ep", "teaching": 15, "exercises": 15}, "ep.md")
    assert not any("20-60 min" in f.message for f in findings)


# -- glossary -----------------------------------------------------------


def test_config_missing_glossary_is_info(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    findings = check_config(lesson_dir)
    assert any(f.severity == "info" and "glossary" in f.message for f in findings)


def test_config_present_glossary_is_silent(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "reference.md").write_text("# Reference\n")
    findings = check_config(lesson_dir)
    assert not any("glossary" in f.message for f in findings)


# -- divs -----------------------------------------------------------------


def test_divs_valid_body_has_no_findings():
    assert _check_divs(VALID_EPISODE_BODY, "ep.md") == []


def test_divs_caution_is_a_known_type():
    # Real bug found auditing research-software-citable-discoverable: caution
    # is a documented Workbench div type (raises awareness of a potential
    # issue/problem, per the Component Guide), was missing from
    # KNOWN_DIV_TYPES and got flagged as unrecognized 5 times across 3 real
    # episodes.
    body = VALID_EPISODE_BODY + "\n:::: caution\nWatch out for this.\n::::\n"
    findings = _check_divs(body, "ep.md")
    assert not any("unrecognized div type" in f.message for f in findings)


def test_divs_genuinely_unknown_type_is_still_flagged():
    body = VALID_EPISODE_BODY + "\n:::: not-a-real-type\ntext\n::::\n"
    findings = _check_divs(body, "ep.md")
    assert any("unrecognized div type" in f.message for f in findings)


def test_divs_unclosed_is_error():
    body = ":::: challenge\nNo closing fence.\n"
    findings = _check_divs(body, "ep.md")
    assert any("never closed" in f.message for f in findings)


def test_divs_unclosed_has_structured_line_number():
    # The line field must be populated, not just embedded in the message --
    # renderers need it as data to build clickable links.
    body = ":::: challenge\nNo closing fence.\n"
    findings = _check_divs(body, "ep.md")
    matches = [f for f in findings if "never closed" in f.message]
    assert matches and matches[0].line == 1


def test_divs_extraneous_close_is_error():
    body = "Some text.\n:::\n"
    findings = _check_divs(body, "ep.md")
    assert any("extraneous closing" in f.message for f in findings)


def test_divs_missing_required_blocks():
    findings = _check_divs("Just prose, no divs at all.\n", "ep.md")
    messages = [f.message for f in findings]
    assert any("questions" in m for m in messages)
    assert any("objectives" in m for m in messages)
    assert any("keypoints" in m for m in messages)


def test_divs_inside_code_fence_are_ignored():
    # A lesson teaching Workbench/Markdown syntax will show ::: literally in a
    # code block -- that must not be parsed as a real div.
    body = VALID_EPISODE_BODY + "\n```\n::: challenge\nexample text\n:::\n```\n"
    findings = _check_divs(body, "ep.md")
    assert findings == []


# -- headings ---------------------------------------------------------------


def test_headings_level_one_is_error():
    findings = _check_headings("# Top level\n\n## Ok\n", "ep.md")
    assert any(f.severity == "error" for f in findings)


def test_headings_level_one_has_structured_line_number():
    findings = _check_headings("# Top level\n\n## Ok\n", "ep.md")
    matches = [f for f in findings if f.severity == "error"]
    assert matches and matches[0].line == 1


def test_headings_first_not_level_two_is_warning():
    findings = _check_headings("### Starts too deep\n", "ep.md")
    assert any("expected level 2" in f.message for f in findings)


def test_headings_duplicate_is_warning():
    findings = _check_headings("## Same\n\ntext\n\n## Same\n", "ep.md")
    assert any("duplicates" in f.message for f in findings)


def test_headings_inside_code_fence_are_ignored():
    # A shell lesson's example code full of `# comment` lines must not be
    # parsed as episode headings.
    body = "## Real heading\n\n```bash\n# this is a shell comment, not a heading\n```\n"
    findings = _check_headings(body, "ep.md")
    assert findings == []


# -- links --------------------------------------------------------------


def test_links_image_missing_alt_and_missing_file(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    body = "![](fig/does-not-exist.png)\n"
    findings = _check_links(body, lesson_dir, "episodes/ep.md")
    messages = [f.message for f in findings]
    assert any("no alt text" in m for m in messages)
    assert any("missing file" in m for m in messages)
    assert all(f.line == 1 for f in findings)


def test_links_episode_relative_fig_image_resolves(tmp_path):
    # Workbench images live under episodes/fig/ and are referenced relative
    # to the episode, not the lesson root.
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "episodes" / "fig").mkdir()
    (lesson_dir / "episodes" / "fig" / "diagram.png").write_bytes(b"")
    body = "![a diagram](fig/diagram.png)\n"
    findings = _check_links(body, lesson_dir, "episodes/ep.md")
    assert not any("missing file" in f.message for f in findings)


def test_links_html_target_resolves_against_md_source(tmp_path):
    # Sandpaper renders every .md source to a same-named .html page, so a
    # link to reference.html should resolve against reference.md.
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "reference.md").write_text("# Reference\n")
    body = "See the [reference](reference.html) page.\n"
    findings = _check_links(body, lesson_dir, "episodes/ep.md")
    assert not any("may be broken" in f.message for f in findings)


def test_links_inside_code_fence_are_ignored(tmp_path):
    # Real bug: a lesson showing learners example markdown to paste into
    # their own README (e.g. a LICENSE badge link) had that illustrative
    # link checked as if it were live prose, and flagged as broken.
    lesson_dir = make_lesson(tmp_path)
    body = "Add this to your README:\n```markdown\nSee the [LICENSE](LICENSE) file.\n```\n"
    findings = _check_links(body, lesson_dir, "episodes/ep.md")
    assert findings == []


def test_links_line_offset_is_applied(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    body = "para\n\n![](fig/missing.png)\n"
    findings = _check_links(body, lesson_dir, "episodes/ep.md", line_offset=5)
    assert any("line 8" in f.message for f in findings)  # body line 3 + offset 5


def test_links_generic_link_text_is_warning(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    body = "Read more [here](https://example.org/docs).\n"
    findings = _check_links(body, lesson_dir, "episodes/ep.md")
    assert any("generic link text" in f.message for f in findings)


# -- objectives (CLDT / Carpentries Lab checklist) ---------------------------


def test_objectives_vague_opener_is_warning():
    body = """\
:::::: objectives
- Understand how version control works.
::::::
"""
    findings, count = _check_objective_verbs(body, "ep.md")
    assert any("hard to assess" in f.message for f in findings)
    assert count == 1


def test_objectives_vague_opener_word_boundary_no_false_positive():
    # "Knowledgeable"/"Understanding-based" must not match "know"/"understand"
    # as a bare prefix -- this was a real bug (no \b in the original regex).
    body = """\
:::::: objectives
- Knowledgeable use of Git for version control.
- Understanding-based approach to Git basics.
::::::
"""
    findings, count = _check_objective_verbs(body, "ep.md")
    assert findings == []
    assert count == 2


def test_objectives_action_verb_has_no_finding():
    body = """\
:::::: objectives
- Explain how version control works.
::::::
"""
    findings, count = _check_objective_verbs(body, "ep.md")
    assert findings == []
    assert count == 1


def test_objectives_verb_check_ignores_other_divs():
    # "Understand" inside a callout, not objectives, shouldn't be flagged --
    # the check only looks at bullets inside the objectives block.
    body = """\
:::::: callout
- Understand this is just an aside.
::::::
"""
    findings, count = _check_objective_verbs(body, "ep.md")
    assert findings == []
    assert count == 0


def test_objectives_more_than_four_is_info():
    body = """\
:::::: objectives
- Explain A.
- Explain B.
- Explain C.
- Explain D.
- Explain E.
::::::
"""
    findings, count = _check_objective_verbs(body, "ep.md")
    assert count == 5
    assert any("5 objectives" in f.message for f in findings)


# -- style (contractions) ----------------------------------------------------


def test_contractions_below_threshold_is_silent():
    body = "This isn't flagged since it's only one line.\n"
    assert _check_contractions(body, "ep.md") == []


def test_contractions_above_threshold_is_info():
    body = "\n".join([f"Line {i}: don't do that, it's not right." for i in range(5)])
    findings = _check_contractions(body, "ep.md")
    assert findings and findings[0].severity == "info"


def test_contractions_possessives_are_not_counted():
    # Real bug: \w+'s matched possessives ("learner's", "Git's") as
    # contractions. Repeat past the count threshold to isolate the fix.
    body = "\n".join(
        [f"Check the learner's laptop and Git's staging area, line {i}." for i in range(5)]
    )
    assert _check_contractions(body, "ep.md") == []


def test_contractions_curly_apostrophe_is_counted():
    body = "\n".join([f"Line {i}: don’t do that, it’s not right." for i in range(5)])
    findings = _check_contractions(body, "ep.md")
    assert findings and findings[0].severity == "info"


# -- objectives assessed by exercises (Carpentries Lab checklist) -----------


def test_objectives_with_zero_exercises_is_warning(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    path = lesson_dir / "episodes" / "01-intro.md"
    path.write_text(
        episode_text(
            front_matter="title: 'Ep'\nteaching: 15\nexercises: 0",
            body=VALID_EPISODE_BODY,
        )
    )
    findings = check_episode(path, lesson_dir)
    assert any("exercises: 0" in f.message for f in findings)


def test_objectives_with_nonzero_exercises_is_silent(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    path = lesson_dir / "episodes" / "01-intro.md"
    path.write_text(episode_text())  # default fixture has exercises: 15
    findings = check_episode(path, lesson_dir)
    assert not any("exercises: 0" in f.message for f in findings)


# -- glossary path (Workbench convention) ------------------------------------


def test_config_glossary_at_learners_path_is_recognized(tmp_path):
    # Real bug: the check only looked at lesson_dir/reference.md, but
    # Workbench's actual convention (confirmed against workbench-template-md
    # and a real published lesson) is learners/reference.md.
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "learners").mkdir()
    (lesson_dir / "learners" / "reference.md").write_text("# Reference\n")
    findings = check_config(lesson_dir)
    assert not any("glossary" in f.message for f in findings)


# -- boilerplate / placeholder detection (CLDT: catch unedited scaffold) ----
# Real bugs found auditing a live CLDT cohort's lesson repo the week after
# training: episodes left at the scaffold's own title/body, and required
# blocks present but still holding the scaffold's placeholder bullets.


def test_boilerplate_scaffold_title_is_error():
    findings = _check_boilerplate({"title": "Using Markdown"}, "Some real body.", "ep.md")
    assert any(f.severity == "error" and "scaffold default" in f.message for f in findings)


def test_boilerplate_real_title_is_silent():
    findings = _check_boilerplate({"title": "Why License?"}, "Some real body.", "ep.md")
    assert findings == []


def test_boilerplate_scaffold_body_fingerprint_is_warning():
    body = 'Some intro.\n\n```r\npaste("This", "new", "lesson", "looks", "good")\n```\n'
    findings = _check_boilerplate({"title": "Real Title"}, body, "ep.md")
    assert any(f.severity == "warning" and "scaffold example text" in f.message for f in findings)


def test_boilerplate_body_fingerprint_reports_real_line_number():
    body = 'Line 1.\nLine 2.\nLine 3.\nBuoyant Barnacle repository.\n'
    findings = _check_boilerplate({"title": "Real Title"}, body, "ep.md")
    assert any("line 4" in f.message for f in findings)


def test_boilerplate_body_fingerprint_line_offset_is_applied():
    body = 'Buoyant Barnacle repository.\n'
    findings = _check_boilerplate({"title": "Real Title"}, body, "ep.md", line_offset=10)
    assert any("line 11" in f.message for f in findings)


def test_boilerplate_real_body_is_silent():
    findings = _check_boilerplate(
        {"title": "Real Title"}, "This episode explains real licensing content.", "ep.md"
    )
    assert findings == []


def test_placeholder_bullets_keypoint_variants_are_flagged():
    body = """\
:::::: keypoints
- keypoint1
- keypoint 2
::::::
"""
    findings = _check_placeholder_bullets(body, "ep.md")
    assert len(findings) == 2
    assert all(f.severity == "error" for f in findings)
    assert sorted(f.line for f in findings) == [2, 3]


def test_placeholder_bullets_real_keypoint_is_silent():
    body = """\
:::::: keypoints
- A license does not give away ownership of your code.
::::::
"""
    assert _check_placeholder_bullets(body, "ep.md") == []


def test_placeholder_bullets_only_checked_inside_required_blocks():
    # A challenge/solution bullet that happens to read "objective 1" (e.g. a
    # multiple-choice answer option) must not be flagged -- only the actual
    # questions/objectives/keypoints blocks are in scope.
    body = """\
:::::: challenge
- objective 1
::::::
"""
    assert _check_placeholder_bullets(body, "ep.md") == []


def test_placeholder_bullets_grammar_variants_are_flagged():
    # From external validation: TBD/TODO/FIXME, N/A/none, punctuation-only,
    # and bracketed instructions are all real placeholder shapes seen in
    # practice, not just the exact scaffold strings.
    body = """\
:::::: keypoints
- TODO
- N/A
- ...
- [add keypoint]
::::::
"""
    findings = _check_placeholder_bullets(body, "ep.md")
    assert len(findings) == 4


def test_placeholder_bullets_markdown_emphasis_is_normalized():
    # "**Keypoint 1**" must still match "keypoint 1" -- wrapping emphasis
    # markers shouldn't let placeholder text evade detection.
    body = """\
:::::: keypoints
- **Keypoint 1**
::::::
"""
    findings = _check_placeholder_bullets(body, "ep.md")
    assert len(findings) == 1


def test_placeholder_bullets_none_as_whole_sentence_is_not_flagged():
    # "None" alone is a placeholder; "None of these licenses..." is a real
    # sentence and must not be flagged just because it starts with "none".
    body = """\
:::::: keypoints
- None of these licenses require attribution.
::::::
"""
    assert _check_placeholder_bullets(body, "ep.md") == []


def test_placeholder_bullets_plus_and_numbered_markers_are_recognized():
    body = """\
:::::: keypoints
+ TODO
1. FIXME
::::::
"""
    findings = _check_placeholder_bullets(body, "ep.md")
    assert len(findings) == 2


# -- extension-less episode files (CLDT: catch invisible-to-the-build files) -


def test_config_extension_less_episode_file_is_warning(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    # No .md/.Rmd extension -- Sandpaper's glob (and this checker's own
    # elsewhere) silently excludes it, so nothing else would ever flag it.
    (lesson_dir / "episodes" / "episode-2-permissive-vs-copyleft").write_text(episode_text())
    findings = check_config(lesson_dir)
    assert any(
        f.severity == "warning" and "no .md/.Rmd extension" in f.message for f in findings
    )


def test_config_fig_and_data_dirs_are_not_flagged(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "episodes" / "fig").mkdir()
    (lesson_dir / "episodes" / "fig" / "diagram.png").write_bytes(b"")
    findings = check_config(lesson_dir)
    assert not any("no .md/.Rmd extension" in f.message for f in findings)


# -- glossary path resolution (CLDT: one resolver, three consumers agree) ---


def test_resolve_glossary_path_prefers_modern_path(tmp_path):
    (tmp_path / "learners").mkdir()
    (tmp_path / "learners" / "reference.md").write_text("# Reference\n")
    (tmp_path / "reference.md").write_text("# Legacy\n")
    assert resolve_glossary_path(tmp_path) == "learners/reference.md"


def test_resolve_glossary_path_falls_back_to_legacy(tmp_path):
    (tmp_path / "reference.md").write_text("# Legacy\n")
    assert resolve_glossary_path(tmp_path) == "reference.md"


def test_resolve_glossary_path_none_when_neither_exists(tmp_path):
    assert resolve_glossary_path(tmp_path) is None


# -- support files: learners/, instructors/, profiles/ content --------------
# check_episode() never sees these (they aren't episodes), and check_config()
# only checked for existence, not content -- real repo had all four of these
# still at the sandpaper::create_lesson() default.


def test_support_files_placeholder_reference_is_warning(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "learners").mkdir()
    (lesson_dir / "learners" / "reference.md").write_text(
        "---\ntitle: 'Reference'\n---\n\n## Glossary\n\nThis is a placeholder file. Please add content here.\n"
    )
    findings = check_support_files(lesson_dir)
    assert any("learners/reference.md" in f.location for f in findings)


def test_support_files_real_reference_is_silent(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "learners").mkdir()
    (lesson_dir / "learners" / "reference.md").write_text(
        "---\ntitle: 'Reference'\n---\n\n## Glossary\n\nPermissive license\n: Allows reuse with minimal restriction.\n"
    )
    assert check_support_files(lesson_dir) == []


def test_support_files_legacy_root_glossary_placeholder_is_flagged(tmp_path):
    # Real bug fixed via the shared resolve_glossary_path(): check_support_files
    # used to only ever look at learners/reference.md, so a legacy-layout
    # lesson's still-placeholder root-level reference.md went unchecked.
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "reference.md").write_text(
        "# Reference\n\nThis is a placeholder file. Please add content here.\n"
    )
    findings = check_support_files(lesson_dir)
    assert any(f.location == "reference.md" for f in findings)


def test_support_files_legacy_root_glossary_real_content_is_silent(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "reference.md").write_text(
        "# Reference\n\nCopyleft\n: Requires derivative works stay open.\n"
    )
    assert check_support_files(lesson_dir) == []


def test_support_files_missing_file_is_not_flagged(tmp_path):
    # Absence is check_config's job (the existing glossary-file-exists check);
    # check_support_files only judges content of files that are present.
    lesson_dir = make_lesson(tmp_path)
    assert check_support_files(lesson_dir) == []


def test_support_files_all_four_paths_checked(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    (lesson_dir / "learners").mkdir()
    (lesson_dir / "instructors").mkdir()
    (lesson_dir / "profiles").mkdir()
    (lesson_dir / "learners" / "setup.md").write_text(
        "---\ntitle: Setup\n---\n\nFIXME: Setup instructions live in this document.\n"
    )
    (lesson_dir / "instructors" / "instructor-notes.md").write_text(
        "---\ntitle: 'Instructor Notes'\n---\n\nThis is a placeholder file. Please add content here.\n"
    )
    (lesson_dir / "profiles" / "learner-profiles.md").write_text(
        "---\ntitle: FIXME\n---\n\nThis is a placeholder file. Please add content here.\n"
    )
    findings = check_support_files(lesson_dir)
    locations = {f.location for f in findings}
    assert locations == {
        "learners/setup.md",
        "instructors/instructor-notes.md",
        "profiles/learner-profiles.md",
    }


# -- front-matter typo hint (CLDT: exercise: vs exercises:) -----------------


def test_front_matter_exercise_typo_gets_specific_hint():
    findings = _check_front_matter({"title": "Ep", "teaching": 15, "exercise": 10}, "ep.md")
    missing = [f for f in findings if "exercises" in f.message]
    assert missing and missing[0].hint and "exercise:" in missing[0].hint


def test_front_matter_generic_missing_field_has_generic_hint():
    findings = _check_front_matter({"teaching": 15, "exercises": 10}, "ep.md")
    missing = [f for f in findings if "title" in f.message]
    assert missing and missing[0].hint == "Add `title:` to the YAML front matter."


# -- end to end -------------------------------------------------------------


def test_check_episode_end_to_end_valid_episode_has_no_findings(tmp_path):
    lesson_dir = make_lesson(tmp_path)
    path = lesson_dir / "episodes" / "01-intro.md"
    path.write_text(episode_text())
    assert check_episode(path, lesson_dir) == []


def test_check_episode_reports_real_file_line_numbers_not_body_relative(tmp_path):
    # Real bug: every check operated on `body` (text after the front-matter
    # strip) but reported line numbers as if body started at line 1, so
    # every finding's line number was off by the front matter's length.
    lesson_dir = make_lesson(tmp_path)
    path = lesson_dir / "episodes" / "01-intro.md"
    # A level-1 heading is always an error, regardless of position -- unlike
    # a bare H3, which is only flagged if it's the *first* heading.
    full_text = episode_text(body=VALID_EPISODE_BODY + "\n# Stray H1\n")
    path.write_text(full_text)
    real_line = full_text.count("\n", 0, full_text.index("# Stray H1")) + 1

    findings = check_episode(path, lesson_dir)
    heading_findings = [f for f in findings if "Stray H1" in f.message]
    assert heading_findings, "expected a level-1 heading finding"
    assert f"line {real_line}" in heading_findings[0].message


# -- read_lesson_metadata ---------------------------------------------------


def test_read_lesson_metadata_full_config_and_citation(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "title: 'Python Intro'\n"
        "carpentry: 'lc'\n"
        "life_cycle: 'beta'\n"
        "license: 'CC-BY 4.0'\n"
        "source: 'https://github.com/org/repo'\n"
        "contact: 'team@example.org'\n"
        "created: '2020-01-01'\n"
    )
    (tmp_path / "CITATION.cff").write_text(
        "authors:\n"
        "  - family-names: Hennesy\n"
        "    given-names: Cody\n"
        "  - family-names: Org\n"
        "    given-names: An\n"
    )
    metadata = read_lesson_metadata(tmp_path)
    assert metadata.title == "Python Intro"
    assert metadata.carpentry == "Library Carpentry"
    assert metadata.life_cycle == "beta"
    assert metadata.license == "CC-BY 4.0"
    assert metadata.source == "https://github.com/org/repo"
    assert metadata.contact == "team@example.org"
    assert metadata.created == "2020-01-01"
    assert metadata.authors == ["Cody Hennesy", "An Org"]


def test_read_lesson_metadata_no_config_or_citation_is_empty(tmp_path):
    metadata = read_lesson_metadata(tmp_path)
    assert metadata.title is None
    assert metadata.authors == []
    assert metadata.has_content() is False


def test_read_lesson_metadata_missing_citation_leaves_authors_empty(tmp_path):
    (tmp_path / "config.yaml").write_text("title: 'Some Lesson'\ncarpentry: 'dc'\n")
    metadata = read_lesson_metadata(tmp_path)
    assert metadata.title == "Some Lesson"
    assert metadata.carpentry == "Data Carpentry"
    assert metadata.authors == []
    assert metadata.has_content() is True


def test_read_lesson_metadata_citation_entity_author_uses_name_field(tmp_path):
    # CFF allows an "entity" author (an organization) via `name` instead of
    # the usual given-names/family-names pair.
    (tmp_path / "config.yaml").write_text("title: 'Some Lesson'\n")
    (tmp_path / "CITATION.cff").write_text("authors:\n  - name: The Carpentries\n")
    metadata = read_lesson_metadata(tmp_path)
    assert metadata.authors == ["The Carpentries"]


def test_read_lesson_metadata_unknown_carpentry_code_passes_through(tmp_path):
    (tmp_path / "config.yaml").write_text("carpentry: 'xyz'\n")
    metadata = read_lesson_metadata(tmp_path)
    assert metadata.carpentry == "xyz"


def test_read_lesson_metadata_malformed_yaml_is_empty_not_a_crash(tmp_path):
    (tmp_path / "config.yaml").write_text("title: [unterminated\n")
    (tmp_path / "CITATION.cff").write_text("authors: [unterminated\n")
    metadata = read_lesson_metadata(tmp_path)
    assert metadata.title is None
    assert metadata.authors == []


# -- misplaced-episode-file detection (unlisted + zero required divs) -------
#
# Real bug: a glossary/resources file dropped in episodes/ instead of
# learners/reference.md, unlisted in config.yaml, structurally nothing like
# an episode -- previously only produced 5 generic "episode is broken"
# errors with no hint that the actual problem was "this file doesn't belong
# here." Filename-agnostic on purpose: the signal is "unlisted + zero of
# the three required blocks," not a hardcoded list of suspicious names.


def test_unlisted_episode_files_returns_files_missing_from_explicit_list(tmp_path):
    lesson_dir = make_lesson(
        tmp_path,
        config_extra="episodes:\n- 01-intro.md\n",
        episodes={"01-intro.md": episode_text(), "glossary.md": "# Glossary\n\nSome terms.\n"},
    )
    assert _unlisted_episode_files(lesson_dir) == ["glossary.md"]


def test_unlisted_episode_files_empty_when_episodes_field_blank(tmp_path):
    # A blank `episodes:` is documented Workbench behavior: sandpaper
    # includes everything automatically, so nothing counts as "unlisted".
    lesson_dir = make_lesson(
        tmp_path, config_extra="episodes:\n", episodes={"glossary.md": "# Glossary\n"}
    )
    assert _unlisted_episode_files(lesson_dir) == []


def test_looks_misplaced_true_when_all_three_required_blocks_missing():
    findings = [
        Finding("error", "divs", "missing required `questions` block", code="WB204"),
        Finding("error", "divs", "missing required `objectives` block", code="WB204"),
        Finding("error", "divs", "missing required `keypoints` block", code="WB204"),
    ]
    assert _looks_misplaced(findings) is True


def test_looks_misplaced_false_when_one_required_block_present():
    findings = [
        Finding("error", "divs", "missing required `questions` block", code="WB204"),
        Finding("error", "divs", "missing required `objectives` block", code="WB204"),
    ]
    assert _looks_misplaced(findings) is False


def test_run_checks_flags_unlisted_zero_structure_file_as_misplaced(tmp_path):
    lesson_dir = make_lesson(
        tmp_path,
        config_extra="episodes:\n- 01-intro.md\n",
        episodes={
            "01-intro.md": episode_text(),
            "glossary.md": "# Glossary\n\nAlgorithm\n: A sequence of steps.\n",
        },
    )
    findings = run_checks(lesson_dir)
    matches = [f for f in findings if "looks like reference content" in f.message]
    assert len(matches) == 1
    assert matches[0].location == "episodes/glossary.md"
    assert matches[0].severity == "warning"


def test_run_checks_does_not_flag_listed_zero_structure_file(tmp_path):
    # If the author DID list it in config.yaml, that's a declared intent
    # for it to be a real episode -- just very unwritten, not misplaced.
    lesson_dir = make_lesson(
        tmp_path,
        config_extra="episodes:\n- 01-intro.md\n- draft.md\n",
        episodes={"01-intro.md": episode_text(), "draft.md": "# Draft\n\nNothing yet.\n"},
    )
    findings = run_checks(lesson_dir)
    assert not any("looks like reference content" in f.message for f in findings)


def test_run_checks_does_not_flag_unlisted_file_with_partial_structure(tmp_path):
    # Some required blocks present (even if incomplete) means this is a
    # real, if broken, episode attempt -- not misplaced reference content.
    lesson_dir = make_lesson(
        tmp_path,
        config_extra="episodes:\n- 01-intro.md\n",
        episodes={
            "01-intro.md": episode_text(),
            "in-progress.md": "---\ntitle: 'WIP'\nteaching: 10\nexercises: 10\n---\n"
            ":::: keypoints\n- something\n::::\n",
        },
    )
    findings = run_checks(lesson_dir)
    assert not any("looks like reference content" in f.message for f in findings)
