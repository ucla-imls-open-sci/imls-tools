# External review: Codex on wbcheck, round 2 (2026-09-30)

Source: an OpenAI Codex review of branch `readme-tighten` at `8f78f8e`,
range `7a3ec91..8f78f8e` (PRs #42, #43, #45, #46), pasted back into the
session. Adjudication is in
`2026-09-30-validation-capture-codex-review.md`.

## Summary as given

A substantial improvement: `--apply`/`--suggest` split, destructive fixes
repaired, target identity and stale tracking, wheel-content CI. Hold a
release for the stale-finding filing bypass and the episode-scoping
regression. Remaining fragility is in transitions between checking, saved
results, and TUI actions, not framework choice.

## Confirmed defects (reviewer's severity)

1. **High: selecting a stale AI finding in the TUI bypasses the filing
   prohibition** (`checker/tui.py` `_plan_issues`). Automatic grouping
   excludes stale findings; the explicit-selection branch only checks
   already-filed IDs.
2. **Medium: `check --episode` reports and fails on other episodes' saved
   findings** (`checker/refresh.py`, `checker/app.py`). Baseline exited 0,
   current exits 1.
3. **Medium: a malformed `results.json` (e.g. `[]`) blocks `check` from
   rebuilding** with `AttributeError`; `report` gives a traceback.
4. **Medium: AI finding IDs are still reassigned after an ignored sibling is
   removed.** Two AI findings with the same rule/file/quote; ignore the
   first; after two checks, none remain.
5. **Medium: delayed issue planning can offer findings just ignored**; also
   selected findings stay eligible when hidden by a filter, and the confirm
   dialog shows only titles/counts.
6. **Medium: partial results render as an apparently clean whole-lesson
   report** (`✔ No issues found`), with no scope shown.
7. **Medium: a missing editor terminates the TUI** (`FileNotFoundError` from
   `subprocess.run`).

## Optional

- At 80x24 the 36-column sidebar hides footer shortcuts and the message
  column.
- Search updates rows but the header count ("36/36 shown") only on submit.
- README's AI claims are stronger than the evidence: moving lesson text into
  the user message doesn't establish it can't redirect the model.

## Reviewer's priorities

1. Centralize issue eligibility; revalidate selected and delayed drafts.
2. Separate invocation scope from persisted scope; label partial reports.
3. Preserve retained AI IDs across refreshes.
4. Controlled cache/editor failure handling; atomic results writes.
5. Narrow-screen help; full Pilot journey tests.

## Verification limits it reported

`pixi run test`/`lint` hit a pixi macOS `system-configuration` panic (exit
101); run directly, 310 tests and ruff passed. No live models, GitHub
writes, HTML/PDF, or sandpaper.
