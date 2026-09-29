"""Rule registry: one stable code per check, with its rationale and the most
specific guide section that states the rule.

A rule code is a finding's durable identity -- the thing issue filing,
suppression, and the TUI key on -- so codes are never renumbered or reused.
Retire a check by deleting its entry, not by giving its code to a new one.

Numbering (see issue #23):
  WB0xx  config.yaml, episode list, lesson-level files
  WB1xx  episode front matter, scaffold/placeholder content, support files
  WB2xx  fenced divs and headings
  WB3xx  links and images
  WB4xx  objectives and style
  AI2xx  AI review findings, one code per review area (checker/ai_review.py)

Guide anchors were checked against the live pages on 2026-09-29:
sandpaper-docs, the Collaborative Lesson Development Training (CLDT)
all-in-one page, and carpentries-lab/reviews' reviewer and editor guides.
See design/future-work-guide-citations-2026-08-31.md for the research
behind the Lab-guide mappings.
"""

from __future__ import annotations

from dataclasses import dataclass

Guide = tuple[str, str]  # (label, url)

_SANDPAPER = "https://carpentries.github.io/sandpaper-docs"
_CLDT = "https://carpentries.github.io/lesson-development-training/aio.html"
_LAB = "https://github.com/carpentries-lab/reviews/blob/main/docs"

G_EPISODES = ("Workbench: Creating a new episode", f"{_SANDPAPER}/episodes.html#creating-a-new-episode")
G_CONFIG = ("Workbench: Configuration", f"{_SANDPAPER}/episodes.html#configuration")
G_YAML = ("Workbench: YAML metadata", f"{_SANDPAPER}/episodes.html#yaml-metadata")
G_REQUIRED = (
    "Workbench: Questions, objectives, keypoints",
    f"{_SANDPAPER}/episodes.html#questions-objectives-keypoints",
)
G_COMPONENTS = ("Workbench Component Guide", f"{_SANDPAPER}/component-guide.html")
G_FENCED_DIVS = ("Workbench style: Fenced divs", f"{_SANDPAPER}/instructor/style.html#fenced-divs")
G_CHALLENGES = ("Workbench: Exercises/challenges", f"{_SANDPAPER}/episodes.html#exerciseschallenges")
G_INTERNAL_LINKS = ("Workbench: Internal links", f"{_SANDPAPER}/episodes.html#internal-links")
G_FIGURES = ("Workbench: Figures", f"{_SANDPAPER}/episodes.html#figures")
G_CLDT_SMART = ("CLDT: SMART objectives", f"{_CLDT}#smart-objectives")
G_CLDT_EPISODES = ("CLDT: Planning your episodes", f"{_CLDT}#planning-your-episodes")
G_CLDT_ASSESS = ("CLDT: Formative assessment", f"{_CLDT}#assessments")
G_CLDT_ACCESS = ("CLDT: Accessibility", f"{_CLDT}#accessibility")
G_CLDT_GLOSSARY = ("CLDT: Glossary of terms", f"{_CLDT}#glossary-of-terms")
G_CLDT_REPO = ("CLDT: Using the Workbench", f"{_CLDT}#using-the-carpentries-workbench")
G_LAB_REV_ACCESS = ("Lab reviewer checklist: Accessibility", f"{_LAB}/reviewer_guide.md#accessibility")
G_LAB_REV_DESIGN = ("Lab reviewer checklist: Design", f"{_LAB}/reviewer_guide.md#design")
G_LAB_REV_SUPPORT = (
    "Lab reviewer checklist: Supporting information",
    f"{_LAB}/reviewer_guide.md#supporting-information",
)
G_LAB_ED_ACCESS = ("Lab editor checklist: Accessibility", f"{_LAB}/editor_guide.md#accessibility")
G_LAB_ED_CONTENT = ("Lab editor checklist: Content", f"{_LAB}/editor_guide.md#content")
G_LAB_ED_STRUCTURE = ("Lab editor checklist: Structure", f"{_LAB}/editor_guide.md#structure")


@dataclass(frozen=True)
class Rule:
    """One check's stable identity: code, short kebab-case name, a
    one-line title, why it matters, and guide citations (most specific
    first)."""

    code: str
    name: str
    title: str
    why: str
    guides: tuple[Guide, ...] = ()


_RULES: tuple[Rule, ...] = (
    # -- WB0xx: config.yaml, episode list, lesson-level files ---------------
    Rule("WB001", "config-missing", "config.yaml not found",
         "Sandpaper can't build a lesson without config.yaml.", (G_CONFIG,)),
    Rule("WB002", "config-invalid-yaml", "config.yaml is not valid YAML",
         "Nothing in config.yaml is readable until it parses.", (G_CONFIG,)),
    Rule("WB003", "config-not-mapping", "config.yaml is not a key: value mapping",
         "Sandpaper reads config.yaml as named fields.", (G_CONFIG,)),
    Rule("WB004", "config-placeholder", "config.yaml field is empty or still the template value",
         "Template values ship a lesson with the wrong title, contact, or source.", (G_CONFIG,)),
    Rule("WB005", "config-created-missing", "`created` date not set",
         "The creation date feeds the lesson's citation and metadata.", (G_CONFIG,)),
    Rule("WB006", "life-cycle-pre-alpha", "`life_cycle` still pre-alpha",
         "Life cycle tells learners and instructors how mature the lesson is.", (G_CONFIG,)),
    Rule("WB007", "episode-listed-missing", "episode listed in config.yaml does not exist",
         "The build fails or silently skips a listed episode.", (G_CONFIG,)),
    Rule("WB008", "episode-no-extension", "file in episodes/ has no .md/.Rmd extension",
         "Sandpaper won't build it and nothing checks it.", (G_EPISODES,)),
    Rule("WB009", "episode-unlisted", "episode file not listed in config.yaml",
         "Unlisted episodes are left out of the build order.", (G_CONFIG,)),
    Rule("WB010", "glossary-missing", "no glossary file",
         "The Lab checklist expects a glossary of key terms.", (G_LAB_REV_SUPPORT, G_CLDT_GLOSSARY)),
    Rule("WB011", "episodes-dir-missing", "no episodes/ directory",
         "A Workbench lesson's content lives in episodes/.", (G_EPISODES,)),
    Rule("WB012", "episode-filter-no-match", "--episode named a file that doesn't exist",
         "The requested episode couldn't be checked.", ()),
    Rule("WB013", "episode-looks-misplaced", "episode file looks like reference content",
         "Support material in episodes/ gets built as an episode.", (G_CLDT_REPO,)),
    # -- WB1xx: front matter, scaffold content, support files ---------------
    Rule("WB101", "front-matter-missing", "episode has no YAML front matter",
         "Title and timings come from the front matter.", (G_YAML,)),
    Rule("WB102", "front-matter-not-mapping", "front matter is not a key: value mapping",
         "Sandpaper reads front matter as named fields.", (G_YAML,)),
    Rule("WB103", "front-matter-field-missing", "required front-matter field missing",
         "title, teaching, and exercises are required for every episode.", (G_YAML,)),
    Rule("WB104", "front-matter-time-not-number", "teaching/exercises is not a number of minutes",
         "Timings feed the lesson schedule.", (G_YAML,)),
    Rule("WB105", "episode-length-out-of-range", "episode length outside 20-60 minutes",
         "Very short or long episodes are a cognitive-load and scope signal.",
         (G_LAB_ED_STRUCTURE, G_CLDT_EPISODES)),
    Rule("WB110", "scaffold-title", "episode title is still the scaffold default",
         "The episode reads as written when it isn't.", (G_CLDT_REPO,)),
    Rule("WB111", "scaffold-body-text", "episode body still contains scaffold example text",
         "Template content ships as lesson content.", (G_CLDT_REPO,)),
    Rule("WB112", "placeholder-bullet", "placeholder text in questions/objectives/keypoints",
         "The required block exists but says nothing yet.", (G_REQUIRED,)),
    Rule("WB113", "support-file-placeholder", "setup/instructor notes/profiles still the scaffold",
         "Learners and instructors get template text instead of real guidance.",
         (G_LAB_REV_SUPPORT,)),
    Rule("WB114", "glossary-placeholder", "glossary is still the scaffold placeholder",
         "The Lab checklist expects no key terms missing from the glossary.",
         (G_LAB_REV_SUPPORT, G_CLDT_GLOSSARY)),
    # -- WB2xx: fenced divs and headings ------------------------------------
    Rule("WB201", "div-unknown-type", "unrecognized div type",
         "An unknown div renders unstyled, often a typo.", (G_COMPONENTS,)),
    Rule("WB202", "div-extra-close", "closing ::: with no matching open div",
         "Unbalanced fences change which content lands in which block.", (G_FENCED_DIVS,)),
    Rule("WB203", "div-unclosed", "div never closed",
         "An unclosed div swallows everything after it.", (G_FENCED_DIVS,)),
    Rule("WB204", "required-block-missing", "required questions/objectives/keypoints block missing",
         "Every episode needs all three at the top level.", (G_REQUIRED,)),
    Rule("WB205", "challenge-without-solution", "more challenges than solutions",
         "The Lab editor checklist expects solutions for non-discussion exercises.",
         (G_LAB_ED_CONTENT, G_CHALLENGES)),
    Rule("WB210", "heading-h1", "episode uses a level-1 heading",
         "The episode title is the only H1; a second breaks page structure.", (G_LAB_ED_ACCESS,)),
    Rule("WB211", "heading-first-not-h2", "first heading is not level 2",
         "Sections start at H2; skipped levels break screen-reader navigation.", (G_LAB_ED_ACCESS,)),
    Rule("WB212", "heading-duplicate", "duplicate heading text",
         "Duplicate headings produce ambiguous anchors and table-of-contents entries.",
         (G_LAB_ED_ACCESS,)),
    Rule("WB213", "heading-level-jump", "heading skips a level",
         "Skipped levels (h2 -> h4) break the outline screen readers navigate by.", (G_LAB_ED_ACCESS,)),
    # -- WB3xx: links and images --------------------------------------------
    Rule("WB301", "image-no-alt", "image has no alt text",
         "Alt text is how screen-reader users get the figure.", (G_LAB_REV_ACCESS, G_FIGURES)),
    Rule("WB302", "image-missing-file", "image file not found",
         "The figure won't render.", (G_FIGURES,)),
    Rule("WB303", "link-generic-text", "generic link text",
         "'Click here' loses meaning for screen readers and translation.",
         (G_LAB_REV_ACCESS, G_CLDT_ACCESS)),
    Rule("WB304", "link-internal-broken", "internal link target not found",
         "Learners hit a 404.", (G_INTERNAL_LINKS,)),
    # -- WB4xx: objectives and style ----------------------------------------
    Rule("WB401", "objective-vague-opener", "objective opens with a hard-to-assess verb",
         "Objectives should describe observable, assessable outcomes.",
         (G_CLDT_SMART, G_LAB_REV_DESIGN)),
    Rule("WB402", "objectives-too-many", "more than 4 objectives in one episode",
         "Many objectives in one episode is a scope and cognitive-load signal.",
         (G_CLDT_EPISODES,)),
    Rule("WB403", "objectives-not-assessed", "objectives declared but no exercise time",
         "Objectives should be assessed by an exercise or other formative check.",
         (G_CLDT_ASSESS, G_LAB_REV_DESIGN)),
    Rule("WB404", "contractions-heavy", "heavy use of contractions",
         "Contractions make lessons harder for translation and ESL learners.",
         (G_LAB_REV_ACCESS,)),
)

# -- AI2xx: AI review areas (checker/ai_review.py AREA_CODES) -------------------
_AI_RULES: tuple[Rule, ...] = (
    Rule("AI201", "ai-objectives", "objective not observable or not assessed",
         "Objectives should describe observable outcomes the episode actually assesses.",
         (G_CLDT_SMART, G_LAB_REV_DESIGN)),
    Rule("AI202", "ai-assessment", "exercise lacks diagnostic power or variety",
         "Exercises should test each objective and reveal specific misconceptions.",
         (G_CLDT_ASSESS, G_LAB_ED_CONTENT)),
    Rule("AI203", "ai-audience", "difficulty or pacing mismatched to audience",
         "Unstated expert assumptions and sudden jumps lose novice learners.", (G_CLDT_EPISODES,)),
    Rule("AI204", "ai-cognitive-load", "episode covers too much at once",
         "Too many new ideas, or ideas before worked examples, overload learners.", (G_CLDT_EPISODES,)),
    Rule("AI205", "ai-tone", "dismissive language, idioms, or unexplained jargon",
         "Words like 'simply' and 'just' discourage learners who find a step hard.",
         (G_LAB_REV_ACCESS, G_CLDT_ACCESS)),
    Rule("AI206", "ai-glossary-gap", "term needs a glossary entry",
         "The Lab checklist expects no key terms missing from the glossary.",
         (G_LAB_REV_SUPPORT, G_CLDT_GLOSSARY)),
    Rule("AI207", "ai-accessibility", "figure or content not accessible",
         "Alt text and non-color cues are how some learners get the content.", (G_LAB_REV_ACCESS,)),
    Rule("AI208", "ai-accuracy", "statement or code looks incorrect",
         "Errors in lesson content become learner misconceptions.", (G_LAB_ED_CONTENT,)),
)

RULES: dict[str, Rule] = {rule.code: rule for rule in _RULES + _AI_RULES}


def get_rule(code: str | None) -> Rule | None:
    """The registered Rule for `code`, or None for an unknown/missing code."""
    return RULES.get(code) if code else None
