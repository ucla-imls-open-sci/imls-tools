Carpentries Workbench Checker (`wbcheck`)
==========================================

[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)

Fast local checks for [Carpentries Workbench](https://carpentries.github.io/workbench/)
lessons. `wbcheck` finds structural problems in under a second: front
matter, required `:::` blocks, headings, broken links and images, and
leftover scaffold text. An optional AI review covers writing and pedagogy,
and every finding it reports quotes the lesson text and is checked against
it. Then work through findings in your editor (nvim's quickfix list, or one
at a time at the right line), let it apply the safe fixes for you, browse
them in a terminal UI, or file them as pull-request-sized GitHub issues.

Run it before you push, instead of waiting on the sandpaper CI build.

```bash
curl -fsSL https://raw.githubusercontent.com/ucla-imls-open-sci/carpentries-workbench-checker/main/install.sh | sh
wbcheck check path/to/lesson
wbcheck fix path/to/lesson
```

## Contents

- [Install](#install)
- [Quick tour](#quick-tour)
- [Commands](#commands)
- [Fixing findings locally](#fixing-findings-locally)
- [What it checks](#what-it-checks)
- [Ignoring findings](#ignoring-findings-wbchecktoml)
- [The AI review](#the-ai-review)
- [Reports](#reports)
- [Filing GitHub issues](#filing-github-issues)
- [How this relates to sandpaper CI](#how-this-relates-to-sandpaper-ci)
- [Development](#development)

## Install

One line, macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/ucla-imls-open-sci/carpentries-workbench-checker/main/install.sh | sh
```

The script:

1. installs [pixi](https://pixi.sh) if you don't have it
2. clones the checker into `~/.local/share/wbcheck`
3. builds its environment from the lockfile (Python and every dependency,
   nothing installed system-wide)
4. puts a `wbcheck` launcher in `~/.pixi/bin`, which pixi's installer
   already adds to your `PATH`

Then:

```bash
wbcheck doctor                 # which optional pieces are ready (gh, Quarto, Ollama, API key, $EDITOR)
wbcheck --install-completion   # tab completion for subcommands and flags
```

**Update** with `wbcheck update` (git pull, then refresh the environment), or
re-run the install line. **Uninstall** by deleting `~/.local/share/wbcheck`
and `~/.pixi/bin/wbcheck`.

To install a branch, tag, or fork, or to use different locations, set any of
`WBCHECK_REF` (default `main`), `WBCHECK_REPO`, `WBCHECK_HOME`, or
`WBCHECK_BIN_DIR` before `sh`:

```bash
curl -fsSL https://raw.githubusercontent.com/ucla-imls-open-sci/carpentries-workbench-checker/main/install.sh | WBCHECK_REF=my-branch sh
```

**Optional extras**, each only needed for one feature:

| For | Needs |
|---|---|
| `wbcheck issues`, filing from the TUI | [GitHub CLI](https://cli.github.com), logged in (`gh auth login`) |
| `report --html` / `--pdf` | [Quarto](https://quarto.org); PDF also needs LaTeX (`quarto install tinytex`) |
| `review --backend claude` | `ANTHROPIC_API_KEY` |
| `review --backend ollama` | [Ollama](https://ollama.com) running, plus a model (see [local models](#local-models-16gb-apple-silicon)) |
| `o` in the TUI | `$VISUAL` or `$EDITOR` set, e.g. `export EDITOR=nvim` (falls back to `vi`) |

Working on the checker itself? See [Development](#development).

## Quick tour

```bash
wbcheck check ~/lessons/my-lesson          # fast checks; saves results; exit 1 on errors
wbcheck fix ~/lessons/my-lesson            # walk the findings in $EDITOR (nvim: quickfix list)
wbcheck fix ~/lessons/my-lesson --apply    # apply the safe automatic fixes, each shown as a diff
wbcheck review ~/lessons/my-lesson --backend claude   # add the AI review to the same results
wbcheck tui ~/lessons/my-lesson            # browse, open in $EDITOR at the line, ignore, file issues
wbcheck issues ~/lessons/my-lesson --preview          # what would be filed as GitHub issues
wbcheck report ~/lessons/my-lesson --html report.html --open
```

Every command shares one results file per lesson,
`<lesson>/.wbcheck/results.json`. The folder ignores itself with its own
`.gitignore`, so lesson repos need no changes. That lets the slow AI review
run separately from the fast checks, and lets reports, issue filing, and the
TUI work from saved results without re-checking.

A target can also be a git URL (`wbcheck check
https://github.com/librarycarpentry/lc-git.git`). It's cloned to a temporary
directory, and results are saved under `./.wbcheck/` instead.

## Commands

`wbcheck <command> --help` lists every option.

### `check`: the fast mechanical checks

```bash
wbcheck check LESSON
wbcheck check LESSON --episode 03-sharing.md   # one episode
wbcheck check LESSON --source                  # show the offending source line under each finding
wbcheck check LESSON --blame                   # record who last changed each file with findings
wbcheck check LESSON --fail-on warning         # exit 1 on warnings too; also info or never
wbcheck check LESSON --quiet                   # save results without printing
wbcheck check LESSON --changed                 # only files with uncommitted changes
wbcheck check LESSON --changed --since main    # ...plus everything changed since main
```

Prints findings grouped by file. Each shows its rule code (a clickable link
to the guide section in terminals that support hyperlinks: iTerm2, Ghostty,
WezTerm, VS Code, recent GNOME Terminal), line number, message, and fix.
Exits `1` if anything is at or above `--fail-on` (default `error`), so it
works in a pre-commit hook or a lesson's own CI. With `--changed`, only
findings in changed files are shown and counted toward the exit code, which
makes `wbcheck check . --changed --since main --fail-on warning` a good
pre-push or PR check: it holds your changes to the standard without failing
on problems you didn't touch. The saved results still hold every finding.

### `fix`: work through findings in your editor

```bash
wbcheck fix LESSON                    # every warning and error, in $VISUAL / $EDITOR
wbcheck fix LESSON --code WB401       # one rule
wbcheck fix LESSON --file 'episodes/0*' --changed
wbcheck fix LESSON --apply            # safe automatic fixes, diff by diff
```

See [Fixing findings locally](#fixing-findings-locally).

### `review`: the AI review

```bash
wbcheck review LESSON --backend claude                       # Anthropic API
wbcheck review LESSON --backend ollama                       # local, free
wbcheck review LESSON --episode 03-sharing.md --backend claude --effort medium
```

Adds structured, quote-verified findings (`AI201` to `AI208`) to the saved
results. Runs `check` first if there are no results yet. Re-reviewing an
episode replaces its earlier AI findings. See [The AI review](#the-ai-review).

### `tui`: browse and triage

```bash
wbcheck tui LESSON        # runs check first if there are no saved results
```

A folder → file → rule-code tree on the left, colored by each file's worst
severity; the findings table on the right; and a detail pane with the full
message, the quote (AI findings), the fix, clickable guide links, and the
source lines around the finding.

| Key | Does |
|---|---|
| `enter` (tree) | filter to that file or rule code |
| `space` | select or unselect a finding (moves down) |
| `o` | open the file at the finding's line in `$VISUAL` / `$EDITOR` (vim, nvim, emacs, nano, VS Code, Cursor, Sublime, Zed, Helix). When you come back, it re-checks and tells you whether that finding is fixed; fixed ones drop off the list |
| `r` | re-run the mechanical checks, keeping AI findings |
| `i` | ignore the selection (or the current finding): adds its ID to `.wbcheck.toml` |
| `c` | file issues: the selection as **one** issue, or, with nothing selected, the visible warnings and errors grouped as `wbcheck issues` would. Shows the list and asks `y`/`n`, skips anything already filed, and shows progress while it talks to GitHub |
| `s` / `a` | cycle minimum severity (all → warnings+ → errors) / source (all → mechanical → AI) |
| `/` | search message, quote, file, and code; `esc` clears every filter |
| `q` | quit |

### `issues`: file findings as GitHub issues

```bash
wbcheck issues LESSON --preview     # dry run, with each issue body
wbcheck issues LESSON --create      # file them (asks first; -y skips)
```

See [Filing GitHub issues](#filing-github-issues).

### `report`: re-render saved results

```bash
wbcheck report LESSON                              # terminal
wbcheck report LESSON --md report.md --json results.json
wbcheck report LESSON --html report.html --open    # needs Quarto
wbcheck report LESSON --pdf report.pdf             # needs Quarto + LaTeX
```

### `doctor` and `update`

`wbcheck doctor` shows the version, install location, and which optional
tools are ready. `wbcheck update` pulls the latest checker and refreshes its
environment; it refuses if the install has local changes.

## Fixing findings locally

`wbcheck fix` re-checks the lesson, then walks you through what it found.
Filter with `--code` (repeatable), `--file GLOB`, `--min-severity`
(default `warning`), `--source mechanical|ai`, and `--changed` /
`--since REF`.

**In vim or nvim** (`$VISUAL` or `$EDITOR`), every finding loads into the
**quickfix list**: the editor opens on the first one, `]q` / `:cnext` and
`[q` / `:cprev` move between them, and `:copen` shows them all with their
messages and fixes. When you quit, the lesson is re-checked and you get a
count of what you fixed. To load findings into an editor that's already
open, `wbcheck fix LESSON --print` writes the same `path:line:col: message`
lines to stdout: `:cexpr system('wbcheck fix . --print')`, or start one with
`nvim -q <(wbcheck fix . --print)`.

**In any other editor** (or with `--step`), it goes one finding at a time:
it shows the code, message, quote, and fix, then `enter` opens the file at
the line, `s` skips, and `q` stops. After each edit it re-checks and says
✔ fixed or ✗ still reported.

**`--apply`** proposes fixes only where the edit is unambiguous, shows each
as a diff, and asks `y`/`n`/`a`(ll)/`q` (`--yes` applies them all):

| Code | Fix |
|---|---|
| `WB103` | rename a front-matter `exercise:` typo to `exercises:` |
| `WB009` | append an unlisted episode to `config.yaml`'s `episodes:` (not when `WB013` says the file looks like reference content) |
| `WB213` | set a heading that skips a level to one below the previous heading |
| `WB401` | replace a vague objective opener with the suggested verb (Understand → Explain, Know → Identify, ...). Worth reading each one: it's a starting point, and the objective still needs an exercise that assesses it |

Each fix checks that the line hasn't changed since the check ran, and
content (prose, placeholders, exercises) is always left to you. Review the
result with `git diff` like any other edit.

## What it checks

Every check has a stable rule code, ruff-style, defined once in
[`checker/rules.py`](checker/rules.py) with why it matters and a link to the
most specific guide section that states the rule. Codes are never renumbered
or reused.

| Code | Severity | Checks |
|---|---|---|
| `WB001` | error | config.yaml not found |
| `WB002` | error | config.yaml is not valid YAML |
| `WB003` | error | config.yaml is not a key: value mapping |
| `WB004` | error | config.yaml field is empty or still the template value |
| `WB005` | warning | `created` date not set |
| `WB006` | info | `life_cycle` still pre-alpha |
| `WB007` | error | episode listed in config.yaml does not exist |
| `WB008` | warning | file in episodes/ has no .md/.Rmd extension |
| `WB009` | warning | episode file not listed in config.yaml |
| `WB010` | info | no glossary file |
| `WB011` | error | no episodes/ directory |
| `WB012` | error | --episode named a file that doesn't exist |
| `WB013` | warning | episode file looks like reference content |
| `WB101` | error | episode has no YAML front matter |
| `WB102` | error | front matter is not a key: value mapping |
| `WB103` | error | required front-matter field missing |
| `WB104` | warning | teaching/exercises is not a number of minutes |
| `WB105` | info | episode length outside 20-60 minutes |
| `WB110` | error | episode title is still the scaffold default |
| `WB111` | warning | episode body still contains scaffold example text |
| `WB112` | error | placeholder text in questions/objectives/keypoints |
| `WB113` | warning | setup/instructor notes/profiles still the scaffold |
| `WB114` | warning | glossary is still the scaffold placeholder |
| `WB201` | info | unrecognized div type |
| `WB202` | error | closing ::: with no matching open div |
| `WB203` | error | div never closed |
| `WB204` | error | required questions/objectives/keypoints block missing |
| `WB205` | info | more challenges than solutions |
| `WB210` | error | episode uses a level-1 heading |
| `WB211` | warning | first heading is not level 2 (callout/spoiler titles don't count) |
| `WB212` | warning | duplicate heading text |
| `WB213` | warning | heading skips a level (h2 → h4), following the rendered outline |
| `WB301` | warning | image has no alt text |
| `WB302` | error | image file not found |
| `WB303` | warning | generic link text ("click here") |
| `WB304` | warning | internal link target not found |
| `WB401` | warning | objective opens with a hard-to-assess verb (suggests a rewrite) |
| `WB402` | info | more than 4 objectives in one episode |
| `WB403` | warning | objectives declared but no exercise time |
| `WB404` | info | heavy use of contractions |

`AI201` to `AI208` are the [AI review's](#the-ai-review) findings.

A few details worth knowing:

- Div and heading checks skip fenced code blocks, so a lesson that teaches
  Markdown or shell `#` comments doesn't trip them.
- Image paths resolve relative to `episodes/` (the Workbench `episodes/fig/`
  convention) or the lesson root, and `.html` links resolve to the `.md` or
  `.Rmd` source they're rendered from.
- The scaffold checks (`WB110` to `WB114`) catch lessons that are
  structurally complete but never written: the default "Using Markdown"
  episode, `keypoint1` bullets, and placeholder `learners/setup.md`,
  `instructors/instructor-notes.md`, `profiles/learner-profiles.md`, and
  glossary files.
- The objectives, contraction, glossary, and heading-skip checks come from
  the [Collaborative Lesson Development Training](https://carpentries.github.io/lesson-development-training/aio.html)
  (CLDT) and the [Carpentries Lab reviewer](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md)
  and editor checklists, not from sandpaper.

**Finding IDs.** Each finding also has a 12-character `id`: a hash of its
code, file, and message, with line numbers and counts left out, plus an
occurrence number for repeats in the same file. The same problem keeps the
same ID when unrelated edits move it, which is what ignoring and issue
de-duplication rely on.

## Ignoring findings: `.wbcheck.toml`

Put a `.wbcheck.toml` at the lesson root, and commit it so collaborators
share it:

```toml
[ignore]
codes = ["WB404"]                      # a rule, everywhere
paths = ["episodes/all_exercises.md"]  # every finding in these files (globs ok)
ids = ["8289307d05d3"]                 # single findings, by ID
```

`check` and `review` drop matching findings before saving, and the report
header says how many were ignored. The TUI's `i` key adds IDs here; when it
does, the file is rewritten in the form above, so comments inside it aren't
kept.

## The AI review

Off unless you run `wbcheck review`: it takes time, and the `claude` backend
costs API usage (roughly $0.10 to $0.25 per episode at `--effort medium`).

It returns **structured findings**, not an essay. Each has a code for its
area, a severity, a verbatim quote from the episode, the problem, a
suggested fix, and a `scope` label that groups related findings into one
pull request's worth of work.

| Code | Area |
|---|---|
| `AI201` | objectives not observable, or not assessed |
| `AI202` | exercises without diagnostic power or variety |
| `AI203` | difficulty or pacing mismatched to the audience |
| `AI204` | too much at once (cognitive load) |
| `AI205` | dismissive language, idioms, unexplained jargon |
| `AI206` | glossary gap, with a draft definition in the fix |
| `AI207` | accessibility (alt text, color-only cues) |
| `AI208` | accuracy |

**Every finding is checked against the text.** The model must quote the
episode, and a finding whose quote isn't actually there is dropped. Matching
tolerates whitespace, smart quotes, markdown emphasis, and `...` elisions.
The run reports how many were dropped. So every AI finding points at a real
line you can check.

**What the model grades against** is pinned into every prompt from
[`checker/rubric/`](checker/rubric/): the Carpentries Lab reviewer checklist,
plus excerpts of CLDT and the Workbench docs. Nothing is fetched at review
time, so the same lesson gets the same rubric every run. The lesson's
glossary (`learners/reference.md`) goes into the prompt too, so glossary-gap
findings skip terms already defined. The mechanical findings are included as
well, so the model doesn't repeat them.

| Backend | Needs | Notes |
|---|---|---|
| `claude` | `ANTHROPIC_API_KEY` | Default model `claude-opus-5-5`. `--effort` is `high` by default; `low`/`medium` are cheaper and faster, `xhigh`/`max` more thorough. The rubric and glossary are prompt-cached across episodes, and if a safety classifier declines an episode, the API retries it on a fallback model |
| `ollama` | `ollama serve` and a pulled model | Fully local and free. Output is constrained to the findings schema, with one automatic retry if the model misses it |

`--model` overrides the default for either backend.

### Local models (16GB Apple Silicon)

Install [Ollama](https://ollama.com), start it with `ollama serve`, and pull a
model with `ollama pull <model>`. (A development checkout also has Ollama in
its pixi environment: `pixi run ollama-serve` and `pixi run pull-models`.)
`wbcheck doctor` tells you whether the server is up and the default model is
pulled.

| Model | Download | Use it for |
|---|---|---|
| `qwen3.5:9b-q4_K_M` (default) | ~6.6 GB | General episode review; best quality for the footprint, with headroom left on 16GB |
| `qwen3.5:4b` | ~3.4 GB | Faster checks while drafting; switch to the 9B for a final pass |
| `qwen2.5-coder:7b` | ~4.7 GB | Lessons heavy on shell, Python, or R code |
| `gpt-oss:20b` | ~14 GB | Best local quality if you can close everything else; slow with other apps open |

On 16GB, don't run a local review alongside another large model or a heavy
IDE: swapping slows it down long before memory actually runs out.

## Reports

`wbcheck report` renders saved results as terminal output, markdown, JSON,
HTML, or PDF. Every format opens with the tool version and, when
`config.yaml` and `CITATION.cff` have them, the lesson's title, carpentry,
life cycle, license, source repo, authors, and contact, so a report handed
to someone else identifies itself.

The markdown report (and the HTML and PDF built from it) has three parts:

1. **Files**: one checkbox per file with its issue count, linking to that
   file's section.
2. **Action summary**: one row per *shared fix* across the lesson, so a
   problem repeated in 16 places is one row with `Occurrences: 16`.
3. **Per-file detail**, in the order you'd fix things in an editor. Findings
   in a file that share a fix collapse into one change with a checklist of
   lines, followed by the rule's guide links.

Each line reference links to the exact line on GitHub at the checked
commit when the lesson is a GitHub repo; files with uncommitted changes at
check time are shown as plain `path:line` instead, since the commit wouldn't
contain what was checked. AI findings show their quote.

HTML and PDF go through a bundled Quarto format extension,
[`checker/quarto/_extensions/checker-report/`](checker/quarto/_extensions/checker-report/),
which owns the look (typography, Carpentries link and accent colors, PDF
margins); `report.py` owns the content. The Carpentries logo isn't embedded,
since its repo has no license. In PDFs, the ❌/⚠️/ℹ️ severity icons don't
render (LaTeX's default font has no emoji); severity still shows through the
checkbox and bold rule code.

## Filing GitHub issues

```bash
wbcheck issues LESSON                           # dry run: the issues it would file
wbcheck issues LESSON --preview                 # ...with each body
wbcheck issues LESSON --create                  # file them via gh (asks first; -y skips)
wbcheck issues LESSON --group-by file           # one issue per file, even for lesson-wide rules
wbcheck issues LESSON --source ai --min-severity info --repo me/my-fork
```

Each issue is sized for one pull request:

- By default (`--group-by auto`), a rule that shows up in 3 or more files
  gets one lesson-wide issue, e.g. every vague objective in one issue. Other
  mechanical findings get one issue per file. `--group-by file` or `rule`
  forces one or the other.
- AI findings are grouped per file and `scope`. An episode's one-off
  suggestions share one "other suggestions" issue, labelled `ai-suggested`
  with a note that they're suggestions to verify.
- Each item has a checkbox, a link to its line at the checked commit, the
  quote (AI findings), and the fix. A "Why these matter" section cites the
  guide for each rule.
- Notes (`info`) are left out unless you pass `--min-severity info` (or, in
  the TUI, select them yourself).

**Re-running never duplicates.** Each finding's ID is hidden in the issue
body. Before filing, `issues` reads every `wbcheck`-labelled issue in the
repo, open or closed, and leaves out anything already filed, so a finding
you close as won't-fix stays closed. The repo defaults to the lesson's
GitHub `origin`, and it warns first when files had uncommitted changes at
check time, since their items can't link to GitHub.

## How this relates to sandpaper CI

The Carpentries' own CI (`sandpaper::validate_lesson()` and pegboard's
`validate_divs()`, `validate_headings()`, and `validate_links()`, run in
Docker on every PR) is authoritative but slow: several minutes, and only
after you push. `wbcheck` mirrors those rules locally in under a second and
adds the CLDT and Carpentries Lab checks above. It's an approximation, not a
replacement: sandpaper is still the final word.

## Development

```bash
git clone https://github.com/ucla-imls-open-sci/carpentries-workbench-checker.git
cd carpentries-workbench-checker
pixi install
pixi run wbcheck check path/to/lesson     # or `pixi shell`, then plain `wbcheck`
```

The pixi environment installs the package in editable mode, so code changes
take effect immediately.

| Task | Does |
|---|---|
| `pixi run test` | the test suite: no network, models, gh, or Quarto needed (the AI backends, gh, and editor are faked) |
| `pixi run lint` / `lint-fix` | ruff: unused imports, import order, missing docstrings in `checker/`, outdated syntax |
| `pixi run refresh-rubric` | re-fetch the AI review's guidance excerpts into `checker/rubric/`; read the diff before committing. Fails loudly if an upstream section it expects has moved |
| `pixi run pull-models` | pull the default local Ollama model (`-small` and `-coding` variants too) |

CI runs the tests and lint, then installs with `install.sh` on Linux and
macOS and runs the installed `wbcheck` from outside the repo, so a file
missing from the package fails the build.

`pixi run format` (`ruff format`) exists but isn't applied wholesale; it
would reflow a lot of intentionally formatted prose strings.

The design notes behind the current version are in [`design/`](design/),
starting with
[`modernization-assessment-2026-09-29.md`](design/modernization-assessment-2026-09-29.md).
Changes are listed in [CHANGELOG.md](CHANGELOG.md).

### Legacy CLI

The original flag-based CLI still works from a development checkout, and is
superseded by `wbcheck`:

```bash
pixi run check LESSON [--episode NAME] [--format terminal|markdown|json] [--output FILE]
                      [--html] [--pdf] [--open] [--blame] [--ai --backend ollama|claude]
```

It replaced the earlier `content-checker/` scripts and `llama-checker.py`.
`legacy/proposal_analysis.ipynb` (scoring lesson proposals with the OpenAI
API) is unrelated to lesson checking and kept only for reference.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Everyone participating is expected to
follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[BSD 3-Clause](LICENSE)
