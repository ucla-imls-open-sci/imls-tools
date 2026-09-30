# Rule metadata and author help proposal

Date: 2026-09-30. Design only, for `wbcheck` 0.2.1 at `9032b056c2a3a18a12068f9db1e6c7a7c7e5136e`. None of the proposed interfaces or fields below is implemented by this review.

Companions: [standards audit](2026-09-30-standards-audit.md) and [implementation handoff](2026-09-30-claude-standards-handoff.md). The audit contains all 48 rule assessments and the source inventory. This document defines the proposed contracts and author experience.

## Decision

Keep stable rule codes and the current commands. Extend the Python rule registry with a small, validated help model; render that same content in an offline `wbcheck explain CODE` command, a catalog, and the existing output surfaces. Keep occurrence evidence and fix decisions out of static rule text.

First correct claims that exceed the detector's evidence. Preserve finding identities before changing mechanical messages. Do not make a TUI redesign or a complete parser replacement a prerequisite.

| Alternative | Advantage | Cost / limitation | Decision |
|---|---|---|---|
| Longer hints at every finding | Small patch; immediately visible | Repeats explanations and exceptions; makes routine output dense | Use only for essential next actions |
| Website-only rule manual | Familiar reference pages | Needs navigation/network; can drift from installed version | Generate later from packaged metadata |
| Shared packaged help plus compact findings | Works offline and across CLI, TUI, reports and issues; one content source | Requires schema validation and renderer adapters | Choose this |
| Profiles, confidence scores and automatic readiness verdicts | Appears to simplify choices | Introduces policy and calibration problems; can imply certification | Defer profiles; do not add scores/verdicts |

Ruff's [rule catalog](https://docs.astral.sh/ruff/rules/) and [F401 help](https://docs.astral.sh/ruff/rules/unused-import/) separate the check, rationale, examples and fix safety. Borrow that information structure. It does not establish wbcheck's authority or which fixes are safe.

## Taxonomy: independent questions

| Dimension | Proposed values | Meaning |
|---|---|---|
| `topic` | `metadata`, `structure`, `accessibility`, `pedagogy`, `prose`, `supporting-material`, `operations` | What an author is working on. One primary topic; related rules handle overlap. |
| `authority` | `technical-requirement`, `review-criterion`, `recommendation`, `checker-policy` | Basis of the practice, not proof that a particular finding is correct. A technical requirement names its environment in applicability. |
| `detection` | `deterministic`, `heuristic`, `ai-assisted`, `human-only` | How the conclusion is reached. A repeatable regex can still be a heuristic for its claimed conclusion. |
| `default_severity` | `error`, `warning`, `info` | Existing default reporting/exit-policy input. Not a measurement of educational quality. |
| `applies_to` | Nonempty tuple of `config`, `episode`, `support-page`, `invocation` | Supported context for this rule. Additional language/stage boundaries are written in `context`. |

Use a single authority for the principal claim. Supporting references can come from other source families, with a note saying what each actually supports. No universal ranking between technical docs, Lab criteria, CLDT advice and communications guidance: their scopes differ.

Examples: WB103 is an episode metadata requirement with a deterministic presence detector. WB403 concerns a review criterion but uses a weak heuristic. WB105 is a recommendation, applied through a timing heuristic. WB404's numerical trigger is checker policy, inspired by language guidance. AI208 addresses a review criterion using AI assistance. `human-only` belongs to future checklist/help content; do not generate synthetic pass/fail findings for it.

WB012 is an invocation problem. In the first metadata release, label it `operations` and preserve its existing behavior. Moving it out of lesson findings and giving it an unconditional invocation-error exit must be a separate announced change.

## Minimal representation

Keep dataclasses in `checker/rules.py`; no YAML schema framework or runtime web loader is needed. The representation below is conceptual. Field names can be adjusted during implementation only with compatible readers and tests.

### Static Rule fields

Required fields have no fallback: missing semantics should fail registry validation in development, not silently become an official requirement.

| Field | Type / default | Requirement and purpose |
|---|---|---|
| `code` | `str`, existing `WBnnn` / `AInnn` | Required. Never renumber or reuse. |
| `name` | unique kebab-case `str` | Required; retain current names even when a legacy name overstates the inference. |
| `title` | short `str` | Required. Topic/action label; not a claim about an individual occurrence. |
| `topic` | enum above | Required. New catalog facet; retain `Finding.category` unchanged for old consumers. |
| `authority` | enum above | Required. Human-readable labels in help. |
| `detection` | enum above | Required. Explain limitations in prose, not a numerical confidence score. |
| `default_severity` | severity enum | Required. Seed from existing detector outputs; do not change them while moving metadata. |
| `severity_reason` | `str` | Required. Explain why this default is useful and what any existing override means. |
| `applies_to` | tuple of page/context enums | Required. Does not activate checks on new file types by itself. |
| `checks` | short paragraph | Required. Exact observation or proxy, including relevant local thresholds. |
| `why` | short paragraph | Required; retain field name. Explain practical relevance without overstating causation. |
| `response` | short paragraph | Required. General author response, distinct from an occurrence-specific `hint`. |
| `references` | tuple of reference keys, default `()` | At least one for external authority; checker policy may have none with the local basis explained in `checks`. |
| `context` | paragraph, default `""` | Optional language, drafting/review-stage and environment boundaries; no automatic lifecycle advancement. |
| `exceptions` | tuple of strings, default `()` | Optional legitimate reasons to retain the content. |
| `limitations` | tuple of strings, default `()` | Optional detector blind spots; mandatory nonempty for heuristic/AI rules by validation. |
| `example` | one string, default `None` | Optional illustrative source/output pair. Do not duplicate a large fixture suite here. |
| `related` | tuple of rule codes, default `()` | Optional; validate all referenced codes. |

Retain explicit occurrence severity for existing AI outputs (`warning` or `info`). The AI rule's proposed default is `warning` as a documented fallback, not a new override of the model's validated choice. No mechanical override exists today; tests should reject accidental disagreements with the registry. If a real conditional mechanical severity emerges, add an explicit documented exception then rather than an unused general policy system now.

Do not add a parallel `category`, `confidence`, `compliance`, `quality_score`, `priority`, or `is_official` field to Rule. They either duplicate another field or suggest certainty the tool does not have. Display order stays separate from metadata authority.

Do not duplicate fix capability in Rule. Provide a single fix-capability lookup owned by `checker/fix.py`, derived from its supported handlers: `none`, `conditional-automatic`, or `editorial`. Help uses that lookup. The concrete fix planner decides whether a fix is available for an occurrence after re-reading the source. WB103 is conditional; WB009/WB401 are editorial; proposed WB213 reclassification is explicitly separate from current behavior.

Do not build deprecation machinery without a retired rule. Reserve all codes; keep help entries for retired codes and state retirement/replacement there. Add a structured lifecycle record when the first actual retirement needs catalog filtering. Do not follow the present registry comment's suggestion to simply delete entries.

### Reusable reference record

Store references once in a small `REFERENCES` mapping beside the registry. One record describes one source section, not an entire multi-purpose site. Rule keys select records in relevance order.

| Field | Type / default | Purpose |
|---|---|---|
| mapping key | unique stable `str` | For example `cldt.episodes.duration`; no mutable title in the key. |
| `title` | required `str` | Source title, not an invented authority label. |
| `section` | required `str` | Human-readable section or opening passage when no heading exists. |
| `url` | required HTTPS `str` | Exact section link where available. |
| `checked_on` | required ISO date `str` | Last manual check that the source supports the claim. |
| `supports` | required short `str` | Scope of support; include a limitation when a threshold or proxy is local. |
| `revision` | optional `str`, `None` | Actual source commit/version if known. `None` displays “live page, unpinned”; a site build-tool version is not a content revision. |

For several rules sharing a source, use a shared section record only when its `supports` statement fits all of them. A live URL check cannot update `checked_on` automatically. Avoid embedding full upstream guides; short paraphrases and links suffice. Keep pinned AI rubric snapshots under `checker/rubric/` with their own provenance; the references catalog should identify those sources rather than pretending the snapshot is live.

### Finding fields and evidence

Retain all current fields: `severity`, `category`, `message`, `location`, `hint`, `line`, `code`, `quote`, `source`, `scope`, `stale`, `occurrence`. Do not rename them in persisted results. A Finding is one observation, not the Rule itself.

Proposed additions, implemented in stages:

- `identity_anchor: str | None = None`: exact pre-hash anchor used to preserve existing identities independently of edited display wording. See migration below.
- `evidence: dict[str, JSON scalar]`, default `{}`: optional small typed-per-rule values needed for explanations/fixes, for example `{"field": "exercises", "declared_value": 0, "objective_count": 1}`. Define allowed keys per emitting rule and validate in tests; do not put arbitrary copies of documents here. Evidence need not exist on legacy results.

`message` states the observed problem or explicitly labeled AI suggestion. `hint` is the next action for this occurrence. `quote` is supporting text, not a truth certificate. `line` remains nullable; never invent a line for an absent element. New WB403 diagnostics should point to the timing field when its source position is known. Missing fields should use a truthful front-matter insertion context or just the filename.

A matched quote is an anchoring status, not a calibrated confidence value. On old saved AI results, say that the quote was matched at review time; preserve stale warnings after source edits. For legacy data without a verifiable provenance path, show the quotation without manufacturing a verification status.

### Concrete conceptual record

```python
Rule(
    code="WB403",
    name="objectives-not-assessed",  # retain the legacy stable name
    title="Review assessment time",
    topic="pedagogy",
    authority="review-criterion",
    detection="heuristic",
    default_severity="warning",
    severity_reason="Review whether declared timing includes assessment; retain the current warning default.",
    applies_to=("episode",),
    checks="An objectives block has counted objectives and exercises is numeric zero.",
    why="Assessment opportunities help instructors notice where learners need support.",
    response="Check the existing assessment opportunities and make the declared timing accurate.",
    references=("cldt.assessments", "lab.reviewer.content"),
    context="Episode source and declared timing, not an observation of teaching.",
    exceptions=("Discussion or another embedded check may already assess the objectives.",),
    limitations=("Zero exercise time does not establish that assessment is absent.",),
    related=("WB104", "AI201", "AI202"),
)
```

The proposed field dictionary, not this illustrative constructor, is the implementation contract. No `fix` key is copied into the Rule: the fix registry reports `none` for WB403.

## One content model, several views

Introduce a small renderer-independent helper (proposed `checker/help.py`) that resolves a Rule and its references into ordered text sections. Keep Rich, Textual and Markdown rendering outside that helper. It returns content, not terminal markup. Treat source text and AI output as literal content and escape them for each destination.

Content order:

1. Rule code/title; human-readable authority, detection and severity labels.
2. What the check observes.
3. Why it matters and what to do next.
4. When retaining the content is reasonable.
5. Limits of the check.
6. Example, fix capability, sources with section/provenance, related rules.

Compact diagnostics retain location, severity word, code, observation and one action. If space is tight, put the action on the next line. Repeat the long explanation once per rule, not once per occurrence. Use “Next” or “Consider” instead of labeling every hint “Fix”.

### Proposed commands

```text
wbcheck explain WB403
wbcheck rules
wbcheck rules --search assessment
wbcheck rules --topic pedagogy
```

These are additions to the existing Typer commands, which were inspected with `wbcheck --help`. `explain` needs neither a lesson directory nor saved results, AI packages, network, `gh`, or Quarto. It exits 0 for a known rule, 2 for an unknown code with a useful catalog suggestion. Accept case-insensitive codes, render the canonical uppercase code. `rules` lists code/title/topic and accepts case-insensitive searches over names and explanation text. Do not add JSON formats or dozens of filters in the first release unless a consumer needs them.

Append one line to normal CLI output: `For context and exceptions: wbcheck explain CODE`. Show actual severity words, not only icons. Keep an ordinary URL visible in expanded help even when OSC 8 terminal links are supported. Current source excerpts under `check --source`, changed-file filtering and editor quickfix are already useful; retain them.

### Proposed TUI behavior

The existing bindings are Space/select, `i`/ignore, `o`/open, `c`/file issues, `s`/severity, `a`/source, `/`/search, `r`/recheck, Escape/clear filters and `q`/quit. Its fixed detail pane already holds source and hints. Do not replace these controls.

Add **F1 / Explain rule** for the current row, displayed in the footer. Open a scrollable rule-help modal using the shared content. F1 is a proposal, not an existing binding; verify delivery in supported terminals and keep the CLI alternative available. A focusable “Explain rule” button in the detail pane gives a second keyboard path. Disable the action with no current row.

The modal captures Escape to close without clearing underlying filters. Tab/Shift-Tab reach its controls, arrow/Page Up/Page Down scroll its content, and visible focus is retained in light/dark themes. On closing, restore the prior widget, row by finding ID, selections, filters and table scroll. Test search-input focus so help bindings cannot intercept ordinary typing. Plain source URLs must remain readable/copyable. A future Collapsible widget is optional; do not nest new expandable controls in the first implementation.

These proposals fit [Textual's input/focus model](https://textual.textualize.io/guide/input/) and [testing tools](https://textual.textualize.io/guide/testing/); use the installed Textual 8.2.8 behavior as the test target. Headless tests do not establish screen-reader usability: retain the plain CLI output and do a real keyboard walkthrough before release. [Typer subcommand documentation](https://typer.tiangolo.com/tutorial/subcommands/) supports the proposed separate offline commands.

### Reports and issues

Markdown/HTML/PDF: preserve file-first evidence and current source links. Add one “Rule explanations” appendix for the codes present, linked from each finding. Keep explanations expanded in Markdown/PDF so no information depends on a disclosure widget. Use visible severity text. Full URLs belong in the source appendix for print/plain-text use. Keep ignored counts and partial-result notices.

GitHub issue drafts: retain one explanation per rule and hidden finding-ID markers. Add only the relevant exception/limitation beside the grouped explanation. Preserve the existing AI judgment caveat, stale-finding exclusion and filing confirmation. This design does not authorize filing issues. Do not introduce automatic issue comments or change grouping thresholds.

Historical reports should state their originating checker version; regenerated rule help comes from the currently installed package. No need to duplicate the entire rule catalog into every saved result. Do not silently replace persisted occurrence evidence with a new interpretation while rendering an old file.

## Six before/after examples

All paths, line numbers and example data below are illustrative. “Before” reflects current emitted wording or the stated detector behavior. “After” is proposed. Expanded help sections below are the content to share across interfaces, not a separate manual.

### 1. Technical problem: WB203, unclosed div

Before: the hint says the closing fence must contain the same or more colons than the opener. The detector does not require that, and the author documentation permits different lengths.

```text
episodes/02-data.md:42: error WB203: No closing fence found for this callout.
  Next: Add ::: at the intended end of the callout; check the surrounding nesting.
```

Expanded explanation: A recognized opening div remains on the scanner's stack at the end of the episode. An explicit close protects the intended Workbench structure. A closing fence uses at least three colons; choose its placement by checking which content belongs inside. Standalone Pandoc accepts end-of-document closure, but the tested pegboard parser does not. Code examples should remain inside code fences. Unsupported Markdown contexts can confuse the scanner.

Schema: `topic=structure`, `authority=technical-requirement`, `detection=deterministic`, `default_severity=error`, `applies_to=(episode,)`, evidence `div_class=callout`. The authority is Workbench compatibility, not a universal Pandoc grammar claim. Reference: [Workbench callout blocks](https://carpentries.github.io/sandpaper-docs/episodes.html#callout-blocks); audit P/PG experiment for the parser difference. Automatic fix: **none**; the intended boundary cannot be inferred safely.

### 2. Recommendation: WB105, timing

Before: reports duration outside the 20–60-minute range; the hint already says it is not a hard rule. Preserve that qualification.

```text
episodes/01-welcome.md: info WB105: Declared teaching and exercise time totals 12 minutes.
  Consider: Keep this if it fits an introduction; otherwise review the episode's scope.
```

Expanded explanation: The check adds declared teaching and exercise minutes; it does not measure a workshop. CLDT uses 20–60 minutes as typical episode scope. A welcome, recap, or deliberately short activity may reasonably differ. Check the purpose and pilot experience before splitting, expanding, or changing the time. Do not invent content just to meet the range.

Schema: `topic=pedagogy`, `authority=recommendation`, `detection=heuristic`, `default_severity=info`, `applies_to=(episode,)`, evidence `teaching=7`, `exercises=5`, `total=12`. Source: [CLDT Episodes, opening and planning](https://carpentries.github.io/lesson-development-training/episodes.html#planning-your-episodes). Automatic fix: **none**. Keep its current non-blocking default. WB402 should use the same framing for objective count, after its list extraction is repaired.

### 3. Review criterion with a proxy: WB205

Before: `2 challenge(s) but only 1 solution(s)`. Global counts cannot identify which exercise needs guidance, and equal counts can hide a gap.

```text
episodes/03-choices.md: info WB205: Found 2 challenge blocks and 1 solution block.
  Next: Review guidance for each exercise; discussions may not need a solution block.
```

Expanded explanation: The current check compares totals across the episode. Inspect each exercise's intended feedback; suitable guidance need not be a single worked answer. Lab editor guidance makes a discussion exception and permits guidance where a unique solution is infeasible. Extra solutions for one challenge can conceal another challenge with none. Do not attach this aggregate finding to a guessed challenge line.

Schema: `topic=pedagogy`, `authority=review-criterion`, `detection=heuristic`, `default_severity=info`, `applies_to=(episode,)`, evidence `challenge_count=2`, `solution_count=1`. References: [Lab editor Content](https://github.com/carpentries-lab/reviews/blob/main/docs/editor_guide.md#content) and [Notes](https://github.com/carpentries-lab/reviews/blob/main/docs/editor_guide.md#notes). Automatic fix: **none**.

A later ancestry-aware detector can say “No nested solution block was found for this challenge; check whether guidance is supplied elsewhere.” It must still permit appropriate alternatives. That is a detector and identity migration, not just new wording.

### 4. Weak inference: WB403

Before: `1 objective(s) declared but exercises: 0 -- nothing in this episode formally assesses them`.

```text
episodes/03-choices.md:4: warning WB403: exercises is 0; this episode declares an objective.
  Next: Check that assessment opportunities are included and their timing is accurate.
```

Expanded explanation: A counted objective and zero exercise minutes prompt a timing/alignment review. They do not prove the absence of assessment. A discussion, check-in or other embedded activity may already provide feedback. If it does, update the timing only when that reflects how the episode is taught. If not, consider an appropriate assessment opportunity. Positive exercise time also does not prove that objectives are assessed.

Schema: as in the full WB403 example above; evidence `field=exercises`, `declared_value=0`, `objective_count=1`. Source: [CLDT Assessments](https://carpentries.github.io/lesson-development-training/formative-assessment.html#assessments), with the [Lab Content criterion](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md#content). Automatic fix: **none**. The proposed warning preserves current severity; no new CI policy.

### 5. Local threshold: WB404

Before: `5 contractions found (147.1 per 1,000 words)` with a hint suggesting expansion. The hint already labels its threshold local; retain that fact prominently.

```text
episodes/04-text.md:17: info WB404: Found 5 contraction-like matches in the scanned text.
  Consider: Review author prose for translation clarity; preserve quoted data and literal values.
```

Expanded explanation: This is an English-pattern scan, triggered by at least five matches and a rate of at least five per 1,000 whitespace tokens. That numerical rule is wbcheck policy. The source guidance raises a contextual language concern, not this count. Code is already excluded in supported contexts; quotations, dataset values, proper names and translations still require care. Do not mechanically expand every match. Exclude clearly identified block quotations in a focused follow-up, documenting that heuristic's own limits.

Schema: `topic=prose`, `authority=checker-policy`, `detection=heuristic`, `default_severity=info`, `applies_to=(episode,)`, `context=English author prose`, evidence `matches=5`, `rate_per_1000=147.1`. Source: [Lab reviewer Accessibility](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md#accessibility); its concern supports discussion, not the threshold. Automatic fix: **none**. An inline quotation outside a recognized quote block is not reliably classifiable as prose versus data.

### 6. AI-assisted judgment: AI208

Before: the model's `problem` text is the displayed message, without a guaranteed uncertainty prefix in all views. A quote match can retain an incorrect criticism, as the audit's arithmetic counterexample demonstrates.

```text
episodes/05-filter.md:33: warning AI208: AI suggests checking the claim about rows returned.
  Evidence: "This keeps every row with a missing value."
  Next: Run the example on data containing a missing value and compare the result.
  Quote matched at review time; the criticism has not been independently verified.
```

Expanded explanation: This is a model suggestion anchored to source text. The checker did not execute the example or verify the domain claim. A quote can be correct while the criticism is wrong. Check the example in its actual environment or consult a relevant authoritative source; retain the original if it is correct. Account for version-specific behavior and missing context. A stale review requires a new review before filing.

Schema: `topic=pedagogy` (content accuracy in this small topic set), `authority=review-criterion`, `detection=ai-assisted`, `default_severity=warning`, `applies_to=(episode,)`. Occurrence `source=ai`, `quote` and `severity=warning` remain; informational AI outputs remain allowed. Reference: [Lab reviewer Content](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md#content). Automatic fix: **none**. Do not weaken `locate_quote` or imply that normalized quote matching validates the reasoning.

## Compatibility before copy editing

### Minimum identity-preserving change

Today a mechanical ID hashes rule/category + location + normalized message + occurrence. AI uses a normalized quoted-text anchor. Lines and unquoted counts are normalized out. Serialized IDs are discarded by the current results reader and recomputed. Consequently, storing yesterday's ID alone will not preserve it on a fresh check.

For a bounded first implementation:

1. Add `identity_anchor` as an optional frozen **pre-hash** anchor. `identity_key` uses it when present, otherwise the existing mechanical/AI algorithm. Keep the hash, code, path and occurrence rules exactly the same.
2. At each mechanical detector whose message changes, compute its anchor from the previous message template and current subject values using the existing normalizer. Treat that template as a compatibility constant, not display text. Test old/new hash equality. Do not put the code/path/occurrence twice into the anchor.
3. When reading versions 1/2, compute the old anchor from the stored message (or quote for AI) before applying any display transformation. Preserve saved occurrence values. Do not trust an arbitrary serialized `id` over its validated inputs.
4. Write results version 3 when the new field is used. New code reads 1, 2 and 3. The old reader must reject 3 clearly rather than silently recomputing wrong IDs from new wording. Describe this downgrade limitation and existing rebuild advice.
5. Keep the same IDs in `.wbcheck.toml`, issue markers and TUI selections. Current ignore/issue comparisons need not change if equality is genuinely preserved. Test them end-to-end with pre-change fixture data, including closed issues and absent results files.
6. Keep existing AI quote-based IDs and occurrence assignment before filtering. Do not renumber retained duplicate AI findings during a partial refresh.

This is a small compatibility bridge, not an ideal permanent identity design. A detector that splits one aggregate finding into several findings needs a separate contract. Never reuse one old ignored ID for a semantically unrelated new occurrence. For WB205 ancestry work, defer release until legacy aggregate ignores/issue markers have an explicit transition policy and tests. A later semantic-anchor system can introduce alias matching, but do not combine that redesign with initial prose corrections.

Presentation-only corrections to `Rule.title`, `why`, guide references, or hints can land first without changing current IDs. Tests still need to check fix handlers: `_fix_wb103`, `_fix_wb213`, `_fix_wb401` and `_fix_wb009` inspect finding wording or source context. Move extraction to validated evidence incrementally, with a legacy fallback while supported saved formats exist.

### Rule/Guide migration

- Extend Rule additively and populate metadata for all 48 codes from the audit; preserve codes and names. Topic is a new catalog concept, not a mass rewrite of legacy categories.
- Keep `Rule.guides` as a compatibility property projecting reference records to `(label, url)` tuples. Preserve `Finding.guides` and serialized guide dictionaries for existing clients.
- Build validation first: unique codes/names, nonempty required fields, valid references, exact expected current severities, known related codes, meaningful limitations for proxies, and all emitted codes registered.
- Move default severity ownership into Rule only after tests demonstrate identical emitted severity. Authority must never select severity automatically.
- Use one help builder for CLI, TUI and static appendices; retain a literal legacy fallback for unknown/codeless old findings.
- No network or AI imports in help. Dataclass metadata is packaged with `checker`; any additional resources need wheel-install/offline smoke tests from outside the checkout.

## First release and deferred work

First release: preserve identities; correct observation/action wording and precise references; add validated registry help, `explain`, a searchable catalog, and shared report/issue explanations. Add TUI F1 after the content contract is stable. Parser corrections with independent fixtures may land separately. Keep severity defaults and selected rules unchanged.

Defer lesson-stage profiles, automatic lifecycle hints, TUI layout redesign, semantic-ID replacement, multi-rule suppression reasons, a hosted documentation site and new quality checks. Existing suppressions already work; explain them before expanding configuration.

Profiles could later offer explicit check selections such as technical checks or Lab preparation. Any profile must list included and excluded rules, retain explicit `--fail-on`, record the selection in results, and state that it is not certification. “Teaching readiness” should be a human checklist label, never a computed passing grade. Profiles are not required for this proposal.

## Maintenance and acceptance

- Generate a Markdown catalog from the registry when needed; validate generated content in CI rather than hand-maintaining parallel explanations in README and a website.
- Normal tests check references structurally and render help offline. A separate maintainer task can check links and flag changed upstream content before a release or at a chosen review interval. Only a manual semantic review advances `checked_on`.
- Test both positive and exception fixtures, source excerpts with literal brackets/Markdown, monochrome and narrow output, unchanged exit thresholds, version 1/2 reads, version 3 round-trips, matching issue markers, and identical help sections across views.
- Test installed offline `explain`/`rules` in a clean core environment, not only the developer checkout.
- Use Textual Pilot for focus restoration, Escape isolation, scrolling, search focus and no-row behavior. Follow with a real terminal keyboard pass. Do not call the UI accessible merely because the widget tests pass.
- Sources were checked on 2026-09-30; the audit records provenance and unresolved technical comparisons. No live AI quality evaluation, complete site build or new TUI implementation was performed for this design.
