Carpentries Workbench Checker (`wbcheck`)
==========================================

[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)

Fast local checks for [Carpentries Workbench](https://carpentries.github.io/workbench/)
lessons. In under a second, `wbcheck` finds broken front matter, missing
`:::` blocks, heading problems, broken links and images, and leftover
scaffold text. Run it before you push instead of waiting on the sandpaper CI
build. An optional AI review adds writing and pedagogy findings, each one
quoting the lesson text it's about.

```bash
curl -fsSL https://raw.githubusercontent.com/ucla-imls-open-sci/carpentries-workbench-checker/main/install.sh | sh
wbcheck check path/to/lesson    # what's wrong
wbcheck fix path/to/lesson      # fix it in your editor
```

## Contents

- [Install](#install)
- [Everyday use](#everyday-use)
- [Checking](#checking-wbcheck-check)
- [Fixing](#fixing-wbcheck-fix)
- [The AI review](#the-ai-review-wbcheck-review)
- [Browsing in the terminal UI](#browsing-in-the-terminal-ui-wbcheck-tui)
- [Filing GitHub issues](#filing-github-issues-wbcheck-issues)
- [Reports](#reports-wbcheck-report)
- [Reference](#reference): rule codes, ignoring findings, saved results, sandpaper
- [Development](#development)

## Install

One line, macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/ucla-imls-open-sci/carpentries-workbench-checker/main/install.sh | sh
```

It installs [pixi](https://pixi.sh) if needed, clones the checker into
`~/.local/share/wbcheck`, builds its environment from the lockfile (nothing
installed system-wide), and puts a `wbcheck` launcher in `~/.pixi/bin`,
which is already on your `PATH` if you use pixi.

```bash
wbcheck doctor                 # which optional pieces are ready
wbcheck --install-completion   # tab completion
wbcheck update                 # pull the latest and refresh the environment
```

To uninstall, delete `~/.local/share/wbcheck` and `~/.pixi/bin/wbcheck`. To
install a branch, tag, or fork, set `WBCHECK_REF` (default `main`),
`WBCHECK_REPO`, `WBCHECK_HOME`, or `WBCHECK_BIN_DIR` before `sh`, e.g.
`... | WBCHECK_REF=my-branch sh`.

Optional extras, each needed for one feature only:

| For | Needs |
|---|---|
| `wbcheck issues`, filing from the TUI | [GitHub CLI](https://cli.github.com), logged in (`gh auth login`) |
| `report --html` / `--pdf` | [Quarto](https://quarto.org); PDF also needs LaTeX (`quarto install tinytex`) |
| `review --backend claude` | `ANTHROPIC_API_KEY` |
| `review --backend ollama` | [Ollama](https://ollama.com) running, plus a model (see [local models](#local-models-16gb-apple-silicon)) |
| `fix`, `o` in the TUI | `$VISUAL` or `$EDITOR`, e.g. `export EDITOR=nvim` (falls back to `vi`) |

## Everyday use

```bash
wbcheck check LESSON                     # fast checks, saved to LESSON/.wbcheck/
wbcheck fix LESSON                       # work through them in $EDITOR
wbcheck fix LESSON --apply               # let it make the safe mechanical fixes
wbcheck review LESSON --backend claude   # optional: add the AI review
wbcheck issues LESSON --preview          # optional: see them as GitHub issues
```

`LESSON` defaults to the current directory. It can also be a git URL
(`wbcheck check https://github.com/librarycarpentry/lc-git.git`), which is
cloned to a temporary directory. Every command reads and writes one results
file per lesson, `<lesson>/.wbcheck/results.json`, which ignores itself, so
the lesson repo needs no changes. `wbcheck <command> --help` lists every
option.

## Checking: `wbcheck check`

```bash
wbcheck check LESSON
wbcheck check LESSON --episode 03-sharing.md   # one episode
wbcheck check LESSON --source                  # show the offending line under each finding
wbcheck check LESSON --blame                   # record who last changed each file with findings
wbcheck check LESSON --fail-on warning         # exit 1 on warnings too (also: info, never)
wbcheck check LESSON --quiet                   # save results without printing
wbcheck check LESSON --changed --since main    # only files changed since main or uncommitted
```

Findings are grouped by file, each with its [rule code](#rule-codes), line,
message, and fix. In terminals with hyperlinks, the code links to the guide
section behind the rule. It exits `1` if anything is at or above `--fail-on`
(default `error`), so it works in a pre-commit hook or CI.

With `--changed`, only findings in changed files are shown and counted
toward the exit code. That makes this a good pre-push check, holding your
changes to the standard without failing on problems you didn't touch:

```bash
wbcheck check . --changed --since main --fail-on warning
```

## Fixing: `wbcheck fix`

`wbcheck fix` re-checks the lesson and opens what it found in your editor.
Narrow it with `--code WB401` (repeatable), `--file 'episodes/0*'`,
`--min-severity` (default `warning`), `--source mechanical|ai`, or
`--changed` / `--since REF`.

### In vim or nvim: stay in one session

Every finding loads into the quickfix list, and the editor opens on the
first one. Don't quit between fixes. Work through the list in place:

1. Fix the finding, then `:w`.
2. `]q` (or `:cnext`) to jump to the next one. `[q` / `:cprev` goes back.
3. `:copen` shows the whole list with messages and fixes; `enter` on a line
   jumps there.

When you quit, the lesson is re-checked and you get a count of what you
fixed. Quickfix entries follow your edits within the session, but they don't
know which findings are resolved. To refresh the list mid-session without
quitting, re-run the check into it:

```vim
:wall | cexpr system('wbcheck fix . --print')
```

`--print` just writes `path:line:col: message` lines to stdout, so it also
works for loading findings into an editor that's already open, or
`nvim -q <(wbcheck fix . --print)`. It's worth a mapping:

```lua
vim.keymap.set('n', '<leader>wr', function()
  vim.cmd("wall | cexpr system('wbcheck fix . --print')")
end, { desc = 'wbcheck: save and refresh quickfix' })
```

### In other editors

With any other editor (or with `--step` in vim), it goes one finding at a
time. It shows the code, message, quote, and fix, then `enter` opens the file
at the line, `s` skips, and `q` stops. After each edit it re-checks and says
✔ fixed or ✗ still reported.

### Automatic fixes: `--apply` and `--suggest`

Both show each change as a diff before writing, edit only the part the
finding is about, and refuse if the line changed since the check ran.
Content (prose, placeholders, exercises) is always left to you.

`--apply` makes safe fixes: unambiguous edits that change no meaning. It
asks `y`/`n`/`a`(ll)/`q`, and `--yes` applies them all.

| Code | Fix |
|---|---|
| `WB103` | rename a front-matter `exercise:` typo to `exercises:` |
| `WB213` | set a heading that skips a level to one below the previous heading |

`--suggest` offers editorial changes that are well defined but yours to
decide. Each asks on its own (default no), and `--yes` never applies them.

| Code | Suggestion | Why it's your call |
|---|---|---|
| `WB401` | replace a vague objective opener with an observable verb (Understand → Explain, Know → Identify, ...), keeping the rest verbatim | it changes what the objective promises, and it still needs an exercise that assesses it |
| `WB009` | add an unlisted episode to `config.yaml`'s `episodes:`, never when the file looks like reference content (`WB013`, re-checked from the file itself) | Workbench lets you leave drafts unlisted on purpose; listing one publishes it |

Use both with `--apply --suggest`, then review with `git diff`.

## The AI review: `wbcheck review`

```bash
wbcheck review LESSON --backend claude                     # Anthropic API
wbcheck review LESSON --backend ollama                     # local, free
wbcheck review LESSON --episode 03-sharing.md --backend claude --effort medium
```

Off unless you run it: it's slow, and the `claude` backend costs roughly
$0.10 to $0.25 per episode at `--effort medium`. It adds structured findings
to the saved results (running `check` first if needed), and re-reviewing an
episode replaces that episode's earlier AI findings.

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

Each finding has a severity, a verbatim quote from the episode, the problem,
a suggested fix, and a `scope` label that groups related findings into one
pull request's worth of work.

**Every finding is checked against the text.** A finding whose quote isn't
in the episode is dropped, and the run reports how many were. Matching
tolerates whitespace, smart quotes, markdown emphasis, and `...` elisions.

**The rubric is pinned.** Every prompt includes
[`checker/rubric/`](checker/rubric/): the Carpentries Lab reviewer checklist
plus excerpts of CLDT and the Workbench docs. Nothing is fetched at review
time, so the same lesson gets the same rubric every run. The episode and the
lesson's glossary go in the user message, never the system prompt, so lesson
text can't carry operator authority. Terms already in the glossary aren't
flagged as gaps, and the mechanical findings are included so the model
doesn't repeat them.

If any episode fails (backend down, refusal, timeout), the review saves the
ones that succeeded and exits 1.

| Backend | Needs | Notes |
|---|---|---|
| `claude` | `ANTHROPIC_API_KEY` | Default model `claude-opus-5-5`. `--effort` defaults to `high`; `low`/`medium` are cheaper and faster, `xhigh`/`max` more thorough. The rubric and glossary are prompt-cached across episodes; if a safety classifier declines an episode, the API retries it on a fallback model |
| `ollama` | `ollama serve` and a pulled model | Local and free. Output is constrained to the findings schema, with one retry if the model misses it. Calls time out after 15 minutes |

`--model` overrides the default for either backend.

### Local models (16GB Apple Silicon)

Install [Ollama](https://ollama.com), run `ollama serve`, and
`ollama pull <model>`. `wbcheck doctor` tells you whether the server is up
and the default model is pulled.

| Model | Download | Use it for |
|---|---|---|
| `qwen3.5:9b-q4_K_M` (default) | ~6.6 GB | General review; best quality for the footprint, with headroom on 16GB |
| `qwen3.5:4b` | ~3.4 GB | Faster checks while drafting; use the 9B for a final pass |
| `qwen2.5-coder:7b` | ~4.7 GB | Lessons heavy on shell, Python, or R code |
| `gpt-oss:20b` | ~14 GB | Best local quality if you can close everything else |

On 16GB, don't run a review alongside another large model or a heavy IDE:
swapping slows it down long before memory runs out.

## Browsing in the terminal UI: `wbcheck tui`

```bash
wbcheck tui LESSON
```

A folder → file → rule tree on the left (colored by worst severity), the
findings table on the right, and a detail pane with the message, quote, fix,
guide links, and surrounding source lines.

| Key | Does |
|---|---|
| `enter` (tree) | filter to that file or rule code |
| `space` | select or unselect a finding |
| `o` | open the file at the finding's line in `$VISUAL` / `$EDITOR`; on return it re-checks, and fixed findings drop off |
| `r` | re-run the mechanical checks, keeping AI findings |
| `i` | ignore the selection (or current finding) in `.wbcheck.toml` |
| `c` | file issues: the selection as one issue, or with nothing selected, the visible warnings and errors grouped as `wbcheck issues` would. Confirms first and skips anything already filed |
| `s` / `a` | cycle minimum severity / source (mechanical, AI) |
| `/` | search; `esc` clears every filter |
| `q` | quit |

## Filing GitHub issues: `wbcheck issues`

```bash
wbcheck issues LESSON                   # dry run: the issues it would file
wbcheck issues LESSON --preview         # ...with each body
wbcheck issues LESSON --create          # file them via gh (asks first; -y skips)
wbcheck issues LESSON --group-by file   # one issue per file, even for lesson-wide rules
wbcheck issues LESSON --source ai --min-severity info --repo me/my-fork
```

Each issue is sized for one pull request. A rule that shows up in 3 or more
files gets one lesson-wide issue; other mechanical findings get one issue per
file (`--group-by file` or `rule` forces one or the other). AI findings are
grouped by file and `scope`, with an episode's one-offs sharing an
`ai-suggested` "other suggestions" issue. Each item has a checkbox, a link to
its line at the checked commit, the fix, and a "Why these matter" section
citing the guide. `info` notes are left out unless you pass
`--min-severity info`.

**Re-running doesn't re-file.** Each finding's ID is hidden in the issue
body, and `issues` skips anything already filed in a `wbcheck`-labelled
issue, open or closed, so a won't-fix stays closed. Keep the label and the
hidden ID on the issue for this to work. The repo defaults to the lesson's
GitHub `origin`. If files had uncommitted changes at check time, it warns
first, since their items can't link to GitHub.

## Reports: `wbcheck report`

```bash
wbcheck report LESSON                              # terminal
wbcheck report LESSON --md report.md --json results.json
wbcheck report LESSON --html report.html --open    # needs Quarto
wbcheck report LESSON --pdf report.pdf             # needs Quarto + LaTeX
```

Renders saved results without re-checking. Every format opens with the tool
version and the lesson's metadata from `config.yaml` and `CITATION.cff`, so a
report handed to someone else identifies itself. The markdown, HTML, and PDF
reports have three parts: a checklist of files, an action summary with one
row per shared fix (a problem in 16 places is one row), and per-file detail
in editor order. Line references link to GitHub at the checked commit when
possible. PDFs don't render the severity emoji; severity still shows in the
checkbox and bold rule code.

## Reference

### Rule codes

Every check has a stable code, defined once in
[`checker/rules.py`](checker/rules.py) with why it matters and a link to the
guide section behind it. Codes are never renumbered or reused. `AI201` to
`AI208` are the [AI review's](#the-ai-review-wbcheck-review).

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

A few details:

- Div and heading checks skip fenced code blocks, so a lesson that teaches
  Markdown or shell `#` comments doesn't trip them. Fences follow CommonMark
  and divs follow Pandoc, including `::: {#q .questions}`. Reference-style
  links (`[text][ref]`) aren't checked yet.
- Image paths resolve relative to `episodes/` or the lesson root, and `.html`
  links resolve to the `.md` or `.Rmd` source they're rendered from.
- The objectives, contraction, glossary, and heading-skip checks come from
  the [Collaborative Lesson Development Training](https://carpentries.github.io/lesson-development-training/aio.html)
  (CLDT) and the [Carpentries Lab reviewer](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md)
  and editor checklists, not from sandpaper.

### Ignoring findings: `.wbcheck.toml`

Put a `.wbcheck.toml` at the lesson root and commit it so collaborators
share it:

```toml
[ignore]
codes = ["WB404"]                      # a rule, everywhere
paths = ["episodes/all_exercises.md"]  # every finding in these files (globs ok)
ids = ["8289307d05d3"]                 # single findings, by ID
```

Matching findings are dropped before saving, and reports say how many. The
TUI's `i` key adds IDs here, rewriting the file in this form, so comments in
it aren't kept.

### How saved results work

- Mechanical checks re-run on every `check`, `review`, `fix`, and TUI
  re-check, so they always match the files as they are.
- AI findings are kept between runs, but each file is fingerprinted. If a
  file changes after its review, its AI findings are marked **stale**: shown
  with a note and never filed as issues until you re-run `review`.
- Results record the lesson and git commit they belong to. Results for a
  different lesson are replaced, never merged. `check --episode` keeps the
  rest of the lesson's results only if those files haven't changed;
  otherwise they're marked partial until the next full check.
- Each finding has a 12-character ID, a hash of its code, file, and message
  (not the line number), so it survives unrelated edits. AI finding IDs come
  from the rule, file, and quoted text, so a reworded re-review keeps the
  same ID. IDs are never reassigned, which is what ignoring and issue
  de-duplication rely on.
- For a git URL, results are saved under `./.wbcheck/<host_owner_repo>/`.

### How this relates to sandpaper CI

The Carpentries' CI (`sandpaper::validate_lesson()` and pegboard's
`validate_divs()`, `validate_headings()`, and `validate_links()`) is
authoritative but takes several minutes, and only runs after you push.
`wbcheck` mirrors those rules locally in under a second and adds the CLDT and
Carpentries Lab checks. It's an approximation: sandpaper is still the final
word.

## Development

```bash
git clone https://github.com/ucla-imls-open-sci/carpentries-workbench-checker.git
cd carpentries-workbench-checker
pixi install
pixi run wbcheck check path/to/lesson     # or `pixi shell`, then plain `wbcheck`
```

The package is installed in editable mode, so code changes take effect
immediately.

| Task | Does |
|---|---|
| `pixi run test` | the test suite; no network, models, gh, or Quarto needed (all faked) |
| `pixi run lint` / `lint-fix` | ruff |
| `pixi run refresh-rubric` | re-fetch the AI review's guidance into `checker/rubric/`; read the diff before committing. Fails loudly if an upstream section moved |
| `pixi run ollama-serve` / `pull-models` | run Ollama and pull the local models from the pixi environment |

CI runs the tests and lint, then installs with `install.sh` on Linux and
macOS and runs `wbcheck` from outside the repo, so a file missing from the
package fails the build. `pixi run format` exists but isn't applied
wholesale, since it would reflow intentionally formatted prose strings.

Design notes are in [`design/`](design/), starting with
[`modernization-assessment-2026-09-29.md`](design/modernization-assessment-2026-09-29.md).
Changes are in [CHANGELOG.md](CHANGELOG.md). HTML and PDF reports use a
bundled Quarto extension,
[`checker/quarto/_extensions/checker-report/`](checker/quarto/_extensions/checker-report/),
which owns the look while `report.py` owns the content.

The original flag-based CLI (`pixi run check LESSON ...`) still works from a
development checkout but is superseded by `wbcheck`.
`legacy/proposal_analysis.ipynb` is unrelated to lesson checking and kept for
reference.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Everyone participating is expected to
follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[BSD 3-Clause](LICENSE)
