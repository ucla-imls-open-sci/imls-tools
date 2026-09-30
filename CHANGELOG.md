# Changelog

## 0.2.1 (2026-09-30)

### Changed
- README reorganized around tasks (check, fix, review, TUI, issues,
  reports), with internals moved to a Reference section. It now spells out
  the vim/nvim loop for `wbcheck fix` (fix, `:w`, `]q`, refresh with
  `:cexpr system('wbcheck fix . --print')`) and is more careful about what
  quote verification proves for AI findings (#46).
- The TUI's issue confirmation lists each issue's findings and says how
  many selected findings a filter is hiding and how many stale ones were
  left out (#47).

### Fixed
From a second external review (`design/2026-09-30-codex-review-wbcheck.md`):
- The TUI could file a stale AI finding if you selected it by hand, and
  could offer findings you ignored while it was checking GitHub. One filing
  rule now covers every path, and the TUI plans issues from the current
  results (#47).
- `check --episode` showed and failed on other episodes' saved findings.
  It now reports on the episode you asked for; the saved results still keep
  the rest. Partial results are labelled in terminal and file reports and
  the TUI, instead of reading as "No issues found" (#48).
- Ignoring one of two AI findings with the same rule, file, and quote could
  give its ID to the other, which then disappeared on the next check.
  Saved AI findings now keep their IDs (#49).
- A damaged `results.json` (e.g. `[]`) crashed `check` instead of being
  rebuilt; `report` and `issues` showed a traceback. `check` now warns and
  rebuilds, read-only commands say how to recover, and results are written
  atomically (#50).
- A missing or failing `$EDITOR` crashed the TUI; it now shows a
  notification and keeps running (#50).

## 0.2.0 (2026-09-29)

A rebuild around a saved results file, structured AI findings, and GitHub
issue filing. Tracked in #21 to #28; the design is in
`design/modernization-assessment-2026-09-29.md`.

### Added
- **`wbcheck` CLI** with `check`, `review`, `report`, `issues`, `tui`, `doctor`, and `update`
  subcommands sharing `<lesson>/.wbcheck/results.json` (#24). Rich terminal
  output, tab completion (`wbcheck --install-completion`), and `check
  --fail-on error|warning|info|never` for CI and pre-commit use.
- **Rule codes** `WB001` to `WB404` and `AI201` to `AI208`, each with a
  rationale and a link to the specific guide section; stable finding IDs
  that survive line shifts (#23).
- **`wbcheck issues`**: files findings as pull-request-sized GitHub issues,
  grouped per file, per rule when a rule spans 3+ files, or per AI scope.
  Skips findings already filed, including in closed issues (#21).
- **`wbcheck tui`**: Textual app to browse, filter, ignore, open in
  `$EDITOR`, and file findings as issues (#28).
- **`.wbcheck.toml`** to ignore findings by code, path glob, or ID.
- **WB213**: headings that skip a level (h2 to h4), per the Carpentries Lab
  editor checklist.
- **`wbcheck fix`**: work through findings in your editor. In vim/nvim they
  load into the quickfix list; other editors go one finding at a time. Both
  re-check afterwards and report what was fixed. `--apply` offers the safe
  fixes (WB103, WB213) as diffs; `--suggest` offers editorial ones (WB401
  objective rewrites, WB009 listing an episode), each confirmed on its own
  and never applied by `--yes`; `--print` emits quickfix lines.
- **`check --changed [--since REF]`**: only show and count findings in files
  you've changed.
- The TUI re-checks when you come back from the editor (`o`) and says
  whether that finding is fixed.
- **One-line install** with pixi (`install.sh`), plus `wbcheck doctor` and
  `wbcheck update`. CI installs with the script on Linux and macOS and runs
  the installed command.

### Changed
- **AI review returns structured findings** with a verbatim quote, which is
  checked against the episode; findings whose quote isn't there are
  dropped (#26). Grading guidance is pinned from `checker/rubric/`
  (`pixi run refresh-rubric`) instead of fetched and embedded each run
  (#25). Default Claude model `claude-opus-5-5`, with `--effort`.
- Objective findings suggest a concrete rewrite (Understand -> Explain,
  Know -> Identify), and more findings carry line numbers.

### Removed
- LangChain, Chroma, tiktoken, and the Ollama requirement for the Claude
  backend; the `codex` backend.

### Fixed
From an external review (`design/2026-09-29-codex-review-wbcheck.md`):
- `fix --apply` could delete an objective's text (WB401, when it contained
  a quote) and corrupt `config.yaml` (WB009, no final newline or a
  YAML-special file name); `--code WB009` bypassed the reference-content
  safeguard.
- `--changed` missed file names with spaces or non-ASCII characters.
- A `config.yaml` or `CITATION.cff` that isn't a mapping crashed the run.
- Code fences didn't track fence character and length; `::: {#id .class}`
  divs read as closing fences; image syntax in inline code was flagged.
- A review where every episode failed, or `--episode` matched nothing,
  exited 0.
- Quote matching crashed on characters that case-fold to several (`ß`).
- Saved results: `check` after `review` deleted AI findings; `check
  --episode` left a partial snapshot that `review` reused; results from one
  git URL could be merged into another's; ignoring a finding could hand its
  ID to a sibling. Now one refresh policy (`checker/refresh.py`) records
  target identity, commit, scope, and file fingerprints, marks AI findings
  stale when their file changes, and never renumbers after filtering. AI
  finding IDs come from the quoted text, not the model's wording.
- The glossary moved out of the system prompt; Ollama calls got a timeout;
  `issues` reads up to 10,000 existing issues and refuses past that rather
  than risk duplicates; CI builds the wheel and checks its contents.

- Installed packages were missing `checker/report.py` (an unanchored
  `report.*` in `.gitignore` excluded it from the build) and the Quarto
  report extension (now shipped inside the package).
- WB211 flagged callout and spoiler titles (`###` inside a fenced div) as
  a bad first heading.
- `--format json` crashed on an unquoted `created:` date in config.yaml.

The legacy `pixi run check` CLI still works and is unchanged apart from the
new AI review output.
