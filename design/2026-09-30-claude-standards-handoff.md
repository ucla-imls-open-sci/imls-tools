# Implementation handoff: standards, diagnostic claims and rule help

Date: 2026-09-30. Audience: Claude or another implementer working in the existing wbcheck repository. This file is a proposed implementation plan, not evidence that any change below has been made.

Read alongside [the complete standards audit](2026-09-30-standards-audit.md) and [the schema/help proposal](2026-09-30-rule-schema-help-proposal.md). Those documents contain the rule matrix, source inventory, field dictionary, six before/after examples and identity migration. This handoff states implementation order and acceptance criteria without requiring the conversation.

## Start here

Repository: `https://github.com/ucla-imls-open-sci/carpentries-workbench-checker`.

Reviewed checkout: `/Users/timdennis/projects/lessons/tools/carpentries-workbench-checker`, branch `main`, HEAD **9032b056c2a3a18a12068f9db1e6c7a7c7e5136e**, wbcheck **0.2.1**. The resumed review found one untracked audit document and no production modifications. Completion adds the two companion documents and an additive verification note in that audit. These review documents are not committed by this task.

Before implementing:

1. Read applicable AGENTS instructions, current branch/status, README, CONTRIBUTING, CHANGELOG and these design documents. The supplied checker path is the explicit target; an ancestor AGENTS file's generic Carpentries path is stale and is not a reason to move repositories.
2. Inspect the current implementations at the symbols named below. Reproduce each finding before editing. Recognize completed fixes, discard stale findings, and preserve unresolved interpretations as questions. Do not implement from historical line numbers alone.
3. Preserve existing user work. Use the repository's branch/PR workflow when implementation is authorized. This evaluation itself authorizes no production edit, commit, push, issue filing or model spending.
4. Record separately any planned changes to default severity, selection, exit behavior, safe fixes, saved-result versions or finding identity. Do not hide those in a metadata refactor.

## What is already fixed

Do not reimplement the September 15 review. Current main already has core/AI dependency separation, a Typer command suite, a Textual TUI, persistent results, per-rule citations, quote-anchored AI findings, dirty-file link handling, focused episode display/exit behavior, consistent issue eligibility, recoverable result errors and guarded fix paths. WB009 and WB401 are already individually confirmed editorial suggestions. Issues already carry an AI-judgment caveat. Most earlier review items are historical context.

The outstanding concern is that some remaining detectors and messages infer more than their evidence supports, and their explanations lack a consistent place for context and exceptions.

## Change sequence

| Step | Scope | Dependency / independent delivery |
|---|---|---|
| 1 | Precise source links, rule rationale and hint corrections: STD-09; contextual explanations for STD-02/04/05/08/11 | Can land without changing mechanical messages or IDs. Preserve severities and selected rules. |
| 2 | Finding identity compatibility: STD-06 | Required before any mechanical message changes. No schema/help redesign is required. |
| 3 | Observation-only messages; targeted parser fixes STD-01/03/07/12 | Separate patches with exception fixtures. Each can land independently once its identity implications are resolved. |
| 4 | Registry fields, references, offline help and shared rendering: DES-01/02 | Uses corrected explanations, not a prerequisite for detector fixes. |
| 5 | TUI help; editorial-fix policy STD-10; operational-error policy DES-03 | Distinct behavior changes, reviewed and tested explicitly. |
| Later | WB205 ancestry, broader div grammar, profile selection and lesson-level AI context | Preserve unresolved questions; do not force these into the first release. |

Where current message parsing drives a fix, retain a compatible fallback until structured evidence is available. The handoff does not require a new Markdown parser or a new framework.

## Confirmed corrections and limitations

### STD-01: image description syntax

Priority medium; confidence high for reproduced source-markup cases.

Files/symbols: `checker/lesson_check.py::_check_links` and image parsing helpers; `checker/rules.py` WB301; `tests/test_lesson_check.py`, `tests/test_codex_review_regressions.py`.

Evidence: an existing `fig/plot.png` plus `![](fig/plot.png){alt="A bar chart showing counts"}` emits WB301. So does explicit `alt=""`. Pandoc 3.11 renders the supplied attribute in both cases. The author documentation describes [figure attributes and decorative images](https://carpentries.github.io/sandpaper-docs/episodes.html#figures).

Proposed change: distinguish missing description syntax from explicit descriptions and declared decorative intent. Recognize supported inline/multiline attributes before diagnosing missing alt. Do not certify description adequacy or decorative appropriateness. Preserve an exception for descriptions supplied in nearby text in explanatory help; do not automatically infer that arbitrary nearby text describes the figure.

Acceptance: nonempty explicit alt and explicit decorative markers do not produce missing-alt findings; an image with neither fallback text nor explicit attribute still does. Cover single/double quotes, multiline attributes, caption plus explicit alt, ordinary caption fallback, code literals and nonexistent file independently. WB302 must still detect the nonexistent file. Describe unsupported generated/reference markup without claiming it passed. No automatic fix or severity change.

### STD-02: zero declared exercise time is not absence of assessment

Priority medium; confidence high.

Files/symbols: `lesson_check.py::check_episode` WB403; `rules.py` WB403; report/console consumers of its message. Tests: `test_lesson_check.py`, `test_rules.py`, `test_results_lifecycle.py`.

Evidence: a valid objective, `exercises: 0`, and an explicit discussion/checkpoint still emit “nothing in this episode formally assesses them”. The [assessment guidance](https://carpentries.github.io/lesson-development-training/formative-assessment.html#assessments) supports checking learner progress; the metadata is only a proxy.

Proposed change: state the observed zero and invite checking existing assessment opportunities and timing. Point to the timing field when a source location is known. Keep the current warning default in this patch. Do not infer that a positive duration proves alignment or silently add minutes.

Acceptance: fixture with discussion does not deny that assessment exists; fixture without it receives the same bounded prompt. Boolean/nonfinite timing is handled as invalid metadata under STD-12, not silently interpreted as a count. Old/new WB403 identities match under STD-06. No automatic fix.

### STD-03: duplicate headings and anchors

Priority medium; confidence high for scoped duplication and the anchor-rationale correction.

Files/symbols: `lesson_check.py::_check_headings`; `rules.py` WB212; tests in `test_lesson_check.py`.

Evidence: `## Alpha / ### Example / ## Beta / ### Example` emits WB212; the saved audit's pegboard 0.7.9 experiment accepts the names in their separate hierarchies. [pegboard heading validation](https://carpentries.github.io/pegboard/reference/validate_headings.html#details) specifies hierarchy-local uniqueness. Pandoc's generated `results` and `results-1` identifiers contradict the registry's generic collision claim.

Proposed change: remove the collision assertion immediately. Scope name-duplication detection to the relevant structural hierarchy after confirming component handling. Continue warning about genuinely confusing sibling headings, without claiming every repetition breaks links.

Acceptance: separate-parent repeats pass; repeated siblings are covered; H2/H3/H4 parent changes, skipped levels, component headings and code fences have explicit expectations. Do not add source line numbers to IDs. Any loss of an old false-positive finding is expected; new legitimate findings must not inherit an unrelated ignored sibling's ID. No automatic heading rename.

### STD-04: challenge/solution totals

Priority medium; confidence high for the global-count limitation. Per-challenge replacement is a later design change.

Files/symbols: `lesson_check.py::check_episode`, `_div_fence`, `_check_divs`; `rules.py` WB205. Tests: `test_lesson_check.py` and migration tests if the detector is replaced.

Evidence: challenge A with two solutions and challenge B with none produces no WB205. A count match is not coverage. The [Lab editor Notes](https://github.com/carpentries-lab/reviews/blob/main/docs/editor_guide.md#notes) describe discussion and alternative-guidance exceptions.

First change: retain aggregate evidence, info severity and rule code; say that it prompts a review of guidance rather than proving an exercise has no answer. Help explains both the masking case and exceptions.

Later acceptance: if nested-block association is introduced, identify the challenge with no descendant solution while allowing discussion and guidance elsewhere. Test nested callouts, multiple solutions, floating solutions, discussion classes and unrelated global solutions. Explicitly resolve the one-aggregate-to-many finding-ID transition first. An empty new finding list must not be described as complete exercise coverage.

### STD-05: glossary alternatives and intentionally unpublished episodes

Priority medium; confidence high for the wording mismatch; coverage of all alternate paths remains bounded.

Files/symbols: `lesson_check.py::resolve_glossary_path`, `check_config`, `check_support_files`; `ai_review.py::build_glossary_block`, `INSTRUCTIONS`; `rules.py` WB009/WB010/WB114/AI206; `fix.py::_fix_wb009`; relevant pinned rubric text.

Evidence: external glossary links do not affect WB010's local-file test. Both Lab guides allow linked external definitions. WB009 correctly avoids a warning when episode discovery is automatic, but its action still directs adding an explicitly excluded draft. [Workbench organization](https://carpentries.github.io/sandpaper-docs/editing.html#organization) documents this distinction.

Proposed change: distinguish “no local file at these checked paths” from “definitions absent”. Explain external or differently located resources as alternatives. Keep the warning to clean up actual local scaffold text. In AI input, “no local glossary supplied” must not become “no glossary written”. For WB009, retain-as-draft is a legitimate response; confirmation to insert an episode must describe publication/order consequences.

Acceptance: missing local glossary plus external link yields qualified advice, not a demand to create a duplicate glossary. A placeholder local file with external coverage still gets cleanup advice. No network retrieval in normal checks. Blank/null episode lists retain automatic discovery behavior; explicit exclusion remains detectable. Existing WB009 suggestion confirmation cannot be bypassed by `--yes`. No guessed definition or automatic publication edit.

### STD-06: finding identities depend on mechanical message text

Priority medium, first implementation dependency; confidence high.

Files/symbols: `report.py::Finding.identity_key`, `Finding.id`, `_normalize_for_id`, `assign_occurrences`, `Finding.to_dict`; `results.py::_finding_from_dict`, version readers/writer; `ignore.py::IgnoreRules.matches`; `issues.py::eligible`, `filed_ids`, `_finding_item`; `refresh.py::_keep_ai_ids`, `refresh`, `merge_ai_review`; TUI selections.

Evidence: changing only WB403's message changes `3d39c41f0a22` to `0568500b8f1e` in the audit fixture. The current reader discards serialized IDs. Ignore and issue matching compare the recomputed ID.

Proposed first implementation: the schema proposal's optional frozen `identity_anchor`, preserving the old normalized pre-hash anchor, existing hash and occurrence policy. Changed mechanical detectors derive the legacy anchor from their former template with the same subject values. Version 3 persists the anchor; the new reader supports 1/2/3. Existing AI quote anchors remain unchanged. Do not rewrite old issue bodies or suppression files.

Acceptance:

- Pre-change fixture results, fresh checks after a wording change, and version-3 round-trips have identical IDs for the same observations.
- A configured ID ignore still applies with no prior results file. An old hidden marker from an open or closed issue still prevents refiling.
- Changing a line or unquoted count retains existing behavior; changing a quoted subject, file or rule remains distinguishable.
- Duplicate occurrence numbers remain stable before filtering; an ignored duplicate's ID never transfers to a retained sibling. Partial refresh and retained AI IDs keep their existing tests.
- Old versions reject version 3 clearly; document downgrade recovery. New readers validate anchors as strings and surface damaged data recoverably.
- Fix planning still works with old and new persisted findings. No blanket old-to-new alias that treats all occurrences of one rule as equivalent.

This bridge is deliberately small. A new semantic identity algorithm or aggregate-to-per-challenge migration requires a separate compatibility design. Metadata-only additions should not change IDs.

### STD-07: objective list parsing changes the result

Priority medium; confidence high.

Files/symbols: `lesson_check.py::_check_objective_verbs` and top-level objective extraction; dependent `check_episode` WB403; WB401/WB402 rules. Tests: `test_lesson_check.py`.

Evidence: five `+ Understand topic N` bullets produce count zero and no WB401/WB402. Existing extraction accepts only `-`/`*` and counts nested items. [CLDT episode objectives](https://carpentries.github.io/lesson-development-training/episodes.html#defining-episode-level-learning-objectives) concern objectives, not a particular Markdown marker.

Proposed change: extract top-level list items within recognized objectives blocks, with equivalent handling of unordered and ordered markers and wrapped text. Count nested explanatory bullets as part of their parent. Preserve source positions. Do not equate replacing a verb with measurable learning.

Acceptance: equivalent `-`, `*`, `+`, numbered and wrapped objective fixtures produce equivalent counts and source locations; nested supporting bullets do not add objectives. Code examples and other divs remain excluded. New WB403 warnings from previously missed objectives are an intentional coverage change and should be noted in release notes, including potential `--fail-on warning` effects. WB402 remains info.

### STD-08: contraction threshold and prose context

Priority low; confidence high for the quote/data fixture, not for every English-language edge case.

Files/symbols: `lesson_check.py::_check_contractions`; `rules.py` WB404; `test_lesson_check.py`.

Evidence: a blockquote of five dataset values `don't` triggers the local count/rate threshold. The hint already acknowledges the threshold is local. [Lab Accessibility](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md#accessibility) discusses extensive use, without setting this number.

Proposed change: keep info severity and explicitly frame the signal as a prose review. Exclude unambiguous quoted blocks when adding syntax-aware scope, preserve literal data/code/proper names, and document unresolved inline ambiguity. Do not turn English prose conventions into a ban for translated lessons.

Acceptance: supported code exclusions remain; quoted dataset fixture does not trigger a recommendation to alter its values; an equivalent author-prose fixture can trigger. Token denominator and threshold remain documented, with no unexplained score. No automatic expansion of contractions.

### STD-09: wrong config section and closing-fence instruction

Priority low; confidence high. Independent quick correction.

Files/symbols: `rules.py::G_CONFIG`, `G_FENCED_DIVS` and WB203 rationale; `lesson_check.py::_check_divs` WB203 hint; `tests/test_rules.py`, `test_lesson_check.py`.

Evidence: `G_CONFIG` currently points to `episodes.html#configuration`, while configuration is on [Editing a lesson](https://carpentries.github.io/sandpaper-docs/editing.html#configyaml). WB203's hint requires matching/exceeding opening fence length; Workbench's callout explanation says length need not match.

Acceptance: source links target the relevant passage; short valid closing fences do not prompt a longer fence. Keep the explicit-close recommendation because the tested pegboard behavior differs from standalone Pandoc EOF closure. No severity or detector change is needed for this patch. Changing guide reachability alone is not adequate semantic validation.

### STD-11: AI review evidence boundaries

Priority medium; confidence high for the input/verification limits, not for live model accuracy.

Files/symbols: `ai_review.py::INSTRUCTIONS`, `build_system_prompt`, `build_glossary_block`, `build_user_prompt`, `locate_quote`, `to_findings`; `rules.py` AI201–AI208; `console.py`, `tui.py::_update_detail`, `report.py`, `issues.py::_body`; `checker/rubric/`.

Evidence: a mocked AI208 finding contains a matching arithmetic quote but a deliberately false suggested correction; `to_findings` retains it. That is expected anchoring behavior. The actual input has episode text, glossary and mechanical findings; it lacks figure pixels, execution results and the learner profile. [Lab review scope](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md#review-scope) is broader than these inputs.

Proposed change: consistently label judgment as AI assistance and quote matching as anchoring only. AI203 should ask an audience/prerequisite question when context is missing; AI207 cannot assert measured contrast or seen image content; AI208 needs verification. Preserve the existing issue caveat rather than duplicating it. Change the prompt's assertion that lesson-wide items “are reviewed separately” if no such review actually runs.

Acceptance: mock quote validation still accepts/rejects anchors correctly but every view distinguishes this from correctness. Unsupported visual/execution claims are not encouraged by prompts. An empty local glossary context does not assert global absence. Stale AI findings remain unfileable even if explicitly selected; changed model wording does not change quote-based IDs. No auto-application of AI suggestions.

CONTRIBUTING asks for a real episode review when prompts/rubric change. Deterministic tests alone cannot close that requirement: during implementation, arrange an authorized, recorded live comparison or mark model-behavior evaluation pending. Do not run paid calls as part of this review handoff.

### STD-12: invalid timing values pass the numeric test

Priority low; confidence high for the reproduced Python/YAML values. Newly named here from the audit's existing coverage evidence.

Files/symbols: `lesson_check.py::_check_front_matter`, `_split_front_matter`, `check_config`; `rules.py` WB104; `test_lesson_check.py`.

Evidence: `teaching=float('nan')`, `exercises=True` returns no finding. Python booleans are integers; nonfinite and negative values can bypass intended numeric-minute checks. The author's numeric timing contract does not imply that every Python number is useful timing.

Proposed change: explicitly accept finite nonnegative nonboolean numbers; retain legitimate zero and fractional minutes. Label that validation boundary as checker interpretation of meaningful durations, not a quoted integer-only Carpentries rule. Check falsey non-mapping YAML and malformed episode-list types separately before broadening this patch.

Acceptance: YAML `true`, `.nan`, `.inf`, negatives and quoted numeric strings receive bounded WB104 advice; ordinary integers, zero and fractions behave as documented. Skip dependent sum/zero-assessment suggestions for invalid durations. Preserve warning severity; expanded coverage can affect explicit `--fail-on warning`, so document it. No automatic time replacement.

## Design recommendations requiring explicit behavior decisions

### STD-10: WB213's automatic fix chooses editorial intent

Priority medium; confidence high that multiple repairs are possible. This is a safety-policy recommendation, not proof that every existing fix is wrong.

Files/symbols: `fix.py::SAFE_FIX_CODES`, `SUGGESTION_CODES`, `_fix_wb213`, `plan_autofixes`; `app.py::fix`; rule-help capability lookup; `test_fix.py`, `test_quick_wins.py`.

A jump from H2 to H4 could be fixed by lowering H4 or by adding a missing H3. Move WB213 to individually confirmed suggestions unless a narrower automatic eligibility condition is justified. Preserve source-match/diff guards. Acceptance: `fix --apply --yes` does not change WB213; the editorial path presents the alternative and requires individual confirmation. WB103's guarded singular-key rename remains automatic. Announce the changed safe-fix set; no diagnostic severity change is implied.

### DES-01: validated rule/reference metadata and offline help

Implement the field dictionary in the schema proposal, preserving code/name and legacy serialized categories. Proposed files: extend `rules.py`; add `checker/help.py` only for shared help content; expose `explain`/`rules` in `app.py`. Add a compatibility `guides` projection; do not duplicate source metadata across rules and findings.

Acceptance: all 48 entries have supported metadata and references with manual check dates; AST-emitted codes and AI AREA_CODES agree with the registry; no duplicate code/name or unknown related rule. Existing source-provenance uncertainty is represented as unpinned, not filled with a fabricated commit. Offline installed commands work without results, models or network. WB012 is identified as operational. AI severities retain current allowed warning/info behavior. No profile automatically changes `--fail-on`.

Keep fix availability derived from actual fix handlers; static help cannot promise that a fix exists for every occurrence. Help must state exceptions, practical limits, next action and exact source section, following the proposal's six examples.

### DES-02: consistent rendering and TUI help

Files/symbols: `console.py::render_findings`, `report.py::render_terminal`, `render_markdown`, JSON adapters, `issues.py::_finding_item`, `_body`, `tui.py::FindingsApp._update_detail` and bindings. Add helper tests alongside `test_app.py`, `test_report.py`, `test_issues.py`, `test_tui.py`.

Acceptance: default output has readable severity/code/location/observation/action, with no color-only meaning. The long explanation is reused once per rule in reports/issues. Static Markdown/PDF retain expanded content and usable source URLs. Literal lesson/AI text cannot become terminal markup. Existing issue IDs, grouping, confirmation and eligibility remain unchanged.

Proposed F1 help does not collide with current listed app bindings. Verify terminal/framework bindings too. A modal must restore finding row, selection, scroll and input focus; Escape closes help without clearing underlying filters. Test no-row state, search typing and keyboard scrolling with installed Textual 8.2.8; do an actual terminal pass. The CLI remains an accessible alternative. Do not call a new layout necessary for explanatory help.

### DES-03: WB012 and operational errors

Files/symbols: `lesson_check.py::run_checks`, `app.py::_refresh`, `check`, `_episode_view`, `_fails`; `refresh.py::refresh`; result serialization and command tests.

The invalid episode selection is currently an error Finding and can be subject to suppression/`--fail-on never`. In a separate change, return an invocation error with status 2 before persisting a new quality result, keeping the previous result intact. Preserve the WB012 code as legacy documentation and reader support; do not reuse it.

Acceptance: unknown episode exits 2 even with `--fail-on never`; it does not overwrite an earlier useful result or appear as a lesson-quality issue. Valid partial checks retain their current scope labels, merging and exit thresholds. Explicitly announce this exit/serialization-policy change. Leave current behavior in place during metadata-only work.

## Open questions, not instructions to assume an answer

| ID | Question | Evidence required before implementation |
|---|---|---|
| OPEN-01 | Which class combinations/orders does the supported Workbench version recognize as components and required blocks? | Compare `.custom .questions`, `.questions .custom`, IDs/attributes, nesting and indentation through actual pegboard/sandpaper rendering. Pandoc retention alone is insufficient. |
| OPEN-02 | How should aggregate WB205 IDs transition to per-challenge findings? | A design covering ignored aggregates, closed issues, duplicate challenge text and refresh; no blanket alias that suppresses unrelated new findings. |
| OPEN-03 | How broad should alternate glossary discovery be? | Check `.Rmd`, configured support pages and direct definition links. Recognizing a link is not proof it defines all terms; ordinary checks stay offline. |
| OPEN-04 | Should heuristic scaffold matches remain errors? | Explicit default-policy decision with author fixtures and `--fail-on` regression expectations. Do not lower severity silently because authority becomes checker-policy. |
| OPEN-05 | Does current rendering actually use `created` for citation metadata as WB005 claims? | Trace the supported renderer/source version before retaining that causal rationale. Missing-date advice can remain qualified. |
| OPEN-06 | How well do AI judgments match expert author review? | An evaluation set and authorized live comparisons, with disagreements recorded. Quote validation and 337 passing tests do not answer it. |

Do not automate pilot completion, incorporation of feedback, accessibility compliance, or Carpentries approval. Optional profiles are deferred; a human teaching-readiness checklist must not become a numeric score.

## Regression and release checklist

1. Registry/source structure: exact current code coverage, metadata completeness, declared defaults versus emitted severities, reference keys/provenance, related-rule integrity. A separate network maintenance check tests link reachability, not source support.
2. Known exceptions: all fixtures listed above, plus support-page versus episode applicability, discussion alternatives, code/quote/data syntax and language scope.
3. Compatibility: version 1/2 load and version 3 round-trip; old/new IDs; ignores with no cached results; issue deduplication for closed and open markers; retained AI occurrences; dirty links; partial and changed-file scopes.
4. Fix paths: singular-key WB103 guards; source changed since check; comments; existing plural key; editorial confirmations; old message-based saved findings remain understandable. No educational rewrite under a safe-fix flag.
5. Renderers/help: one content source, plain URLs, narrow/monochrome output, unknown codes, old/codeless findings, static appendix, no AI/network imports in core help. Wheel smoke test outside repository.
6. TUI: focus/selection restoration, Escape isolation, modal scroll, no-row state, ordinary search text, stale AI filing rejection and external changes during filing.
7. Release notes list changed parser coverage, safe-fix set, persisted-result version, and any explicit exit/default decisions. A wording-only correction must not be described as new validation authority.

## Verification available to the implementer

At the same reviewed HEAD, the resumed evaluation independently reran:

- `.pixi/envs/default/bin/python -m pytest tests/ -q`: **337 passed in 30.60s**.
- `.pixi/envs/default/bin/ruff check checker tests`: **passed**.
- Installed `wbcheck --help`: confirmed current command set; no `explain` or catalog command exists yet.
- Temporary detector/Pandoc fixtures: reproduced explicit-alt/decorative false positives, duplicate anchors with suffixes, global solution-count masking, zero-time overstatement, plus-marker objective omission, quoted contraction trigger, local-glossary limitation, class-order limitation, invalid timing acceptance and changed message IDs. Registry enumeration again found 48 codes with no missing or unused entries.
- Source rechecks: Workbench author docs, CLDT episodes/assessment/writing, Lab editor/reviewer guides, pegboard headings, Pandoc, Carpentries communications/developer docs, Ruff and Typer/Textual primary documentation. The CLDT objectives page failed one repeat tool fetch; retain the earlier audit evidence and retry before changing that citation, rather than claiming the source disappeared.

The prior audit additionally records local R/pegboard and CLI fix/recheck experiments; those were not all repeated in this continuation. Temporary scripts are disposable; essential fixture inputs and observed behavior are written in the audit. Earlier `pixi run` commands failed before executing tasks with a macOS Rust system-configuration error; direct installed executables worked. No production changes, commits, pushes, issue writes, live model review, full site build, PDF visual audit or new TUI implementation occurred in this evaluation.
