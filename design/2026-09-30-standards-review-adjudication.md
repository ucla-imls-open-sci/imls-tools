# Adjudication: review of the standards-review implementation (2026-09-30)

An external review of the uncommitted `standards-review` working tree (base
`9032b05`) was pasted into the session. It raised four findings (REV-01 to REV-04). Its
closing sections, pasted separately, confirmed the implementation's URL
corrections to the audit (`objectives.html#smart-objectives`, not
`learning-objectives.html`; `editing.html#config-yaml`, not `#configyaml`)
and requested no further production changes.

| ID | Finding | Verified | Verdict | Fix |
|---|---|---|---|---|
| REV-01 (P1) | Dropping nested WB401 bullets, or newly counting `+`/numbered objectives, moved 0.2.1 occurrence IDs between findings | Reproduced exactly: both fixtures gave the reviewer's IDs on the branch and on 0.2.1 | Adopt | `_check_objective_verbs` replays 0.2.1's WB401 detection (any `-`/`*` line in the block) and occurrence count, so a finding 0.2.1 also made keeps its exact ID and a skipped nested bullet keeps its slot. A `+`/numbered objective gets an anchor 0.2.1 couldn't produce (`...|v3`), so it can't take a legacy slot. Tests: both fixtures, plus fresh checks with old-ID ignores and no saved results |
| REV-02 (P2) | `alt` matched inside another attribute's value (`title="Example alt='text'"`) | Reproduced: no WB301 | Adopt | Attribute text is tokenized into key/value pairs honouring quotes and backslash escapes; only an `alt` key counts. The brace scanner also honours escaped quotes. Tests: alt-like text in title/data values, escaped quote, genuine alt after a quoted title |
| REV-03 (P2) | TUI detail showed the rule's default severity where an `info` AI finding sits under a `warning`-default rule | Confirmed by code | Adopt | The detail header shows the finding's own severity word; the rule line says "default severity warning". `RuleHelp.labels` now reads "warning (default)". Test: an info AI208 finding |
| REV-04 (P2) | TUI help test failed where Textual captured output wrapped the text | Not reproduced here (passed at default and 40 columns), but the dependence on the app's captured console is real | Adopt | The test renders the pane with its own fixed-width console into a buffer and compares whitespace-normalized text; content assertions (explanation, full URL) unchanged |

Separately found while checking REV-04: at `COLUMNS=40`, three older tests
(`test_report_keeps_bracketed_hint_text`, `test_issues_create_files_labels_then_is_idempotent`,
`test_shell_completion_is_offered`) fail on `main` too, because Rich wraps CLI
output. Pre-existing, not caused by this branch; worth a follow-up.

After the fixes: 492 tests pass, ruff clean; the 0.2.1 golden fixture and five
real lessons (scratch copies) keep every surviving finding's 0.2.1 ID.

Also from the review's closing notes: `scripts/check_wheel.py` takes its
expected file list from `git ls-files checker`, so a new module like
`checker/help.py` is covered once it's staged (not only once committed). The
declared deferrals (WB213 fix policy, WB012 exit behaviour, TUI F1 help,
per-challenge WB205, div class order, the `created` citation question) and the
pending live AI prompt evaluation stand as listed in the CHANGELOG.
