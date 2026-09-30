# Adjudication: Codex review round 2 (2026-09-30)

Review captured in `2026-09-30-codex-review-wbcheck.md`. Checked against
`8f78f8e`. "Code" means confirmed by reading the cited path; "live" means
reproduced on a copy of lc-open-hw.

| # | Finding | Verified | Verdict | Severity |
|---|---|---|---|---|
| 1 | Stale AI finding filed via TUI selection | code: `_plan_issues` selection branch filters only `already`; `issues.py:197` stale filter applies only to `plan_issues` | Adopt | High (agree) |
| 2 | `check --episode` counts other episodes | live: full check exit 1, `--episode annex.md` exit 1 and lists lesson2-5 findings | Adopt; regression from `cfa7205` | Medium (agree) |
| 3 | `[]` results file crashes `check` | live: `AttributeError: 'list' object has no attribute 'get'` | Adopt | Medium (agree) |
| 4 | AI IDs reassigned after ignore | code: `refresh()` keeps only `kept`, so the ignored sibling is gone from the saved set; next refresh `assign_occurrences(ai)` renumbers the survivor to 0, the ignored ID | Adopt. Also contradicts the README's "IDs are never reassigned" | Medium (agree) |
| 5a | Ignore during pending gh lookup | code: `_plan_issues` captures the selection list at start, no revalidation in `_confirm_issues` | Adopt, small fix | Low (window is the ~1 s gh lookup) |
| 5b | Hidden selections stay eligible | code | Partly adopt: keep persistent selection (intentional), but the confirm dialog should list included findings and say how many are hidden | Low |
| 6 | Partial results report as clean | code: `console.py`/`report.py` never read `results.scope` | Adopt | Medium (agree) |
| 7 | Missing editor kills TUI | code: bare `subprocess.run` in `action_open_editor` | Adopt | Low (`doctor` flags `$EDITOR`; cheap fix anyway) |
| O1 | 80x24 sidebar | not verified | Defer to backlog | - |
| O2 | Search count lags | not verified, plausible | Adopt when touching TUI | - |
| O3 | README AI claims overstated | agree on reading | Adopt in PR #46: "can't carry operator authority" is too strong | - |

Not adopted: nothing rejected outright. The pixi `system-configuration`
panic is specific to Codex's sandbox; `pixi run test` passes here (310).

## Plan

One issue per PR, in the reviewer's order:

1. Issue eligibility in one place (`issues.py`), used by both TUI branches
   and revalidated in `_confirm_issues` against current results (1, 5a, 5b).
   Pilot test: review, edit, recheck, select stale, `c`; writer gets nothing.
2. Invocation scope vs saved scope: `check --episode` shows and exits on the
   checked episode only; reports and TUI header show partial scope (2, 6).
3. AI identity: keep ignored findings' identities reserved (or preserve
   retained occurrences) so a survivor never inherits an ignored ID (4).
4. Robustness: validate results shape into one `ResultsFormatError`,
   `check` warns and rebuilds, read-only commands explain; atomic write;
   editor launch errors caught in the TUI (3, 7).

No release tag until 1 and 2 are merged.
