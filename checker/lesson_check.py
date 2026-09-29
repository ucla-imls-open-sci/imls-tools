"""Mechanical structure checks for a Carpentries Workbench lesson.

These approximate, locally and in seconds, what sandpaper::validate_lesson()
and pegboard's validate_divs() / validate_headings() / validate_links() check
in CI (see https://carpentries.github.io/sandpaper-docs/episodes.html and
https://carpentries.github.io/pegboard/). They are not a replacement for the
real CI check -- they exist so a lesson author can catch the obvious problems
before pushing and waiting on a PR build.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from checker.report import Finding, LessonMetadata, assign_occurrences

REQUIRED_TOP_DIVS = ("questions", "objectives", "keypoints")

# Non-exhaustive, but covers everything in the Workbench style guide as of 2026.
KNOWN_DIV_TYPES = {
    "questions",
    "objectives",
    "keypoints",
    "challenge",
    "solution",
    "discussion",
    "callout",
    "caution",  # raises awareness of a potential issue/problem, per the Workbench Component Guide
    "testimonial",
    "instructor",
    "spoiler",
    "prereq",
    "checklist",
    "hint",
    "tab",
    "group-tab",
}

# config.yaml's `carpentry:` code -> the full org name, for the report header.
CARPENTRY_NAMES = {
    "lc": "Library Carpentry",
    "dc": "Data Carpentry",
    "swc": "Software Carpentry",
    "cp": "The Carpentries",
    "incubator": "The Carpentries Incubator",
}

CONFIG_PLACEHOLDER_VALUES = {
    "title": "Lesson Title",
    "contact": "team@carpentries.org",
    "source": "https://github.com/carpentries/workbench-template-md",
}

# Exact strings from `sandpaper::create_lesson()`'s default scaffold episode.
# A CLDT cohort under deadline pressure regularly ships these unedited -- they
# read as "done" (all three required blocks are present, front matter is
# valid) but the content is still the template's own worked example, not the
# lesson's. Deterministic and exact-match on purpose: this only fires on the
# literal scaffold text, never on a real episode that happens to share a
# word with it.
SCAFFOLD_EPISODE_TITLE = "using markdown"
SCAFFOLD_BODY_FINGERPRINTS = (
    "this is a lesson created via the carpentries workbench",
    'paste("this", "new", "lesson", "looks", "good")',
    "buoyant barnacle",
)

# Placeholder bullet text left in required blocks after generating a lesson --
# the block itself exists (so check_divs is silent), but nothing inside it is
# real content yet. Matched against a bullet's full text, lowercased and
# stripped, so "Keypoint 1" and "keypoint1" both match.
PLACEHOLDER_BULLET_TEXTS = {
    "keypoint1",
    "keypoint2",
    "keypoint 1",
    "keypoint 2",
    "objective 1",
    "objective n",
    "put questions here",
    "put objectives here",
    "put keypoints here",
}

# Beyond the exact-string set above: a small grammar for the placeholder
# *shapes* authors actually leave behind (found via external validation
# against real bullet text, not just the exact strings from one scaffold).
# Deliberately conservative -- legitimate bullets can be short ("Use Git."),
# so TBD/TODO/FIXME only match as an opener (a real bullet never starts with
# one), while N/A/none require the bullet to be *only* that word, since
# "None of these licenses..." is a real sentence, not a placeholder.
PLACEHOLDER_GRAMMAR_RE = re.compile(
    r"""^(?:
        (?:tbd|todo|fixme)\b[:.]?\s*.*   # opener, e.g. "TODO", "TODO: add content"
        |n/?a                             # whole bullet only: "N/A" or "NA"
        |none                             # whole bullet only
        |[.?!…-]{2,}                 # punctuation-only, e.g. "...", "???"
        |x{2,}                            # "xxx"-style stand-in text
        |[\[<].*[\]>]                     # bracketed instruction, e.g. "[add objective]"
    )$""",
    re.IGNORECASE | re.VERBOSE,
)

# Strips wrapping markdown emphasis/inline-code (**bold**, _em_, `code`) and a
# single trailing sentence-ending punctuation mark before placeholder
# comparison, so "**Keypoint 1**" and "TODO." aren't missed just because the
# exact string doesn't literally match.
_MD_EMPHASIS_RE = re.compile(r"^[*_`]+|[*_`]+$")
_TRAILING_END_PUNCT_RE = re.compile(r"[.!]$")
# Bullet markers this checker recognizes: -, *, +, or an ordered "1." / "1)".
_BULLET_MARKER_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")


def _normalize_bullet_text(raw: str) -> str:
    text = _MD_EMPHASIS_RE.sub("", raw.strip()).strip()
    text = _TRAILING_END_PUNCT_RE.sub("", text).strip()
    return text


def _is_placeholder_bullet(normalized_lower: str) -> bool:
    return normalized_lower in PLACEHOLDER_BULLET_TEXTS or bool(
        PLACEHOLDER_GRAMMAR_RE.match(normalized_lower)
    )

# Workbench's actual convention is learners/reference.md (confirmed against
# both carpentries/workbench-template-md and a real published lesson) -- but
# older lessons may still have a legacy root-level reference.md. One shared
# resolver, used by the glossary-existence check, the glossary-content check,
# and the AI review's glossary reader, so all three agree on which file is
# "the glossary" instead of each hardcoding its own answer (a real bug: the
# content/AI-reader checks used to only look at the modern path, so a legacy
# lesson's real glossary would read as "missing" to the AI review even
# though the existence check correctly found it).
GLOSSARY_CANDIDATE_PATHS = ("learners/reference.md", "reference.md")


def resolve_glossary_path(lesson_dir: Path) -> str | None:
    """The first existing glossary candidate path (repo-relative, forward
    slashes), preferring the modern learners/reference.md, or None if
    neither exists."""
    for rel_path in GLOSSARY_CANDIDATE_PATHS:
        if (lesson_dir / rel_path).exists():
            return rel_path
    return None


GLOSSARY_PLACEHOLDER_FINGERPRINT = "this is a placeholder file"
GLOSSARY_HINT = (
    "[Carpentries Lab] 'No key terms are missing from the lesson glossary' is part of "
    "the reviewer checklist. Port over the terms your episodes actually use."
)

# Scaffold text in learners/instructors/profiles files -- these aren't
# episodes, so check_episode() never sees them, and check_config() only
# checks that a glossary file *exists*. A CLDT-produced repo commonly has
# all of these still at their generated defaults. The glossary itself is
# handled separately (see resolve_glossary_path above), since it alone needs
# candidate-path resolution.
SUPPORT_FILE_CHECKS = {
    "learners/setup.md": (
        "fixme: setup instructions live in this document",
        "[CLDT] Covered in the 'Preparing to Teach' episode's Setup Instructions exercise. "
        "If your lesson needs no software/data setup, replace this with a short note saying "
        "so, rather than leaving the scaffold's example instructions in place.",
    ),
    "instructors/instructor-notes.md": (
        "this is a placeholder file",
        "[CLDT] Covered in the 'Preparing to Teach' episode's Instructor Notes exercise: "
        "rationale, what worked/didn't in early drafts, teaching tips, common "
        "troubleshooting.",
    ),
    "profiles/learner-profiles.md": (
        "this is a placeholder file",
        "Add at least one realistic learner profile, used to sanity-check exercise "
        "difficulty against your stated audience.",
    ),
}

# Collaborative Lesson Development Training (carpentries.github.io/lesson-development-training)
# and The Carpentries Lab reviewer checklist (github.com/carpentries-lab/reviews) both call out
# weak, unmeasurable objective verbs -- prefer "explain"/"choose"/"predict" over these. This is
# a denylist of *openers*, not a verb classifier: a verb absent from this list is not thereby
# "good", and a match here means "worth a second look", not "wrong" -- CLDT's actual test is
# whether attainment is directly observable, not which word an objective happens to start with.
VAGUE_OBJECTIVE_OPENER_RE = re.compile(
    r"^(know|understand|appreciate|learn about|be familiar with|become familiar with|"
    r"be aware of|grasp|(?:gain|develop) an understanding of)\b",
    re.IGNORECASE,
)

# Contractions are a closed set (pronoun/auxiliary + 't/'s/'re/...), unlike possessives
# (any noun + 's) -- matching \w+ before the apostrophe wrongly counts "learner's"/"Git's"
# as contractions. ’ covers curly/smart apostrophes from copy-pasted prose.
_CONTRACTION_STEMS = (
    "don", "doesn", "didn", "won", "wouldn", "can", "couldn", "shouldn", "isn", "aren",
    "wasn", "weren", "hasn", "haven", "hadn", "mustn", "needn", "shan",
    "i", "you", "he", "she", "it", "we", "they", "who", "what", "that", "there", "here",
    "let", "how", "where", "when", "why",
)
CONTRACTION_RE = re.compile(
    r"\b(?:" + "|".join(_CONTRACTION_STEMS) + r")['’](?:t|s|re|ve|ll|d|m)\b",
    re.IGNORECASE,
)
INLINE_CODE_RE = re.compile(r"`[^`]*`")

# Lab checklist + CLDT: "descriptive link text" -- avoid generic phrases that
# say nothing out of context (screen readers, translation).
GENERIC_LINK_TEXT = {
    "here", "click here", "this link", "link", "click", "this",
    "this page", "read more", "learn more",
}

FRONT_MATTER_RE = re.compile(r"^---\n(.*?\n)---\n(.*)$", re.DOTALL)
DIV_FENCE_RE = re.compile(r"^(:{3,})\s*\{?\.?([a-zA-Z-]*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
# A Markdown link/image destination can carry an optional title after the
# URL, separated by whitespace and quoted: `(fig/plot.png "A plot")`. Without
# stripping it, the checker treats the quoted title as part of the file path
# and reports the image/link as missing even when it exists.
_LINK_TITLE_RE = re.compile(r'''^(\S+)(?:\s+["'(].*["')])?$''')


def _strip_link_title(destination: str) -> str:
    match = _LINK_TITLE_RE.match(destination.strip())
    return match.group(1) if match else destination.strip()
CODE_FENCE_RE = re.compile(r"^(```+|~~~+)")


def _code_fence_mask(body: str) -> list[bool]:
    """One bool per line: True if that line falls inside a fenced code block.

    A lesson teaching Markdown, Workbench syntax, or shell `#` comments will
    contain literal `:::` or `#` text inside ```/~~~ blocks -- those aren't
    real divs or headings and must not be checked as such.
    """
    mask = []
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if not in_fence:
            if CODE_FENCE_RE.match(stripped):
                in_fence = True
                mask.append(True)
            else:
                mask.append(False)
        else:
            mask.append(True)
            if CODE_FENCE_RE.match(stripped):
                in_fence = False
    return mask


def _unlisted_episode_files(lesson_dir: Path) -> list[str]:
    """Episode filenames on disk that aren't in config.yaml's `episodes:`
    list. Empty when config.yaml is missing/unparseable, or when the
    `episodes:` field itself is blank -- sandpaper then includes every file
    automatically, so nothing counts as "unlisted" (see check_config()).
    Shared by check_config() (the "not listed" warning) and run_checks()
    (the "this doesn't look like an episode at all" check below, which
    only fires for files that are both unlisted and structurally empty)."""
    config_path = lesson_dir / "config.yaml"
    if not config_path.exists():
        return []
    try:
        config = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError:
        return []
    episodes_field = config.get("episodes")
    if not episodes_field:
        return []
    episodes_dir = lesson_dir / "episodes"
    if not episodes_dir.exists():
        return []
    on_disk = sorted(p.name for p in episodes_dir.glob("*") if p.suffix in (".md", ".Rmd"))
    return [name for name in on_disk if name not in episodes_field]


def check_config(lesson_dir: Path) -> list[Finding]:
    """Check config.yaml: placeholder values, episode list vs. files on disk,
    extension-less episode files, and glossary existence."""
    findings: list[Finding] = []
    config_path = lesson_dir / "config.yaml"
    if not config_path.exists():
        return [
            Finding(
                "error",
                "config",
                "config.yaml not found",
                location="config.yaml",
                hint="Every Workbench lesson needs a config.yaml at its root.",
                code="WB001",
            )
        ]

    try:
        config = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError as exc:
        return [
            Finding(
                "error",
                "config",
                f"config.yaml is not valid YAML: {exc}",
                location="config.yaml",
                code="WB002",
            )
        ]

    if not isinstance(config, dict):
        return [
            Finding(
                "error",
                "config",
                f"config.yaml must be a mapping of key: value pairs, found a "
                f"top-level {type(config).__name__} instead",
                location="config.yaml",
                hint="Example:\n  title: My Lesson\n  episodes:\n    - introduction.md",
                code="WB003",
            )
        ]

    for field, placeholder in CONFIG_PLACEHOLDER_VALUES.items():
        value = config.get(field)
        if not value or value == placeholder:
            findings.append(
                Finding(
                    "error",
                    "config",
                    f"`{field}` is still the template placeholder or empty",
                    location="config.yaml",
                    hint=f"Set `{field}` to your lesson's real value.",
                    code="WB004",
                )
            )

    if not config.get("created"):
        findings.append(
            Finding(
                "warning",
                "config",
                "`created` date is not set",
                location="config.yaml",
                hint="Set `created` to the date the lesson was started (YYYY-MM-DD).",
                code="WB005",
            )
        )

    if config.get("life_cycle") == "pre-alpha":
        findings.append(
            Finding(
                "info",
                "config",
                "`life_cycle` is still `pre-alpha`",
                location="config.yaml",
                hint="Update life_cycle as the lesson matures: pre-alpha -> alpha -> beta -> stable.",
                code="WB006",
            )
        )

    episodes_field = config.get("episodes")
    listed_episodes = episodes_field or []
    episodes_dir = lesson_dir / "episodes"
    on_disk = (
        sorted(p.name for p in episodes_dir.glob("*") if p.suffix in (".md", ".Rmd"))
        if episodes_dir.exists()
        else []
    )

    missing_on_disk = [e for e in listed_episodes if e not in on_disk]
    for name in missing_on_disk:
        findings.append(
            Finding(
                "error",
                "config",
                f"config.yaml lists episode `{name}` but it does not exist under episodes/",
                location="config.yaml",
                hint="Create the file, or remove it from `episodes:` if it's no longer "
                "planned.",
                code="WB007",
            )
        )

    # A file sitting in episodes/ without a .md/.Rmd extension is invisible to
    # both Sandpaper and this checker's own glob() elsewhere -- it silently
    # never gets built, never gets checked, and never shows up as "missing"
    # anywhere else, since nothing ever looked for it. This is exactly what
    # happened to a real draft episode: renamed with a typo, dropped its
    # extension, and sat unbuilt and uninspected for days before anyone
    # noticed. `fig/`, `data/`, and dotfiles are legitimate non-episode
    # entries and are excluded.
    if episodes_dir.exists():
        for p in sorted(episodes_dir.glob("*")):
            if p.is_dir() or p.name.startswith("."):
                continue
            if p.suffix not in (".md", ".Rmd"):
                findings.append(
                    Finding(
                        "warning",
                        "config",
                        f"episodes/{p.name} has no .md/.Rmd extension, Sandpaper won't "
                        "build it and this checker can't inspect it",
                        location="config.yaml",
                        hint="If this is meant to be an episode, rename it with a .md "
                        "extension. Right now it's invisible to the build.",
                        code="WB008",
                    )
                )

    # A blank `episodes:` field is valid and documented: sandpaper then includes
    # every file under episodes/ automatically, in alphabetical order. Only flag
    # "unlisted" files when the author is curating an explicit ordered list.
    if episodes_field:
        for name in _unlisted_episode_files(lesson_dir):
            findings.append(
                Finding(
                    "warning",
                    "config",
                    f"episodes/{name} exists but is not listed in config.yaml `episodes:`",
                    location="config.yaml",
                    hint="Add it to the episodes list so it's included and ordered in the build.",
                    code="WB009",
                )
            )

    if resolve_glossary_path(lesson_dir) is None:
        findings.append(
            Finding(
                "info",
                "config",
                "no glossary file found (learners/reference.md)",
                location="config.yaml",
                hint="[Carpentries Lab] Checks that no key terms are missing from the "
                "lesson glossary. This only checks the file exists, not its contents.",
                code="WB010",
            )
        )

    return findings


def read_lesson_metadata(lesson_dir: Path) -> LessonMetadata:
    """Lesson identity for the report header: title, carpentry, life cycle,
    license, source repo, contact, and authors, from config.yaml and (if
    present) CITATION.cff. Best-effort -- missing or unparseable files just
    leave those fields empty; this is descriptive context for a report
    header, not a check that should fail the run, so it deliberately doesn't
    raise or return Findings the way check_config() does."""
    metadata = LessonMetadata()

    config_path = lesson_dir / "config.yaml"
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text()) or {}
        except yaml.YAMLError:
            config = {}
        carpentry_code = config.get("carpentry") or None
        metadata.title = config.get("title") or None
        metadata.carpentry = (
            CARPENTRY_NAMES.get(carpentry_code, carpentry_code) if carpentry_code else None
        )
        metadata.life_cycle = config.get("life_cycle") or None
        metadata.license = config.get("license") or None
        metadata.source = config.get("source") or None
        metadata.contact = config.get("contact") or None
        metadata.created = config.get("created") or None

    citation_path = lesson_dir / "CITATION.cff"
    if citation_path.exists():
        try:
            citation = yaml.safe_load(citation_path.read_text()) or {}
        except yaml.YAMLError:
            citation = {}
        for entry in citation.get("authors") or []:
            if not isinstance(entry, dict):
                continue
            # CFF allows an "entity" author (an organization) via `name`,
            # instead of the usual given-names/family-names pair.
            name = entry.get("name") or " ".join(
                part for part in (entry.get("given-names"), entry.get("family-names")) if part
            )
            if name:
                metadata.authors.append(name)

    return metadata


def check_support_files(lesson_dir: Path) -> list[Finding]:
    """Check learners/, instructors/, and profiles/ content -- files
    check_episode() never sees (they aren't episodes) and check_config()
    only checks for existence of, not content. A CLDT-produced repo commonly
    has all of these still at their `sandpaper::create_lesson()` defaults,
    each of these files being generated as a valid, present, entirely
    unwritten placeholder."""
    findings = []
    for rel_path, (fingerprint, hint) in SUPPORT_FILE_CHECKS.items():
        path = lesson_dir / rel_path
        if not path.exists():
            continue
        if fingerprint in path.read_text(errors="replace").lower():
            findings.append(
                Finding(
                    "warning",
                    "boilerplate",
                    f"{rel_path} is still the scaffold placeholder, not written yet",
                    location=rel_path,
                    hint=hint,
                    code="WB113",
                )
            )

    glossary_path = resolve_glossary_path(lesson_dir)
    if glossary_path is not None:
        full_path = lesson_dir / glossary_path
        if GLOSSARY_PLACEHOLDER_FINGERPRINT in full_path.read_text(errors="replace").lower():
            findings.append(
                Finding(
                    "warning",
                    "boilerplate",
                    f"{glossary_path} is still the scaffold placeholder, not written yet",
                    location=glossary_path,
                    hint=GLOSSARY_HINT,
                    code="WB114",
                )
            )
    return findings


def _split_front_matter(text: str) -> tuple[dict, str] | None:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return None
    try:
        front_matter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None
    return front_matter, match.group(2)


# Real bug found in a CLDT-produced lesson: `exercise:` (singular) instead
# of `exercises:` silently passes YAML parsing and just looks like a missing
# field, with no indication the author actually wrote a value, just under
# the wrong key. Worth naming directly rather than making the author guess.
_SINGULAR_FIELD_TYPOS = {"exercises": "exercise"}


def _check_front_matter(front_matter: dict, location: str) -> list[Finding]:
    findings = []
    for field in ("title", "teaching", "exercises"):
        if field not in front_matter or front_matter[field] in (None, ""):
            typo = _SINGULAR_FIELD_TYPOS.get(field)
            hint = f"Add `{field}:` to the YAML front matter."
            if typo and typo in front_matter:
                hint = (
                    f"Found `{typo}:` instead, that's likely a typo, the required "
                    f"field is `{field}:` (plural)."
                )
            findings.append(
                Finding(
                    "error",
                    "front-matter",
                    f"missing required front-matter field `{field}`",
                    location=location,
                    hint=hint,
                    code="WB103",
                )
            )
    for field in ("teaching", "exercises"):
        value = front_matter.get(field)
        if value is not None and not isinstance(value, (int, float)):
            findings.append(
                Finding(
                    "warning",
                    "front-matter",
                    f"`{field}` should be a number of minutes, got {value!r}",
                    location=location,
                    hint=f"Set `{field}:` to a plain integer, e.g. `{field}: 15`, not a "
                    "quoted string or a range.",
                    code="WB104",
                )
            )

    teaching, exercises = front_matter.get("teaching"), front_matter.get("exercises")
    if isinstance(teaching, (int, float)) and isinstance(exercises, (int, float)):
        total = teaching + exercises
        if total < 20 or total > 60:
            findings.append(
                Finding(
                    "info",
                    "front-matter",
                    f"episode is {total:g} min (teaching + exercises), outside the "
                    "20-60 min range Collaborative Lesson Development Training suggests",
                    location=location,
                    hint="[CLDT] Not a hard rule -- but very short or very long episodes are "
                    "worth a second look for scope.",
                    code="WB105",
                )
            )
    return findings


def _check_objective_verbs(body: str, location: str) -> tuple[list[Finding], int]:
    """Flag objectives that open with a verb that's often hard to assess
    (know/understand/...) instead of an action verb (explain/choose/predict/...)
    -- see CLDT's SMART objectives guidance and the Carpentries Lab reviewer
    checklist. Also returns the objective bullet count, reused by check_episode()
    for the "2-4 objectives per episode" and "assessed by an exercise" checks."""
    findings = []
    in_code = _code_fence_mask(body)
    lines = body.splitlines()
    depth = 0
    in_objectives = False
    objectives_depth = None
    objective_count = 0

    for i, line in enumerate(lines):
        if in_code[i]:
            continue
        match = DIV_FENCE_RE.match(line.strip())
        if match:
            div_type = match.group(2).lower()
            if div_type:
                if div_type == "objectives" and depth == 0:
                    in_objectives = True
                    objectives_depth = depth
                depth += 1
            else:
                depth -= 1
                if in_objectives and depth == objectives_depth:
                    in_objectives = False
            continue

        if not in_objectives:
            continue
        stripped = line.strip()
        if not stripped.startswith(("-", "*")):
            continue
        bullet_text = stripped.lstrip("-* ").strip()
        objective_count += 1
        verb_match = VAGUE_OBJECTIVE_OPENER_RE.match(bullet_text)
        if verb_match:
            findings.append(
                Finding(
                    "warning",
                    "objectives",
                    f'objective opens with a phrase that can be hard to assess '
                    f'("{verb_match.group(1)}"): "{bullet_text[:70]}"',
                    location=location,
                    hint="[CLDT] Not a hard rule -- judge by whether attainment is directly "
                    "observable, not just the opening word. An action verb (explain, "
                    "choose, predict, ...) usually makes that easier to write.",
                    code="WB401",
                )
            )

    if objective_count > 4:
        findings.append(
            Finding(
                "info",
                "objectives",
                f"{objective_count} objectives in this episode",
                location=location,
                hint="[CLDT] Aim for 2-4 objectives per episode; consider splitting into "
                "multiple episodes if you need more.",
                code="WB402",
            )
        )

    return findings, objective_count


def _check_boilerplate(
    front_matter: dict, body: str, location: str, line_offset: int = 0
) -> list[Finding]:
    """Flag unedited `sandpaper::create_lesson()` scaffold content. The three
    required blocks all being present (so `_check_divs` is silent) says
    nothing about whether anyone has actually written the episode yet -- a
    CLDT cohort under time pressure regularly ships the scaffold's own worked
    example untouched. Exact substring match on purpose, to avoid flagging
    real content that happens to share incidental wording.

    Fingerprints are sourced from `sandpaper::create_lesson()`'s generated
    episode as of the Workbench version in use during the CLDT audit that
    motivated this check (2026-08). If Carpentries changes the scaffold's
    wording upstream, these will stop matching new lessons silently, no
    error, just quietly reduced recall, worth re-diffing against a freshly
    generated lesson occasionally rather than assuming these stay accurate
    forever."""
    findings = []
    title = str(front_matter.get("title") or "").strip().lower()
    if title == SCAFFOLD_EPISODE_TITLE:
        findings.append(
            Finding(
                "error",
                "boilerplate",
                f'title is still the scaffold default: "{front_matter.get("title")}"',
                location=location,
                hint="[CLDT] This is `sandpaper::create_lesson()`'s own default episode "
                "title, not a real one. Replace it before this episode is considered "
                "written.",
                code="WB110",
            )
        )

    body_lower = body.lower()
    for fingerprint in SCAFFOLD_BODY_FINGERPRINTS:
        match_index = body_lower.find(fingerprint)
        if match_index != -1:
            lineno = body.count("\n", 0, match_index) + 1 + line_offset
            findings.append(
                Finding(
                    "warning",
                    "boilerplate",
                    f'body still contains scaffold example text on line {lineno}: '
                    f'"{fingerprint}"',
                    location=location,
                    line=lineno,
                    hint="[CLDT] This looks like unedited Carpentries Workbench scaffold "
                    "content, not real lesson material. Replace it, or delete the episode "
                    "if it isn't ready to write yet, an empty episode is more honest than "
                    "a filled-in-looking one that's still the template.",
                    code="WB111",
                )
            )
    return findings


def _check_placeholder_bullets(body: str, location: str, line_offset: int = 0) -> list[Finding]:
    """Flag placeholder bullet text (`keypoint1`, `Put questions here`, ...)
    left inside `questions`/`objectives`/`keypoints` blocks. The block itself
    existing satisfies `_check_divs`'s required-block check, so this is the
    only thing that catches "structurally complete, actually empty"."""
    findings = []
    in_code = _code_fence_mask(body)
    lines = body.splitlines()
    depth = 0
    tracked_type: str | None = None
    tracked_depth: int | None = None

    for i, line in enumerate(lines):
        if in_code[i]:
            continue
        match = DIV_FENCE_RE.match(line.strip())
        if match:
            div_type = match.group(2).lower()
            if div_type:
                if div_type in REQUIRED_TOP_DIVS and depth == 0:
                    tracked_type = div_type
                    tracked_depth = depth
                depth += 1
            else:
                depth -= 1
                if tracked_type is not None and depth == tracked_depth:
                    tracked_type = None
            continue

        if tracked_type is None:
            continue
        stripped = line.strip()
        marker_match = _BULLET_MARKER_RE.match(stripped)
        if not marker_match:
            continue
        bullet_raw = stripped[marker_match.end():].strip()
        normalized = _normalize_bullet_text(bullet_raw)
        if _is_placeholder_bullet(normalized.lower()):
            reported_line = i + 1 + line_offset
            findings.append(
                Finding(
                    "error",
                    "boilerplate",
                    f'`{tracked_type}` still has placeholder bullet text on line '
                    f'{reported_line}: "{bullet_raw}"',
                    location=location,
                    line=reported_line,
                    hint="[CLDT] Replace with real content, this is scaffold placeholder "
                    "text, not a written keypoint/objective/question.",
                    code="WB112",
                )
            )
    return findings


def _check_contractions(body: str, location: str) -> list[Finding]:
    """The Carpentries Lab reviewer checklist flags heavy contraction use as an
    accessibility concern for translation and ESL learners. Contractions are a
    closed set of stems (it's, don't, ...), unlike possessives (any noun + 's),
    so CONTRACTION_RE only matches known stems -- and inline code spans are
    stripped first so identifiers like `don't_do_this` don't get counted."""
    in_code = _code_fence_mask(body)
    contraction_count = 0
    word_count = 0
    for i, line in enumerate(body.splitlines()):
        if in_code[i]:
            continue
        prose = INLINE_CODE_RE.sub(" ", line)
        contraction_count += len(CONTRACTION_RE.findall(prose))
        word_count += len(prose.split())

    if word_count == 0:
        return []
    rate_per_1000 = contraction_count / word_count * 1000
    if contraction_count >= 5 and rate_per_1000 >= 5:
        return [
            Finding(
                "info",
                "style",
                f"{contraction_count} contractions found ({rate_per_1000:.1f} per 1,000 "
                "words)",
                location=location,
                hint="[Carpentries Lab] Consider spelling them out (don't -> do not) for "
                "translation and ESL learners. This threshold is a local heuristic, not "
                "an official Carpentries rule.",
                code="WB404",
            )
        ]
    return []


def _check_divs(body: str, location: str, line_offset: int = 0) -> list[Finding]:
    findings = []
    stack: list[tuple[str, int]] = []
    seen_top_level: set[str] = set()
    in_code = _code_fence_mask(body)

    for lineno, line in enumerate(body.splitlines(), start=1):
        if in_code[lineno - 1]:
            continue
        match = DIV_FENCE_RE.match(line.strip())
        if not match:
            continue
        div_type = match.group(2).lower()

        if div_type:
            stack.append((div_type, lineno))
            if not stack[:-1]:  # this is a top-level div
                seen_top_level.add(div_type)
            if div_type not in KNOWN_DIV_TYPES:
                findings.append(
                    Finding(
                        "info",
                        "divs",
                        f"unrecognized div type `{div_type}` on line {lineno + line_offset}"
                        " -- verify against the Workbench style guide",
                        location=location,
                        line=lineno + line_offset,
                        hint="See https://carpentries.github.io/sandpaper-docs/episodes.html "
                        "for the full list of recognized div types.",
                        code="WB201",
                    )
                )
        else:
            if not stack:
                findings.append(
                    Finding(
                        "error",
                        "divs",
                        f"extraneous closing `:::` on line {lineno + line_offset} with no "
                        "matching open div",
                        location=location,
                        line=lineno + line_offset,
                        hint="Either this fence has no matching opening `::: type` above it, "
                        "or an earlier div's closing fence was deleted, causing this one to "
                        "close the wrong block. Check the div immediately above.",
                        code="WB202",
                    )
                )
            else:
                stack.pop()

    for div_type, lineno in stack:
        findings.append(
            Finding(
                "error",
                "divs",
                f"`{div_type}` div opened on line {lineno + line_offset} is never closed",
                location=location,
                line=lineno + line_offset,
                hint="Add a closing `:::` fence (same or more colons than the opening "
                "fence) before the next block starts. An unclosed div silently swallows "
                "everything after it, including blocks that look fine on their own, "
                "check whether a `keypoints`/`questions`/`objectives` block further down "
                "actually landed inside this one instead of at the top level.",
                code="WB203",
            )
        )

    for required in REQUIRED_TOP_DIVS:
        if required not in seen_top_level:
            findings.append(
                Finding(
                    "error",
                    "divs",
                    f"missing required `{required}` block",
                    location=location,
                    hint=f"Every episode needs a top-level `:::: {required} ... ::::` block. "
                    "If one exists in the file but isn't showing as top-level, an earlier "
                    "unclosed div is probably nesting it, see any 'never closed' finding "
                    "above first.",
                    code="WB204",
                )
            )

    return findings


def _check_headings(body: str, location: str, line_offset: int = 0) -> list[Finding]:
    findings = []
    seen: dict[str, int] = {}
    first_heading_seen = False
    in_code = _code_fence_mask(body)

    for lineno, line in enumerate(body.splitlines(), start=1):
        if in_code[lineno - 1]:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        level, text = len(match.group(1)), match.group(2).strip()
        reported_line = lineno + line_offset

        if level == 1:
            findings.append(
                Finding(
                    "error",
                    "headings",
                    f"level-1 heading `# {text}` on line {reported_line}"
                    " -- episodes must not use H1, start at H2",
                    location=location,
                    line=reported_line,
                    code="WB210",
                )
            )
        elif not first_heading_seen and level != 2:
            findings.append(
                Finding(
                    "warning",
                    "headings",
                    f"first heading `{'#' * level} {text}` on line {reported_line} is level "
                    f"{level}, expected level 2",
                    location=location,
                    line=reported_line,
                    code="WB211",
                )
            )

        if level >= 2:
            first_heading_seen = True

        if text in seen:
            findings.append(
                Finding(
                    "warning",
                    "headings",
                    f"heading `{text}` on line {reported_line} duplicates the one on line "
                    f"{seen[text]}",
                    location=location,
                    hint="Give each challenge/solution/exercise a unique, descriptive heading "
                    "instead of reusing a generic one.",
                    line=reported_line,
                    code="WB212",
                )
            )
        else:
            seen[text] = reported_line

    return findings


def _check_links(body: str, lesson_dir: Path, location: str, line_offset: int = 0) -> list[Finding]:
    findings = []
    episode_dir = (lesson_dir / "episodes") if (lesson_dir / "episodes").exists() else lesson_dir
    in_code = _code_fence_mask(body)

    for i, line in enumerate(body.splitlines()):
        if in_code[i]:
            continue
        lineno = i + 1 + line_offset
        for alt, raw_path in IMAGE_RE.findall(line):
            path = _strip_link_title(raw_path)
            if not alt.strip():
                findings.append(
                    Finding(
                        "warning",
                        "links",
                        f"image on line {lineno} has no alt text: `{path}`",
                        location=location,
                        line=lineno,
                        hint="Add descriptive alt text for accessibility.",
                        code="WB301",
                    )
                )
            if not path.startswith(("http://", "https://", "{{")):
                # Workbench episodes reference images (e.g. fig/foo.png) relative to
                # episodes/, not the lesson root -- check both, episode dir first.
                in_episode_dir = (episode_dir / path.lstrip("/")).resolve().exists()
                in_lesson_root = (lesson_dir / path.lstrip("/")).resolve().exists()
                if not (in_episode_dir or in_lesson_root):
                    findings.append(
                        Finding(
                            "error",
                            "links",
                            f"image on line {lineno} points to a missing file: `{path}`",
                            location=location,
                            line=lineno,
                            hint="Check the path is relative to episodes/ (images "
                            "typically live in episodes/fig/), and that the file was "
                            "actually committed.",
                            code="WB302",
                        )
                    )

        for text, raw_path in LINK_RE.findall(line):
            path = _strip_link_title(raw_path)
            if text.strip().lower() in GENERIC_LINK_TEXT:
                findings.append(
                    Finding(
                        "warning",
                        "links",
                        f'generic link text "{text}" on line {lineno}',
                        location=location,
                        line=lineno,
                        hint="[CLDT/Carpentries Lab] Screen readers and translation tools "
                        "lose context with generic link text like 'click here' -- "
                        "describe the destination.",
                        code="WB303",
                    )
                )
            if path.startswith(("http://", "https://", "#", "mailto:", "{{")):
                continue
            # Sandpaper renders every .md/.Rmd source to a same-named .html page,
            # so a link to e.g. reference.html or ../learners/setup.html has no
            # literal file on disk -- check for the source instead, either
            # extension, an episode can be written in either.
            check_path = path.split("#", 1)[0]
            candidates = [check_path]
            if check_path.endswith(".html"):
                stem = check_path[: -len(".html")]
                candidates = [stem + ".md", stem + ".Rmd"]
            if not check_path:
                continue
            search_dirs = (
                episode_dir,
                lesson_dir,
                lesson_dir / "learners",
                lesson_dir / "instructors",
                lesson_dir / "profiles",
            )
            if not any(
                (d / candidate.lstrip("/")).resolve().exists()
                for d in search_dirs
                for candidate in candidates
            ):
                findings.append(
                    Finding(
                        "warning",
                        "links",
                        f"internal link on line {lineno} may be broken: `{path}`",
                        location=location,
                        line=lineno,
                        hint="Confirm the target exists relative to episodes/, the "
                        "lesson root, or learners/, instructors/, profiles/. A link to "
                        "another episode's rendered .html targets its .md source.",
                        code="WB304",
                    )
                )
    return findings


def check_episode(path: Path, lesson_dir: Path) -> list[Finding]:
    """Run every episode-level check (front matter, divs, headings, links,
    boilerplate, placeholder bullets, objective verbs, contractions) on one
    episode file."""
    location = str(path.relative_to(lesson_dir)) if path.is_relative_to(lesson_dir) else path.name
    text = path.read_text(errors="replace")
    findings: list[Finding] = []

    parsed = _split_front_matter(text)
    if parsed is None:
        findings.append(
            Finding(
                "error",
                "front-matter",
                "episode does not start with a `---` YAML front-matter block",
                location=location,
                code="WB101",
            )
        )
        body = text
        front_matter = {}
        line_offset = 0
    elif not isinstance(parsed[0], dict):
        findings.append(
            Finding(
                "error",
                "front-matter",
                f"front matter must be a mapping of key: value pairs, found a "
                f"top-level {type(parsed[0]).__name__} instead",
                location=location,
                hint="Example:\n  title: My Episode\n  teaching: 10\n  exercises: 5",
                code="WB102",
            )
        )
        body = parsed[1]
        front_matter = {}
        line_offset = text[: len(text) - len(body)].count("\n")
    else:
        front_matter, body = parsed
        findings.extend(_check_front_matter(front_matter, location))
        # Every check below reports line numbers relative to `body`, which
        # starts after the front matter -- offset them back to real file
        # line numbers, or every reported line is wrong by the front
        # matter's length.
        line_offset = text[: len(text) - len(body)].count("\n")

    findings.extend(_check_divs(body, location, line_offset))
    findings.extend(_check_headings(body, location, line_offset))
    findings.extend(_check_links(body, lesson_dir, location, line_offset))
    findings.extend(_check_boilerplate(front_matter, body, location, line_offset))
    findings.extend(_check_placeholder_bullets(body, location, line_offset))
    objective_findings, objective_count = _check_objective_verbs(body, location)
    findings.extend(objective_findings)
    findings.extend(_check_contractions(body, location))

    # [Carpentries Lab]: "All lesson and episode objectives are assessed by
    # exercises or another opportunity for formative assessment."
    if objective_count > 0 and front_matter.get("exercises") == 0:
        findings.append(
            Finding(
                "warning",
                "objectives",
                f"{objective_count} objective(s) declared but exercises: 0 -- nothing "
                "in this episode formally assesses them",
                location=location,
                hint="[Carpentries Lab] Consider adding a challenge, discussion, or "
                "other formative-assessment checkpoint.",
                code="WB403",
            )
        )

    in_code = _code_fence_mask(body)
    lines = body.splitlines()
    challenges = sum(
        1
        for i, ln in enumerate(lines)
        if not in_code[i] and re.match(r"^:{3,}\s*\{?\.?challenge", ln)
    )
    solutions = sum(
        1
        for i, ln in enumerate(lines)
        if not in_code[i] and re.match(r"^:{3,}\s*\{?\.?solution", ln)
    )
    if challenges > solutions:
        findings.append(
            Finding(
                "info",
                "divs",
                f"{challenges} challenge(s) but only {solutions} solution(s)",
                location=location,
                hint="Not every challenge needs a solution block, but double-check this is intentional.",
                code="WB205",
            )
        )

    return findings


def _looks_misplaced(episode_findings: list[Finding]) -> bool:
    """True when an "episode" has none of the three required
    questions/objectives/keypoints blocks at all. Even a totally blank,
    just-created episode has empty versions of all three, since they're
    baked into `sandpaper::create_lesson()`'s own scaffold -- so zero of
    the three present is a much stronger "this was never meant to be an
    episode" signal than "this episode is very unwritten." Checked against
    the actual WB204 findings (each required block that's missing produces
    its own Finding), not by re-parsing the body, so this can't drift out of
    sync with what _check_divs() actually detected."""
    missing_required = sum(1 for f in episode_findings if f.code == "WB204")
    return missing_required == len(REQUIRED_TOP_DIVS)


def run_checks(lesson_dir: Path, episode_filter: str | None = None) -> list[Finding]:
    """Entry point: run config/support-file checks plus every episode check,
    optionally scoped to one episode via episode_filter."""
    findings = check_config(lesson_dir)
    findings.extend(check_support_files(lesson_dir))

    episodes_dir = lesson_dir / "episodes"
    if not episodes_dir.exists():
        findings.append(
            Finding("error", "config", "no episodes/ directory found", location=str(lesson_dir), code="WB011")
        )
        return findings

    episode_files = sorted(p for p in episodes_dir.glob("*") if p.suffix in (".md", ".Rmd"))
    if episode_filter:
        episode_files = [p for p in episode_files if p.name == episode_filter]
        if not episode_files:
            findings.append(
                Finding(
                    "error",
                    "config",
                    f"no episode named `{episode_filter}` found under episodes/",
                    code="WB012",
                )
            )
            return findings

    unlisted = set(_unlisted_episode_files(lesson_dir))
    for path in episode_files:
        episode_findings = check_episode(path, lesson_dir)
        if path.name in unlisted and _looks_misplaced(episode_findings):
            findings.append(
                Finding(
                    "warning",
                    "config",
                    f"episodes/{path.name} has none of the required "
                    "questions/objectives/keypoints blocks and isn't listed in "
                    "config.yaml `episodes:` -- this looks like reference content, not "
                    "an unwritten episode",
                    location=str(path.relative_to(lesson_dir)),
                    hint="If this is meant to be an episode, add the required blocks "
                    "and list it in config.yaml. If it's reference content instead, "
                    "move it: a glossary belongs in learners/reference.md; other "
                    "support material belongs under learners/, instructors/, or "
                    "profiles/, not episodes/.",
                    code="WB013",
                )
            )
        findings.extend(episode_findings)

    return assign_occurrences(findings)
