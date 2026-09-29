# Changelog

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
  Never files duplicates, even of closed issues (#21).
- **`wbcheck tui`**: Textual app to browse, filter, ignore, open in
  `$EDITOR`, and file findings as issues (#28).
- **`.wbcheck.toml`** to ignore findings by code, path glob, or ID.
- **WB213**: headings that skip a level (h2 to h4), per the Carpentries Lab
  editor checklist.
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
- Installed packages were missing `checker/report.py` (an unanchored
  `report.*` in `.gitignore` excluded it from the build) and the Quarto
  report extension (now shipped inside the package).
- WB211 flagged callout and spoiler titles (`###` inside a fenced div) as
  a bad first heading.
- `--format json` crashed on an unquoted `created:` date in config.yaml.

The legacy `pixi run check` CLI still works and is unchanged apart from the
new AI review output.
