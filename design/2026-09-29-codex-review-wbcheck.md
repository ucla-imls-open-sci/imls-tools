# External review: Codex on wbcheck (2026-09-29)

Source: an OpenAI Codex review of branch `fix-workflow`, commit `7a3ec91`
(merged as PR #41), pasted back into the session. Adjudication (what was
verified, adopted, rejected, deferred) is in
`2026-09-29-validation-capture-codex-review.md`.

## Summary as given

`wbcheck` is useful as an advisory checker, but its bulk automatic fixes
aren't yet trustworthy, and a clean result isn't strong assurance. 280 tests
pass, but targeted fixtures showed content loss, misleading success, and
wrong attribution of saved results.

## Confirmed defects (reviewer's severity)

1. **High: WB401 autofix deletes objective content.** The replacement is
   parsed out of the hint prose with `Try "([^"]+)"`, so an embedded quote
   truncates it: `- Understand "git status" output.` became `- Explain .`
   (`checker/fix.py`).
2. **High: WB009 autofix can corrupt `config.yaml`.** With no final newline,
   `- 01.md` became `- 01.md- 02.md`. An episode named `[draft].md` is
   inserted unquoted and breaks YAML parsing.
3. **High: URL targets mix lessons.** Checks of git URLs share
   `./.wbcheck/results.json`, and `review` loads it without checking the
   target, so reviewing URL B after checking URL A keeps A's findings,
   GitHub base, and issue destination.
4. **Medium: `--changed` misses filenames with spaces.** `git status
   --porcelain` quotes them (`"episodes/a b.md"`), so they never match; an H1
   error in such a file passed `check --changed` with exit 0. `--since`
   splits on whitespace too.
5. **Medium: non-mapping YAML crashes the run.** `config.yaml` of `- x`
   gets WB003, then later code calls `.get()` on the list (AttributeError).
   Metadata loading (`CITATION.cff`) has the same assumption.
6. **Medium: Markdown scanning false positives/negatives.** Fence tracking
   ignores fence character and length (a ```` block containing ``` exposes
   `#` comments as WB210, the reverse hides a real H1); `::: {#q
   .questions}` is read as a closing fence; reference links aren't checked;
   image syntax inside inline code is flagged as a missing image. Pandoc
   parses these as supported syntax.
7. **Medium: saved-results refresh is inconsistent.** `check` after `review`
   deletes AI findings; `check --episode` saves a partial snapshot that a
   later whole-lesson `review` reuses; TUI re-checks keep stale AI findings
   and git context.
8. **Medium: renumbering after filtering changes identities.** Ignoring the
   first of several duplicate headings, then renumbering, gives the
   surviving sibling the ignored ID. AI finding IDs depend on generated
   wording.
9. **Medium: filters bypass the WB013 safeguard.** `wbcheck fix --apply
   --yes --code WB009` adds an unlisted `glossary.md` because the filter
   removes WB013 before the planner looks for it.
10. **Medium: failed AI reviews exit 0.** All-backend failure and an
    unmatched `--episode` both succeed silently.
11. **Low: Unicode case folding breaks quote location.** `ß` folds to `ss`
    but the index map gets one entry: `locate_quote("abcdefgh", "ß"*20 +
    "\nabcdefgh")` raises IndexError.

## Design concerns

- WB401 (pedagogical rewrite) and WB009 (publishes a draft; Workbench
  supports unlisted drafts) are editorial decisions, not safe structural
  repairs, especially under `--yes`.
- Quote verification doesn't establish review quality; no evaluated corpus;
  the lesson-level review isn't implemented.
- Prompt-injection resistance unproven; glossary text sits in the system
  prompt.
- Ollama calls have no timeout.
- `wbcheck issues` reads at most 1,000 issues, so "never duplicates" is too
  absolute.
- CI's install smoke test runs an editable checkout, so it doesn't prove
  wheel contents.

## Reviewer's three next changes

1. Make automatic fixes non-destructive: no prose parsing, validated YAML
   edits, full safety context, editorial suggestions separated from
   bulk-safe fixes.
2. Unify the saved-results lifecycle and identity: validate target and
   revision, track scope and freshness, keep IDs stable through filtering,
   merge mechanical and AI results consistently.
3. Strengthen the checker boundary: git filename parsing, YAML guards,
   Pandoc-backed syntax fixtures, end-to-end command-sequence tests.

## Environment notes from the reviewer

`pixi run test`/`lint` panicked in its sandbox (macOS system-configuration);
running pytest and ruff from the env directly gave 280 passed and lint
clean. A Quarto HTML smoke test failed on a Sass cache database error; wheel
inspection was blocked (no hatchling).
