# Claude CLI prompt: implement the standards review

Copy the prompt below into Claude Code while working in this repository. This prompt authorizes local implementation; it does not authorize commits, pushes, PRs, issue filing, paid model reviews, or changes to lesson repositories.

```text
Work in /Users/timdennis/projects/lessons/tools/carpentries-workbench-checker.

Implement a focused first release from the September 30 standards review. The goal is trustworthy, actionable feedback that reduces lesson-author effort in a local editor or on GitHub. Keep this a small authoring aid; do not turn it into a compliance or teaching-quality certification tool.

Read applicable AGENTS.md instructions and these files before editing:
- design/2026-09-30-standards-audit.md
- design/2026-09-30-rule-schema-help-proposal.md
- design/2026-09-30-claude-standards-handoff.md
- README.md, CONTRIBUTING.md, CHANGELOG.md

The reviewed baseline was main at 9032b056c2a3a18a12068f9db1e6c7a7c7e5136e, wbcheck 0.2.1. The review documents were uncommitted. Inspect the current branch, HEAD and working tree; preserve all existing work. Revalidate findings against current code and focused fixtures. Recognize fixes already made, discard stale findings, and keep unresolved interpretations as questions. The September 15 review is historical; many of its implementation problems are already fixed.

First implementation scope, in this order:

1. Correct source links, rationale and hints that overstate the evidence. These can land independently of the larger schema. Cover STD-09 and the contextual guidance in STD-02, STD-04, STD-05, STD-08 and STD-11.

2. Preserve finding identity before changing mechanical message text (STD-06). Current IDs depend on normalized messages, so even copy edits can invalidate suppressions and duplicate GitHub issues. Follow the proposal's identity_anchor bridge, including old-result readers, explicit result-version handling and golden ID fixtures. Fresh checks must still recognize old ID ignores even without a saved results file. Keep existing AI quote-based identities, duplicate occurrences, partial refresh and issue markers stable. Do not replace the identity algorithm wholesale.

3. Make targeted, independently testable corrections:
   - STD-01: recognize supported explicit/multiline alt attributes and decorative markers; do not infer description adequacy.
   - STD-02: WB403 reports zero declared exercise time without asserting that assessment is absent.
   - STD-03: correct the duplicate-anchor rationale and scope duplicate headings to verified hierarchy behavior.
   - STD-05: distinguish absent local glossary files from absent definitions; allow linked definitions in guidance and preserve intentional drafts under WB009.
   - STD-07: extract equivalent top-level objectives across Markdown list markers and wrapped items, without counting nested explanatory bullets separately.
   - STD-08: keep the contraction threshold explicitly local, preserve literal data/quotations, and narrow clearly supported quote contexts without creating a banned-word policy.
   - STD-12: reject boolean/nonfinite/negative timings while retaining legitimate zero and fractional minutes; avoid downstream timing claims for invalid values.
   - STD-11: label AI judgment and evidence limits consistently. Preserve the existing issue-body caveat. A matched quotation verifies an anchor, not a pedagogical or factual criticism.

For WB205, correct the current aggregate-count explanation now. Defer per-challenge detection until the aggregate-to-individual identity migration is designed. For div class order and other unresolved Workbench behavior, gather evidence and retain uncertainty instead of assuming Pandoc behavior proves Workbench behavior.

4. Implement the minimal shared help design (DES-01 and the rendering portion of DES-02): validated Rule/reference metadata, preserved stable codes/names and legacy category/guide compatibility, an offline `wbcheck explain CODE`, and a searchable `wbcheck rules` catalog. Use one source of truth for explanations across CLI, existing TUI details, reports and issue drafts. Show observation, next action, authority, exceptions, limitations and precise sources without repeating long explanations at every occurrence. Display severity words and plain URLs as well as optional styling. Preserve current source links, scope notices and issue eligibility.

Defer new TUI modal/keybindings, profile selection, hosted documentation, lifecycle verdicts, semantic-ID redesign and new rule families. Keep the existing TUI layout and controls. Do not change default severities, selected rules, issue grouping or --fail-on behavior in this batch. Leave the separate WB012 operational-exit change and WB213 safe-fix reclassification documented for a follow-up; do not silently fold them into metadata work. Do not add automatic educational rewrites.

Implementation constraints:
- Use a working branch if currently on main and permitted by the environment. Do not discard, overwrite or stash away user work to make progress.
- Make production edits only in this checker repository. Never modify a real lesson to test a fix; use temporary fixtures.
- No commits, pushes, PRs or GitHub issue writes. Do not launch paid/live AI reviews without explicit authorization. Read-only source verification is allowed.
- Normal checks and rule help must work offline. AI dependencies remain optional. Do not install a new framework or replace the parser without a demonstrated need.
- Treat observation, source authority, detection method and practical severity as separate dimensions. No quality scores, invented confidence percentages or approval claims.
- Reuse existing tests and architecture. Do not encode the current bug as the desired test outcome.
- Keep fixes compatible with old persisted findings; current fix handlers inspect message text in places, so wording changes need regression tests.

Validation:
- Run the relevant targeted fixtures and the full test/lint suite. The review baseline had 337 passing tests and clean lint, but that count is not a target.
- Prefer documented pixi tasks. If the same macOS pixi Rust system-configuration crash recurs before task execution, use .pixi/envs/default/bin/python -m pytest tests/ -q and .pixi/envs/default/bin/ruff check checker tests; report the limitation without modifying the global environment.
- Test old results, persisted IDs, .wbcheck.toml ignores, issue deduplication including closed issue markers, duplicate findings and partial refresh.
- Verify installed offline help outside the source checkout with core dependencies only, and shared explanation content in CLI, reports, TUI details and issue drafts.
- Changes to AI prompts/rubric require evaluation beyond mocked tests under CONTRIBUTING.md. If no live comparison is authorized, report that validation as pending instead of claiming model behavior is verified.
- Update documentation and release notes for actual changes, especially saved-result versions and expanded detector coverage that can affect an explicit --fail-on threshold.

Finish with a concise summary of implemented changes, tests and evidence, intentional behavior/compatibility changes, and deferred review IDs. Provide a short before/after diagnostic example. Leave the code and documents available for review; do not publish anything.
```
