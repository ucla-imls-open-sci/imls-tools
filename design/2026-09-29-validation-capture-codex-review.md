# Validation capture: Codex review of wbcheck (2026-09-29)

The review itself is in `2026-09-29-codex-review-wbcheck.md`. Every claimed
defect was reproduced independently, from scripts written against current
`main`, before being adopted. All 11 reproduced. Tim signed off on the table
below ("adopt what you adjudicated adopt, in the sequence you think").

## Outcome

| # | Claim | Verified | Decision | Landed |
|---|---|---|---|---|
| 1 | WB401 autofix deletes objective text (quotes in the objective) | yes: `- Explain .` | adopt | PR #42: rewrite only the opener from the source line (`rewrite_objective_opener`), never parse hint prose |
| 2 | WB009 autofix corrupts config.yaml (no final newline; `[draft].md`) | yes, both | adopt | PR #42: keep line boundaries, YAML-quote names, re-parse and check the list before writing |
| 3 | git URL results mix lessons | yes (by code) | adopt | PR B: `target_id` + per-repo results folders; other-target results replaced, not merged |
| 4 | `--changed` misses names with spaces | yes | adopt | PR #42: `git status -z` / `git diff -z` |
| 5 | non-mapping config.yaml / CITATION.cff crashes | yes, both | adopt | PR #42: `load_yaml_mapping`, field types guarded |
| 6a | fences ignore character/length | yes | adopt | PR #42: CommonMark fence tracking |
| 6b | `::: {#q .questions}` read as a closing fence | yes | adopt | PR #42: `_div_fence` (Pandoc fenced_divs) everywhere |
| 6c | image syntax in inline code flagged | yes | adopt | PR #42 |
| 6d | reference-style links unchecked | yes | defer | new feature, not a bug |
| 6e | Pandoc as test oracle | not tried | defer | Pandoc isn't in the env; fixtures cover the reported cases |
| 7 | check deletes AI findings; partial snapshots reused; TUI keeps stale state | yes (first two), by code (third) | adopt | PR B: one `refresh()` for check/review/fix/TUI; file fingerprints mark AI findings stale; scope `full`/`partial`; review always refreshes |
| 8 | renumbering after ignore moves IDs; AI IDs depend on wording | yes | adopt | PR B: number before filtering, never after; AI identity from the quote |
| 9 | `--code WB009` bypasses WB013 | yes | adopt | PR #42: safeguard re-derived from the file (also holds when WB013 is ignored) |
| 10 | failed / unmatched reviews exit 0 | yes | adopt | PR #42: exit 1 on any failure (successes saved), 2 on no match |
| 11 | `ß` case fold crashes quote location | yes | adopt | PR #42 |
| D1 | WB401/WB009 are editorial, not safe | agree | **defer to Tim** | proposed: `--apply` = WB103, WB213; WB401/WB009 behind `--suggest`, always per-fix confirm |
| D2 | quote checks don't prove review quality | agree | defer | issue #29 (evaluation set) |
| D3 | glossary in the system prompt | agree | adopt | PR #42: cached user-message block; system prompt is tool-controlled text only |
| D4 | no Ollama timeout | yes | adopt | PR #42: `Client(timeout=900)` |
| D5 | "never duplicates" too absolute (1,000 cap) | yes | adopt | PR #42: 10,000 and refuse past it; wording softened |
| D6 | CI can't catch files missing from the wheel | yes | adopt | PR #42: `pixi run check-wheel` in CI; verified it fails on the old `.gitignore` bug |
| - | `pixi run test` panic; Quarto Sass cache error | no: reviewer's sandbox | reject | both run here and in CI |

## Evidence that the fixes don't regress real lessons

Finding counts per rule code were compared between `main` and PR #42 on 24
local lessons, with the old code forced onto the import path (a first
attempt accidentally ran the new code twice and was discarded). The counts
were identical: the fixes only change behavior on the edge cases the review
found.

## Found while doing it

- The first `--episode` merge compared only files that had findings, so an
  edited episode that had been clean slipped through as "unchanged". A
  command-sequence test caught it; it now compares every other episode file.
- The 12 AI findings from the earlier live Claude run on
  better-research-software had already been wiped by old-style `check` runs:
  item 7 in practice.

## Still open

D1 (split `--apply`), 6d (reference links), D2/#29 (evaluation set), and
the lesson-level AI review pass (#27).
