# Review of standards-review implementation

Reviewed 2026-09-30 against the uncommitted `standards-review` working tree, based on `9032b056c2a3a18a12068f9db1e6c7a7c7e5136e`. Review only: no implementation/test changes, commits or external writes. The four preceding design documents were left unchanged.

## Verdict

The implementation addresses much of the handoff: offline help, shared rule metadata, bounded wording, result-version handling and several detector exceptions are present. Fix the occurrence-identity regression before relying on the compatibility claim. Three other reproducible issues are below. This review does not reject the deliberately deferred work or claim live AI behavior was evaluated.

## Findings

### REV-01 [P1]: objective filtering can transfer a retired ID to a surviving finding

Location: `checker/lesson_check.py::_check_objective_verbs`, lines 802–825; interaction with `checker/report.py::assign_occurrences`.

The new nested-item filter drops old WB401 occurrences without reserving their legacy identity slots. Conversely, newly recognized `+` or numbered objectives can consume the old ID of a later `-` objective. The image and heading migrations track legacy occurrences, but WB401 does not.

Reproduction, using the same `episodes/a.md` location for the baseline and current helper, followed by `assign_occurrences`:

```markdown
::: objectives
- Explain the workflow
  - Understand data
- Understand data
:::
```

| Version | Source line | ID |
|---|---:|---|
| 0.2.1 | 3, nested item | `cc83a9a971e1` |
| 0.2.1 | 4, top-level item | `3c4e43f7ac85` |
| Current | 4, top-level item | `cc83a9a971e1` |

An `IgnoreRules(ids={"cc83a9a971e1"})` that formerly ignored only the nested item now suppresses the surviving top-level objective. An old issue marker similarly matches the wrong occurrence, while the surviving objective loses its previous ID.

The inverse case is also reproduced:

```markdown
::: objectives
+ Understand data

- Understand data
:::
```

Previously only line 4 was reported, with `cc83a9a971e1`. Now line 2 takes that ID and line 4 becomes `3c4e43f7ac85`. The golden fixture uses different nested and top-level text, so it does not exercise either collision.

Requested correction: preserve 0.2.1 occurrence identities for legacy-detectable WB401 subjects before filtering nested bullets. Give newly supported marker occurrences identities that cannot steal a legacy occurrence's slot. Base grouping on the same normalized identity material as the old algorithm, not merely raw source text. Add both fixtures to the golden/ignore/issue tests, including a fresh check with no saved results. Do not solve this by assigning a single ID to all occurrences of an objective.

### REV-02 [P2]: the alt detector matches text inside another attribute's value

Location: `checker/lesson_check.py::_explicit_alt`, lines 284–292; `_ALT_ATTR_RE`, line 261.

`_image_attributes` finds the attribute block with quote awareness, but `_explicit_alt` then searches its entire text without respecting attribute-value boundaries. For an existing image file:

```markdown
![](plot.png){title="Example alt='text'"}
```

The checker emits no WB301. Pandoc 3.11 renders:

```html
<p><img src="plot.png" title="Example alt=&#39;text&#39;" /></p>
```

There is no alt attribute or caption. The words in the title have been mistaken for explicit image-description markup.

Requested correction: recognize `alt` only as an attribute key outside other quoted values, including escaped quotes. Test a title/data attribute containing alt-like text, a genuine alt attribute after another quoted value, explicit empty alt and multiline descriptions. Preserve the separate missing-file check. This is a source-syntax false negative, not a claim about the adequacy of any image description.

### REV-03 [P2]: the TUI displays default severity as occurrence severity

Location: `checker/tui.py::FindingsApp._update_detail`, especially line 304; `checker/help.py::RuleHelp.labels`.

`help_.labels` begins with `Rule.default_severity`. AI findings legitimately carry either `info` or `warning`; their rule default is `warning`. A headless TUI fixture with `Finding(severity="info", code="AI208", source="ai", ...)` renders:

```text
● AI208  episodes/a.md:3  [ai]
Consider checking the example.
...
warning · Carpentries review criterion · AI-assisted suggestion · topic: pedagogy
```

The actual severity is info, yet the explicit severity word in the detail is warning. This conflicts with the selection/filtering behavior and the goal of meaning that does not depend on color or symbols.

Requested correction: show `f.severity` explicitly alongside the occurrence. Keep the rule default confined to clearly labeled rule-help text, or label it as “default severity” when showing it in the detail. Add an informational AI finding test, not only the current mechanical warning fixture.

### REV-04 [P2]: the new TUI help test depends on unwrapped rendered output

Location: `tests/test_help.py::test_tui_detail_shows_the_same_explanation`, lines 195–202.

The full suite here returns **482 passed, 1 failed**. Running the failing test alone reproduces it. The explanatory sentence is present but wraps, so line 200's exact contiguous substring assertion fails. The visible URL also wraps inside `formative-assessment.html`, making the later URL assertion width-sensitive. `Console(record=True, width=200)` did not prevent this in the active Textual capture context.

Requested correction: assert shared text content before terminal layout, and separately test presentation at explicit widths; alternatively render through an independent `io.StringIO` console to avoid the app's output capture and make the width contract explicit. Preserve meaningful assertions that the whole explanation and source URL exist. Do not fix this by removing the content assertions or simply widening the test until it happens to pass.

This result does not contradict the earlier reported successful run; it establishes an environment-sensitive failure that should be resolved before treating the suite as reliably green.

## Verified corrections to the original audit

The implementer's URL corrections are right:

- [CLDT SMART objectives](https://carpentries.github.io/lesson-development-training/objectives.html#smart-objectives) is on `objectives.html`, not the audit's `learning-objectives.html`.
- [Workbench config.yaml](https://carpentries.github.io/sandpaper-docs/editing.html#config-yaml) uses `#config-yaml`, not `#configyaml`.

The original audit's URL errors should not be copied into new reference records. The implementation uses the corrected URLs. This review preserves the original design documents as requested rather than silently rewriting their historical evidence.

## Verification and limits

- Inspected implementation diffs, new help/identity/standards tests, fixture coverage, metadata, result readers, suppressions, issue matching and help renderers.
- `.pixi/envs/default/bin/python -m pytest tests/ -q`: **482 passed, 1 failed in 32.00s**.
- Isolated TUI help test: same failure, **1 failed in 1.29s**.
- `.pixi/envs/default/bin/ruff check checker tests`: **passed**.
- Temporary Python probes compared HEAD's detector with the working-tree detector using the same locations and occurrence assignment; reproduced both WB401 identity transfers and their effect on ID ignores.
- Pandoc 3.11 comparison reproduced the false alt detection. A separate next-line attribute experiment did not show a supported Pandoc attribute, so it is not reported as a defect.
- Headless Textual fixture reproduced the AI info/default-warning mismatch. No new interactive-terminal accessibility claim is made.
- No paid/live model review, real-lesson rewrite, full Workbench build or repeat of the implementer's five-lesson/wheel-install study was performed. The reported studies are useful but do not cover the reproductions above.
- The tracked-files-only wheel check limitation is real: `scripts/check_wheel.py` obtains its expected list with `git ls-files checker`. Adding a file to the index is sufficient for that inventory; a commit itself is not technically required. Nothing was staged by this review.

The declared deferrals remain separate: WB213 automatic-fix policy, WB012 invocation-error behavior, new TUI controls, per-challenge WB205, div class-order compatibility and the created-date citation question. Live AI prompt evaluation remains pending under CONTRIBUTING. No additional production changes are requested merely to remove those explicit limitations.
