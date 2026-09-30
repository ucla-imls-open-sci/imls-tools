"""Rule registry: one stable code per check, with what it observes, why it
matters, what to do, when to keep the content anyway, what the check can't
see, and the most specific source sections behind it.

A rule code identifies a check, not an individual finding (see
Finding.id for that). Codes are never renumbered or reused; a retired check
keeps its entry (with a note saying so) so old results and issues still
explain themselves.

Numbering (see issue #23):
  WB0xx  config.yaml, episode list, lesson-level files
  WB1xx  episode front matter, scaffold/placeholder content, support files
  WB2xx  fenced divs and headings
  WB3xx  links and images
  WB4xx  objectives and style
  AI2xx  AI review findings, one code per review area (checker/ai_review.py)

Four separate questions per rule, per design/2026-09-30-rule-schema-help-proposal.md:
  topic      what the author is working on
  authority  the basis of the practice (not proof a finding is right)
  detection  how the conclusion is reached
  default_severity  the reporting default, matching what the check emits

Sources were read and their section anchors checked on 2026-09-30 (see
design/2026-09-30-standards-audit.md). `checked_on` only moves when someone
re-reads a source and confirms it still supports the claim; a link that
still resolves isn't enough.
"""

from __future__ import annotations

from dataclasses import dataclass

Guide = tuple[str, str]  # (label, url), the legacy citation shape

TOPICS = ("metadata", "structure", "accessibility", "pedagogy", "prose", "supporting-material", "operations")
AUTHORITIES = ("technical-requirement", "review-criterion", "recommendation", "checker-policy")
DETECTIONS = ("deterministic", "heuristic", "ai-assisted", "human-only")
SEVERITIES = ("error", "warning", "info")
APPLIES_TO = ("config", "episode", "support-page", "invocation")

AUTHORITY_LABELS = {
    "technical-requirement": "Workbench technical requirement",
    "review-criterion": "Carpentries review criterion",
    "recommendation": "Carpentries recommendation",
    "checker-policy": "wbcheck's own policy",
}
DETECTION_LABELS = {
    "deterministic": "deterministic check",
    "heuristic": "heuristic (a proxy for the underlying question)",
    "ai-assisted": "AI-assisted suggestion",
    "human-only": "needs human review",
}


@dataclass(frozen=True)
class Reference:
    """One source section: what it is, where, when it was last read, and
    exactly what it supports (including where a threshold is our own)."""

    title: str
    section: str
    url: str
    checked_on: str
    supports: str
    revision: str | None = None  # a content commit, when known; None = live page, unpinned

    @property
    def label(self) -> str:
        """Short citation label, e.g. "CLDT: Assessments"."""
        return f"{self.title}: {self.section}"

    @property
    def provenance(self) -> str:
        """The source revision if pinned, else says it's a live page."""
        return f"revision {self.revision[:12]}" if self.revision else "live page, unpinned"


_SANDPAPER = "https://carpentries.github.io/sandpaper-docs"
_CLDT = "https://carpentries.github.io/lesson-development-training"
_LAB = "https://github.com/carpentries-lab/reviews/blob/main/docs"
_LAB_REV = "d3ee510983b7997fd1b1f4f2b58a25a79e48092d"  # carpentries-lab/reviews main, 2026-09-30
_CHECKED = "2026-09-30"


def _ref(title: str, section: str, url: str, supports: str, revision: str | None = None) -> Reference:
    return Reference(title, section, url, _CHECKED, supports, revision)


REFERENCES: dict[str, Reference] = {
    "wb.config": _ref(
        "Workbench", "config.yaml", f"{_SANDPAPER}/editing.html#config-yaml",
        "The lesson-level fields in config.yaml (title, contact, source, created, life_cycle, "
        "episodes) and what each is for."),
    "wb.organization": _ref(
        "Workbench", "Organization (episode order and drafts)", f"{_SANDPAPER}/editing.html#organization",
        "An explicit `episodes:` list sets which files are published and in what order; a blank "
        "list uses every file alphabetically; drafts can stay unlisted on purpose."),
    "wb.new-episode": _ref(
        "Workbench", "Creating a new episode", f"{_SANDPAPER}/episodes.html#creating-a-new-episode",
        "Episodes are .md or .Rmd files in episodes/."),
    "wb.yaml": _ref(
        "Workbench", "YAML metadata", f"{_SANDPAPER}/episodes.html#yaml-metadata",
        "Episode front matter holds title, teaching, and exercises, timings in minutes."),
    "wb.required": _ref(
        "Workbench", "Questions, objectives, keypoints",
        f"{_SANDPAPER}/episodes.html#questions-objectives-keypoints",
        "Each episode has questions, objectives, and keypoints blocks."),
    "wb.components": _ref(
        "Workbench Component Guide", "Components", f"{_SANDPAPER}/component-guide.html",
        "The fenced-div components Workbench styles. Custom classes are valid Pandoc; they're "
        "just not styled."),
    "wb.callouts": _ref(
        "Workbench", "Callout blocks", f"{_SANDPAPER}/episodes.html#callout-blocks",
        "Fenced divs open and close with a line of at least three colons; the lengths needn't match."),
    "wb.fenced-divs": _ref(
        "Workbench style guide", "Fenced divs", f"{_SANDPAPER}/instructor/style.html#fenced-divs",
        "Recommendations for readable fenced-div source, not Pandoc grammar."),
    "wb.challenges": _ref(
        "Workbench", "Exercises/challenges", f"{_SANDPAPER}/episodes.html#exerciseschallenges",
        "Challenge and solution blocks, nesting, and multiple solutions."),
    "wb.internal-links": _ref(
        "Workbench", "Internal links", f"{_SANDPAPER}/episodes.html#internal-links",
        "Link to other lesson files by their source path."),
    "wb.figures": _ref(
        "Workbench", "Figures", f"{_SANDPAPER}/episodes.html#figures",
        "Figure markup: captions, explicit `{alt='...'}` attributes (which may wrap across lines), "
        "and alt text for generated R figures."),
    "wb.decorative": _ref(
        "Workbench", "Decorative images", f"{_SANDPAPER}/episodes.html#decorative-images",
        "`alt=\"\"` marks an image as decorative, so screen readers skip it."),
    "pegboard.headings": _ref(
        "pegboard", "validate_headings: Details",
        "https://carpentries.github.io/pegboard/reference/validate_headings.html#details",
        "Workbench's heading validation: first heading at level 2, nothing at level 1, levels "
        "increase sequentially, headings have names, and names are unique within their own "
        "hierarchy."),
    "cldt.smart": _ref(
        "CLDT", "SMART objectives", f"{_CLDT}/objectives.html#smart-objectives",
        "Objectives should describe specific, observable outcomes. It doesn't ban particular "
        "opening verbs; the verb list is wbcheck's proxy."),
    "cldt.planning": _ref(
        "CLDT", "Planning your episodes", f"{_CLDT}/episodes.html#planning-your-episodes",
        "Episodes typically take 20-60 minutes, as a planning recommendation."),
    "cldt.episode-objectives": _ref(
        "CLDT", "Defining episode-level learning objectives",
        f"{_CLDT}/episodes.html#defining-episode-level-learning-objectives",
        "2-4 objectives per episode as a starting point for scope."),
    "cldt.assessments": _ref(
        "CLDT", "Assessments", f"{_CLDT}/formative-assessment.html#assessments",
        "Formative assessment checks learner progress and can take several forms, not only "
        "timed exercises."),
    "cldt.accessibility": _ref(
        "CLDT", "Accessibility", f"{_CLDT}/explanation.html#accessibility",
        "Accessible writing: descriptive link text, alt text, and related practices."),
    "cldt.language": _ref(
        "CLDT", "Language", f"{_CLDT}/explanation.html#language",
        "Plain, inclusive language, including avoiding contractions, idioms, and dismissive "
        "words. Contextual advice, not a word list."),
    "cldt.less-is-more": _ref(
        "CLDT", "Less is more", f"{_CLDT}/explanation.html#less-is-more",
        "Limit how much new material an episode introduces."),
    "cldt.glossary": _ref(
        "CLDT", "Glossary of terms", f"{_CLDT}/explanation.html#glossary-of-terms",
        "Define the key terms a lesson uses in a glossary."),
    "cldt.workbench": _ref(
        "CLDT", "Using the Carpentries Workbench", f"{_CLDT}/aio.html#using-the-carpentries-workbench",
        "Lessons start from the Workbench template, whose placeholder content gets replaced."),
    "lab.reviewer.access": _ref(
        "Lab reviewer checklist", "Accessibility", f"{_LAB}/reviewer_guide.md#accessibility",
        "Reviewers check alt text, link text, heading structure, and extensive contraction use.",
        _LAB_REV),
    "lab.reviewer.content": _ref(
        "Lab reviewer checklist", "Content", f"{_LAB}/reviewer_guide.md#content",
        "Reviewers check accuracy, exercises and solutions, and that objectives are assessed by "
        "exercises or another formative assessment.", _LAB_REV),
    "lab.reviewer.design": _ref(
        "Lab reviewer checklist", "Design", f"{_LAB}/reviewer_guide.md#design",
        "Reviewers check that objectives are clear, measurable, and fit the audience.", _LAB_REV),
    "lab.reviewer.support": _ref(
        "Lab reviewer checklist", "Supporting information", f"{_LAB}/reviewer_guide.md#supporting-information",
        "Reviewers check setup instructions, learner profiles, and that key terms are defined, in a "
        "lesson glossary or a linked external one.", _LAB_REV),
    "lab.editor.access": _ref(
        "Lab editor checklist", "Accessibility", f"{_LAB}/editor_guide.md#accessibility",
        "Editors check heading structure and other accessibility basics.", _LAB_REV),
    "lab.editor.content": _ref(
        "Lab editor checklist", "Content", f"{_LAB}/editor_guide.md#content",
        "Editors check that exercises have solutions or guidance.", _LAB_REV),
    "lab.editor.structure": _ref(
        "Lab editor checklist", "Structure", f"{_LAB}/editor_guide.md#structure",
        "Editors check episode timings and structure.", _LAB_REV),
    "lab.editor.notes": _ref(
        "Lab editor checklist", "Notes (solutions)", f"{_LAB}/editor_guide.md#notes",
        "Solutions are wanted for every challenge, but guidance is enough where no single solution "
        "fits, and discussion exercises need none.", _LAB_REV),
}


@dataclass(frozen=True)
class Rule:
    """One check's stable identity and its explanation. See the module
    docstring for the four classification fields. Fix capability is not
    stored here: checker/fix.py owns it (fix_capability())."""

    code: str
    name: str
    title: str
    topic: str
    authority: str
    detection: str
    default_severity: str
    severity_reason: str
    applies_to: tuple[str, ...]
    checks: str  # the exact observation or proxy, including local thresholds
    why: str  # why it matters, without overstating cause
    response: str  # the general next step, distinct from a finding's own hint
    references: tuple[str, ...] = ()  # REFERENCES keys, most specific first
    context: str = ""
    exceptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    example: str | None = None
    related: tuple[str, ...] = ()

    @property
    def guides(self) -> tuple[Guide, ...]:
        """(label, url) citations, the shape reports and saved results
        have always used."""
        return tuple((REFERENCES[key].label, REFERENCES[key].url) for key in self.references)


_EP = ("episode",)
_CFG = ("config",)
_BLOCKING = "Blocks or breaks the Workbench build, or the check can't run past it."
_SCAFFOLD_LIMIT = ("Matches known scaffold text only; a changed upstream template won't match, and "
                   "a lesson that teaches the scaffold can match legitimately.")

_RULES: tuple[Rule, ...] = (
    # -- WB0xx: config.yaml, episode list, lesson-level files ---------------
    Rule("WB001", "config-missing", "config.yaml not found", "metadata", "technical-requirement",
         "deterministic", "error", _BLOCKING, _CFG,
         checks="No config.yaml at the checked directory's root.",
         why="Workbench can't build a lesson without config.yaml.",
         response="Check you pointed wbcheck at the lesson root, or create config.yaml from the template.",
         references=("wb.config",), related=("WB011",)),
    Rule("WB002", "config-invalid-yaml", "config.yaml is not valid YAML", "metadata", "technical-requirement",
         "deterministic", "error", _BLOCKING, _CFG,
         checks="config.yaml doesn't parse as YAML; the parser's message is included.",
         why="Nothing in config.yaml is readable until it parses.",
         response="Fix the YAML syntax at the line the parser reports.",
         references=("wb.config",),
         limitations=("Parsing is all this checks; field values are checked by other rules.",)),
    Rule("WB003", "config-not-mapping", "config.yaml is not a key: value mapping", "metadata",
         "technical-requirement", "deterministic", "error", _BLOCKING, _CFG,
         checks="config.yaml parses, but its top level is a list or a single value instead of named fields.",
         why="Workbench reads config.yaml as named fields.",
         response="Rewrite it as `field: value` lines, following the template.",
         references=("wb.config",)),
    Rule("WB004", "config-placeholder", "config.yaml field is empty or still the template value", "metadata",
         "checker-policy", "heuristic", "error",
         "An error because a lesson published with the template's title, contact, or source misleads "
         "readers; it's wbcheck's default, not a build failure.", _CFG,
         checks="title, contact, or source is empty or exactly equals the Workbench template's value.",
         why="Template values ship a lesson with the wrong title, contact, or source.",
         response="Set the field to this lesson's real value.",
         references=("wb.config",),
         exceptions=("A lesson that genuinely shares a template value, such as a Carpentries team contact.",),
         limitations=("Compares with three known template strings; any other wrong value passes.",)),
    Rule("WB005", "config-created-missing", "`created` date not set", "metadata", "recommendation",
         "deterministic", "warning", "Worth fixing, but the lesson still builds.", _CFG,
         checks="config.yaml has no usable `created` value.",
         why="The creation date is lesson metadata that readers and citations can use.",
         response="Record the date the lesson was started (YYYY-MM-DD), if known.",
         references=("wb.config",),
         limitations=("Doesn't check that the date is valid or plausible.",)),
    Rule("WB006", "life-cycle-pre-alpha", "`life_cycle` still pre-alpha", "metadata", "recommendation",
         "deterministic", "info", "A reminder only: pre-alpha can be accurate.", _CFG,
         checks="config.yaml's life_cycle is exactly `pre-alpha`.",
         why="Life cycle tells learners and instructors how mature the lesson is.",
         response="Keep it if it reflects where the lesson is; update it when the lesson has been taught "
         "and revised.",
         references=("wb.config",),
         exceptions=("A lesson that is still in pre-alpha development.",),
         limitations=("wbcheck can't tell whether a lesson is ready for the next stage; that's a "
                      "human decision.",)),
    Rule("WB007", "episode-listed-missing", "episode listed in config.yaml does not exist", "structure",
         "technical-requirement", "deterministic", "error", _BLOCKING, _CFG,
         checks="A filename in config.yaml's `episodes:` list has no matching file in episodes/.",
         why="The build fails or silently skips a listed episode.",
         response="Restore the file, fix the name, or remove the entry.",
         references=("wb.organization", "wb.config"), related=("WB009",)),
    Rule("WB008", "episode-no-extension", "file in episodes/ has no .md/.Rmd extension", "structure",
         "checker-policy", "heuristic", "warning", "Worth checking; it may be a stray file on purpose.", _CFG,
         checks="A regular, non-hidden file in episodes/ has an extension other than .md or .Rmd.",
         why="Workbench won't build it and nothing checks it.",
         response="Rename it with .md if it's meant to be an episode; otherwise leave it or move it.",
         references=("wb.new-episode",),
         exceptions=("Data files or notes kept in episodes/ on purpose.",),
         limitations=("Assumes any such file might be an episode.",)),
    Rule("WB009", "episode-unlisted", "episode file not listed in config.yaml", "structure",
         "technical-requirement", "deterministic", "warning",
         "A warning so an accidentally unpublished episode is noticed; drafts are a normal reason.",
         _CFG,
         checks="config.yaml has an explicit `episodes:` list and an .md/.Rmd file in episodes/ isn't in it.",
         why="An explicit episodes list publishes only the files it names; an unlisted file stays an "
         "unpublished draft, which may be intentional.",
         response="Leave a draft unlisted until it's ready; then add it to `episodes:`, which publishes it "
         "in that position.",
         references=("wb.organization",),
         exceptions=("A draft episode you aren't ready to publish.",),
         limitations=("Doesn't know which unlisted files are drafts; a blank `episodes:` list (automatic "
                      "order) is never flagged.",),
         related=("WB013", "WB007")),
    Rule("WB010", "glossary-missing", "no local glossary file", "supporting-material", "review-criterion",
         "heuristic", "info", "A note only: a linked glossary is an accepted alternative.", _CFG,
         checks="Neither learners/reference.md nor a legacy root reference.md exists.",
         why="The Lab checklists ask that key terms are defined, in a lesson glossary or a linked "
         "external one; no local file doesn't mean no definitions.",
         response="Confirm key terms are defined where learners can find them: a local glossary or a "
         "linked external one.",
         references=("lab.reviewer.support", "cldt.glossary"),
         exceptions=("The lesson links to an external glossary.",),
         limitations=("Only looks for a local file at two paths (not .Rmd or other names) and doesn't read "
                      "links; a file's presence says nothing about which terms it covers.",),
         related=("WB114", "AI206")),
    Rule("WB011", "episodes-dir-missing", "no episodes/ directory", "structure", "technical-requirement",
         "deterministic", "error", _BLOCKING, _CFG,
         checks="The checked directory has no episodes/ folder.",
         why="A Workbench lesson's content lives in episodes/.",
         response="Check you pointed wbcheck at the lesson root.",
         references=("wb.new-episode",), related=("WB001",)),
    Rule("WB012", "episode-filter-no-match", "--episode named a file that doesn't exist", "operations",
         "checker-policy", "deterministic", "error",
         "An invocation problem, not a lesson-quality finding. It's reported as a finding for now; "
         "making it an ordinary command error is a separate, announced change.", ("invocation",),
         checks="`--episode NAME` matched no .md/.Rmd file in episodes/.",
         why="The requested episode couldn't be checked.",
         response="Use an existing filename from episodes/, e.g. `--episode 01-introduction.md`.",
         limitations=("Says nothing about the lesson itself.",)),
    Rule("WB013", "episode-looks-misplaced", "episode file looks like reference content", "structure",
         "checker-policy", "heuristic", "warning", "Worth a look; it may be an intentional draft.", _EP,
         checks="An unlisted file in episodes/ has none of the questions, objectives, or keypoints blocks.",
         why="An unlisted file in episodes/ with no episode blocks may be support material that belongs "
         "in learners/ or instructors/, or an early draft.",
         response="If it's support material, move it (a glossary goes in learners/reference.md); if it's "
         "a draft episode, add the blocks when you write it.",
         references=("wb.organization", "cldt.workbench"),
         exceptions=("An unwritten draft episode.",),
         limitations=("Infers purpose from missing blocks only.",), related=("WB009", "WB204")),
    # -- WB1xx: front matter, scaffold content, support files ---------------
    Rule("WB101", "front-matter-missing", "episode has no YAML front matter", "metadata",
         "technical-requirement", "deterministic", "error", _BLOCKING, _EP,
         checks="The episode doesn't start with a `---` block that parses as YAML.",
         why="Title and timings come from the front matter.",
         response="Start the file with a `---` block holding title, teaching, and exercises.",
         references=("wb.yaml",),
         limitations=("A front-matter block with invalid YAML is reported the same as a missing one.",)),
    Rule("WB102", "front-matter-not-mapping", "front matter is not a key: value mapping", "metadata",
         "technical-requirement", "deterministic", "error", _BLOCKING, _EP,
         checks="The front matter parses, but isn't named fields.",
         why="Workbench reads front matter as named fields.",
         response="Rewrite it as `field: value` lines.", references=("wb.yaml",)),
    Rule("WB103", "front-matter-field-missing", "required front-matter field missing", "metadata",
         "technical-requirement", "deterministic", "error", _BLOCKING, _EP,
         checks="title, teaching, or exercises is absent or empty; a singular `exercise:` typo is named.",
         why="title, teaching, and exercises are required for every episode.",
         response="Add the field. `wbcheck fix --apply` can rename a singular `exercise:` key.",
         references=("wb.yaml",), related=("WB104",)),
    Rule("WB104", "front-matter-time-not-number", "teaching/exercises is not a number of minutes", "metadata",
         "technical-requirement", "deterministic", "warning", "The build may still run, but timings are wrong.",
         _EP,
         checks="teaching or exercises isn't a finite, non-negative number: a string, a range, a YAML "
         "`true`/`false`, `.nan`, `.inf`, or a negative value. Zero and fractions are fine.",
         why="Timings feed the lesson schedule.",
         response="Set it to a plain number of minutes, e.g. `exercises: 15`.",
         references=("wb.yaml",),
         context="\"Finite and non-negative\" is wbcheck's reading of a number of minutes.",
         limitations=("Timing-based checks (WB105, WB403) are skipped while the value is invalid.",),
         related=("WB103", "WB105", "WB403")),
    Rule("WB105", "episode-length-out-of-range", "episode length outside 20-60 minutes", "pedagogy",
         "recommendation", "heuristic", "info", "A prompt to review scope, never a requirement.", _EP,
         checks="teaching + exercises, as declared, is under 20 or over 60 minutes.",
         why="CLDT suggests 20-60 minutes as a typical episode; very short or long ones are worth a look "
         "for scope.",
         response="Keep it if it fits (an introduction or wrap-up is often short); otherwise review the "
         "episode's scope.",
         references=("cldt.planning", "lab.editor.structure"),
         exceptions=("Introductions, recaps, and short lessons.",),
         limitations=("Uses declared minutes, not how long the episode takes to teach.",),
         related=("WB104",)),
    Rule("WB110", "scaffold-title", "episode title is still the scaffold default", "supporting-material",
         "checker-policy", "heuristic", "error",
         "An error because an unedited scaffold episode reads as finished; wbcheck's default, not a build "
         "failure.", _EP,
         checks="The episode title is exactly the scaffold's \"Using Markdown\".",
         why="The episode reads as written when it isn't.",
         response="Give the episode its real title.",
         references=("cldt.workbench",),
         exceptions=("An episode that really is about using Markdown.",), limitations=(_SCAFFOLD_LIMIT,),
         related=("WB111",)),
    Rule("WB111", "scaffold-body-text", "episode body still contains scaffold example text",
         "supporting-material", "checker-policy", "heuristic", "warning", "Worth replacing before publishing.",
         _EP,
         checks="The episode contains one of the scaffold episode's distinctive sentences.",
         why="Template content ships as lesson content.",
         response="Replace the scaffold text with the lesson's own material.",
         references=("cldt.workbench",),
         exceptions=("A lesson that teaches or quotes the Workbench scaffold.",),
         limitations=(_SCAFFOLD_LIMIT,), related=("WB110",)),
    Rule("WB112", "placeholder-bullet", "placeholder text in questions/objectives/keypoints",
         "supporting-material", "checker-policy", "heuristic", "error",
         "An error because the required block exists but says nothing yet; wbcheck's default.", _EP,
         checks="A bullet in a questions/objectives/keypoints block is scaffold text or placeholder-shaped "
         "(TODO, TBD, N/A, [bracketed instruction], ...).",
         why="The required block exists but says nothing yet.",
         response="Write the real question, objective, or key point.",
         references=("wb.required",),
         exceptions=("A real bullet that happens to look like a placeholder.",),
         limitations=("Pattern-based; can't judge whether a real-looking bullet says anything useful.",),
         related=("WB204",)),
    Rule("WB113", "support-file-placeholder", "setup/instructor notes/profiles still the scaffold",
         "supporting-material", "review-criterion", "heuristic", "warning", "Worth replacing before review.",
         ("support-page",),
         checks="learners/setup.md, instructors/instructor-notes.md, or profiles/learner-profiles.md still "
         "contains its scaffold marker text.",
         why="Learners and instructors get template text instead of real guidance.",
         response="Write lesson-specific guidance, or replace the placeholder with a short note if the "
         "lesson doesn't need it.",
         references=("lab.reviewer.support",),
         limitations=(_SCAFFOLD_LIMIT, "Doesn't check that setup instructions work.")),
    Rule("WB114", "glossary-placeholder", "glossary is still the scaffold placeholder", "supporting-material",
         "review-criterion", "heuristic", "warning", "Placeholder text reads as unfinished.", ("support-page",),
         checks="The local glossary file still contains the scaffold's placeholder text.",
         why="Placeholder text in the local glossary reads as unfinished, wherever the lesson's terms are "
         "actually defined.",
         response="Replace it with the lesson's terms, or remove it if a linked external glossary is used.",
         references=("lab.reviewer.support", "cldt.glossary"),
         limitations=("Says nothing about how well any glossary covers the lesson's terms.",),
         related=("WB010", "AI206")),
    # -- WB2xx: fenced divs and headings ------------------------------------
    Rule("WB201", "div-unknown-type", "unrecognized div type", "structure", "checker-policy", "heuristic",
         "info", "Often a typo, but custom classes are legitimate.", _EP,
         checks="A div's first class isn't one of the Workbench components wbcheck knows.",
         why="An unknown div renders unstyled, often a typo.",
         response="Check the spelling; keep it if it's a deliberate custom class.",
         references=("wb.components",),
         exceptions=("Custom classes with their own styling.",),
         limitations=("Looks at the first class only; the known list may lag new components.",)),
    Rule("WB202", "div-extra-close", "closing ::: with no matching open div", "structure",
         "technical-requirement", "deterministic", "error", _BLOCKING, _EP,
         checks="A closing fence appears with no open div to close.",
         why="Unbalanced fences change which content lands in which block.",
         response="Check the div just above: a missing opener, or an extra closer.",
         references=("wb.callouts", "wb.fenced-divs"),
         limitations=("Colons in unusual Markdown contexts can be misread; code fences are skipped.",),
         related=("WB203",)),
    Rule("WB203", "div-unclosed", "div never closed", "structure", "technical-requirement", "deterministic",
         "error", _BLOCKING, _EP,
         checks="A div is still open at the end of the episode.",
         why="An unclosed div swallows everything after it. Pandoc closes it at the end of the file, but "
         "Workbench's parser (pegboard) rejects the episode.",
         response="Add a closing fence (at least three colons) where the block should end.",
         references=("wb.callouts", "wb.fenced-divs"),
         limitations=("Can report where a div opened, not where it should close.",), related=("WB202", "WB204")),
    Rule("WB204", "required-block-missing", "required questions/objectives/keypoints block missing",
         "structure", "technical-requirement", "deterministic", "error", _BLOCKING, _EP,
         checks="No top-level questions, objectives, or keypoints block was recognized.",
         why="Every episode needs all three at the top level.",
         response="Add the block, or fix the nesting if an unclosed div above swallowed it.",
         references=("wb.required",),
         limitations=("Recognizes a block by its first class, so `::: {.custom .questions}` isn't seen; "
                      "which class orders Workbench itself accepts is unverified.",),
         related=("WB203", "WB112")),
    Rule("WB205", "challenge-without-solution", "more challenges than solutions", "pedagogy",
         "review-criterion", "heuristic", "info", "A prompt to review guidance, not proof of a gap.", _EP,
         checks="The episode has more challenge blocks than solution blocks, counted across the whole episode.",
         why="The Lab editor checklist asks for solutions or guidance for non-discussion exercises. This "
         "compares totals only, so it can't tell which exercise lacks one.",
         response="Review each exercise's guidance: a solution, or notes on what to look for.",
         references=("lab.editor.notes", "lab.editor.content", "wb.challenges"),
         exceptions=("Discussion exercises.", "Exercises with guidance instead of a single solution."),
         limitations=("Compares totals: two solutions for one challenge can hide another with none, and "
                      "no finding doesn't mean every exercise has guidance.",)),
    Rule("WB210", "heading-h1", "episode uses a level-1 heading", "accessibility", "technical-requirement",
         "deterministic", "error", "Workbench's heading validation rejects it.", _EP,
         checks="The episode source has a `#` level-1 heading.",
         why="The episode title is the only H1; a second breaks page structure.",
         response="Use `##` for top-level sections.",
         references=("pegboard.headings", "lab.editor.access"),
         limitations=("Setext and raw-HTML headings aren't checked.",), related=("WB211",)),
    Rule("WB211", "heading-first-not-h2", "first heading is not level 2", "accessibility",
         "technical-requirement", "deterministic", "warning", "Worth fixing for navigation.", _EP,
         checks="The first section heading (outside divs) isn't `##`.",
         why="Sections start at H2; skipped levels break screen-reader navigation.",
         response="Start sections at `##`.",
         references=("pegboard.headings", "lab.editor.access"),
         limitations=("Checks source headings, not the rendered page.",), related=("WB210", "WB213")),
    Rule("WB212", "heading-duplicate", "duplicate heading text", "accessibility", "technical-requirement",
         "deterministic", "warning", "Worth distinguishing for navigation.", _EP,
         checks="Two headings with the same text and level share the same parent section.",
         why="Repeated headings under the same parent are hard to tell apart when navigating by heading; "
         "pegboard requires headings to be unique within their hierarchy.",
         response="Give one of them a distinguishing label.",
         references=("pegboard.headings", "lab.editor.access"),
         exceptions=("The same heading under different parent sections is fine.",),
         limitations=("Compares heading text exactly, as written in the source.",)),
    Rule("WB213", "heading-level-jump", "heading skips a level", "accessibility", "technical-requirement",
         "deterministic", "warning", "Worth fixing for navigation.", _EP,
         checks="A heading is more than one level deeper than the one before it (component headings count).",
         why="Skipped levels (h2 -> h4) break the outline screen readers navigate by.",
         response="Change the heading's level, or add the missing intermediate heading; which is right "
         "depends on the outline you intend.",
         references=("pegboard.headings", "lab.editor.access"),
         limitations=("Checks source headings, not the rendered page.",), related=("WB211",)),
    # -- WB3xx: links and images --------------------------------------------
    Rule("WB301", "image-no-alt", "image has no alt text", "accessibility", "review-criterion",
         "deterministic", "warning", "Worth fixing before review.", _EP,
         checks="An image has no caption text, no `alt=` attribute, and no decorative `alt=\"\"` marker.",
         why="Alt text is how screen-reader users get the figure; decorative images are marked with "
         "alt=\"\" instead.",
         response="Describe the image with `{alt='...'}`, or mark a decorative one `{alt=\"\"}`.",
         references=("wb.figures", "wb.decorative", "lab.reviewer.access"),
         exceptions=("A figure described in detail in the text right next to it, if its alt says so.",),
         limitations=("Checks that a description or marker is present, not that it describes the figure.",
                      "Reference-style images and figures generated by R code aren't checked.")),
    Rule("WB302", "image-missing-file", "image file not found", "structure", "technical-requirement",
         "deterministic", "error", "The figure won't render.", _EP,
         checks="A local image path doesn't exist relative to episodes/ or the lesson root.",
         why="The figure won't render.",
         response="Fix the path (images usually live in episodes/fig/) or commit the file.",
         references=("wb.figures",),
         limitations=("Reference-style images and generated figures aren't checked.",)),
    Rule("WB303", "link-generic-text", "generic link text", "accessibility", "review-criterion", "heuristic",
         "warning", "Worth rewording before review.", _EP,
         checks="A link's text is one of a few generic English phrases (\"click here\", \"this link\", ...).",
         why="'Click here' loses meaning for screen readers and translation.",
         response="Make the link text say where it goes.",
         references=("lab.reviewer.access", "cldt.accessibility"),
         limitations=("A fixed English phrase list; context and other languages aren't considered.",)),
    Rule("WB304", "link-internal-broken", "internal link target not found", "structure", "technical-requirement",
         "heuristic", "warning", "May be a false alarm, so a warning rather than an error.", _EP,
         checks="A relative link's target (with .html mapped to its .md/.Rmd source) isn't found in the "
         "usual lesson folders.",
         why="Learners hit a 404.",
         response="Check the target path in the rendered lesson.",
         references=("wb.internal-links",),
         limitations=("Anchors aren't checked, reference-style links aren't checked, and searching several "
                      "folders can hide a wrong relative path.",)),
    # -- WB4xx: objectives and style ----------------------------------------
    Rule("WB401", "objective-vague-opener", "objective opens with a hard-to-assess verb", "pedagogy",
         "recommendation", "heuristic", "warning", "Worth a second look; the verb is a proxy.", _EP,
         checks="A top-level objective starts with understand, know, learn about, be familiar with, or a "
         "similar phrase.",
         why="Objectives should describe observable, assessable outcomes.",
         response="Name what learners will do that you can observe. `wbcheck fix --suggest` offers a draft "
         "verb, which you confirm one at a time.",
         references=("cldt.smart", "lab.reviewer.design"),
         limitations=("An opener list, not a judgment: a listed verb can be fine in context, and an "
                      "unlisted one can still be vague.",),
         related=("WB402", "WB403", "AI201")),
    Rule("WB402", "objectives-too-many", "more than 4 objectives in one episode", "pedagogy", "recommendation",
         "heuristic", "info", "A prompt to review scope, never a requirement.", _EP,
         checks="The objectives block has more than four top-level items.",
         why="CLDT suggests 2-4 objectives per episode as a starting point for scope.",
         response="Consider whether the episode covers too much, or whether objectives can merge.",
         references=("cldt.episode-objectives",),
         exceptions=("An episode whose scope really needs more.",),
         limitations=("Counts list items, not distinct outcomes.",), related=("WB401",)),
    Rule("WB403", "objectives-not-assessed", "objectives declared but no exercise time", "pedagogy",
         "review-criterion", "heuristic", "warning", "Worth checking; zero minutes is only a prompt.", _EP,
         checks="The episode declares objectives and its front matter says `exercises: 0`.",
         why="Objectives should have an opportunity for formative assessment. Zero declared exercise time "
         "is a prompt to check that, not proof it's missing.",
         response="Check that learners get a chance to show each objective, and that `exercises:` reflects "
         "the time it takes.",
         references=("cldt.assessments", "lab.reviewer.content"),
         exceptions=("A discussion or check-in may already assess the objectives.",),
         limitations=("Zero exercise time doesn't mean nothing assesses the objectives, and positive time "
                      "doesn't prove that it does.",),
         related=("WB104", "AI201", "AI202")),
    Rule("WB404", "contractions-heavy", "heavy use of contractions", "prose", "checker-policy", "heuristic",
         "info", "A prompt for prose review only.", _EP,
         checks="Author prose (not code or blockquotes) has 5+ contraction-like matches and 5+ per 1,000 "
         "whitespace-separated tokens. The threshold is wbcheck's own.",
         why="The Lab reviewer checklist asks reviewers to consider extensive contraction use in author "
         "prose; the count threshold is wbcheck's own.",
         response="Review author prose for translation clarity; don't change quoted text or data.",
         references=("lab.reviewer.access", "cldt.language"),
         context="English author prose.",
         exceptions=("Quotations, data values, and names.",),
         limitations=("An English pattern match; inline quotations inside prose lines still count.",)),
)

# -- AI2xx: AI review areas (checker/ai_review.py AREA_CODES) -------------------
_AI_SEVERITY = ("The model chooses warning or info for each finding; warning is the documented default, "
                "not an override.")
_AI_LIMIT = ("A matched quote shows where the finding points, not that the judgment is right.",
             "The model sees one episode's source text, the local glossary file, and the mechanical "
             "findings: not rendered pages, run code, other episodes, or learner profiles.")

_AI_RULES: tuple[Rule, ...] = (
    Rule("AI201", "ai-objectives", "objective not observable or not assessed", "pedagogy", "review-criterion",
         "ai-assisted", "warning", _AI_SEVERITY, _EP,
         checks="The model judges whether objectives are observable and assessed in this episode.",
         why="AI suggestion: objectives should describe observable outcomes the episode assesses. The model "
         "sees one episode, not the whole lesson.",
         response="Check how you'd observe this objective, and where it's assessed.",
         references=("cldt.smart", "lab.reviewer.design"),
         limitations=_AI_LIMIT, related=("WB401", "WB403")),
    Rule("AI202", "ai-assessment", "exercise lacks diagnostic power or variety", "pedagogy", "review-criterion",
         "ai-assisted", "warning", _AI_SEVERITY, _EP,
         checks="The model judges whether exercises give feedback on each objective.",
         why="AI suggestion: exercises should give feedback on each objective. Discussion or other guidance "
         "can be enough.",
         response="Review the exercise against its objective.",
         references=("cldt.assessments", "lab.reviewer.content", "lab.editor.notes"),
         limitations=_AI_LIMIT, related=("WB205", "WB403")),
    Rule("AI203", "ai-audience", "difficulty or pacing mismatched to audience", "pedagogy", "review-criterion",
         "ai-assisted", "warning", _AI_SEVERITY, _EP,
         checks="The model looks for unstated prerequisites and sudden jumps.",
         why="AI suggestion: possible unstated prerequisites or jumps. The model doesn't see your learner "
         "profiles, so compare with your stated audience.",
         response="Compare the assumed prerequisite with your learner profiles.",
         references=("cldt.planning", "lab.reviewer.content"), limitations=_AI_LIMIT),
    Rule("AI204", "ai-cognitive-load", "episode covers too much at once", "pedagogy", "recommendation",
         "ai-assisted", "warning", _AI_SEVERITY, _EP,
         checks="The model judges whether the episode introduces too much at once.",
         why="AI suggestion: possibly too much at once. The model has no pilot or timing data.",
         response="Compare with how the episode went when taught.",
         references=("cldt.less-is-more", "cldt.planning"), limitations=_AI_LIMIT, related=("WB105",)),
    Rule("AI205", "ai-tone", "dismissive language, idioms, or unexplained jargon", "prose", "recommendation",
         "ai-assisted", "warning", _AI_SEVERITY, _EP,
         checks="The model flags possibly dismissive wording, idioms, or unexplained jargon.",
         why="AI suggestion: wording worth checking in context. Words like 'simply' and 'just' can "
         "discourage learners; the same word in code, data, or a name is fine.",
         response="Reread the wording in context.",
         references=("cldt.language", "lab.reviewer.access"),
         exceptions=("Code, data values, names, and quotations.",), limitations=_AI_LIMIT, related=("WB404",)),
    Rule("AI206", "ai-glossary-gap", "term needs a glossary entry", "supporting-material", "review-criterion",
         "ai-assisted", "warning", _AI_SEVERITY, _EP,
         checks="The model flags terms it thinks aren't explained, with a draft definition.",
         why="AI suggestion: a term may need a definition. The model sees only the local glossary file, if "
         "any, not linked external glossaries.",
         response="Check whether the term is defined locally or in a linked glossary before adding one.",
         references=("lab.reviewer.support", "cldt.glossary"),
         limitations=_AI_LIMIT, related=("WB010", "WB114")),
    Rule("AI207", "ai-accessibility", "figure or content not accessible", "accessibility", "review-criterion",
         "ai-assisted", "warning", _AI_SEVERITY, _EP,
         checks="The model flags alt text or color cues from the source text.",
         why="AI suggestion from source text only: the model doesn't see rendered figures or measure "
         "contrast, so inspect the rendered page.",
         response="Inspect the rendered figure and its description.",
         references=("lab.reviewer.access", "wb.figures"), limitations=_AI_LIMIT, related=("WB301",)),
    Rule("AI208", "ai-accuracy", "statement or code looks incorrect", "pedagogy", "review-criterion",
         "ai-assisted", "warning", _AI_SEVERITY, _EP,
         checks="The model flags statements or code it thinks are wrong.",
         why="AI suggestion: a possible error. Nothing was executed or checked against a source; verify "
         "before changing the lesson.",
         response="Run the example or check an authoritative source; keep the original if it's right.",
         references=("lab.reviewer.content",), limitations=_AI_LIMIT),
)

RULES: dict[str, Rule] = {rule.code: rule for rule in _RULES + _AI_RULES}


def get_rule(code: str | None) -> Rule | None:
    """The registered Rule for `code`, or None for an unknown/missing code."""
    return RULES.get(code) if code else None
