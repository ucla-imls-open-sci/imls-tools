Carpentries Workbench Checker
==============================

[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)

Local pre-flight checks for [Carpentries Workbench](https://carpentries.github.io/workbench/)
lessons: a fast, deterministic structure check (front matter, required
`:::` blocks, headings, links/images), plus an optional AI narrative review
of writing and pedagogy. Point it at a local lesson directory or a lesson's
git URL; run it before opening a PR instead of waiting on the sandpaper CI
build.

## Why two layers

Real Carpentries CI (`sandpaper::validate_lesson()` and the `pegboard`
package's `validate_divs()` / `validate_headings()` / `validate_links()`, run
inside a Docker container on every PR) is authoritative but slow — several
minutes, and it only runs after you push. `checker/lesson_check.py` mirrors
the same rules locally, in under a second, with no dependencies beyond
Python: required front matter (`title`, `teaching`, `exercises`), the three
required top-level blocks (`questions`, `objectives`, `keypoints`), balanced
and recognized `:::` div types, heading rules (start at `##`, no `#`, no
duplicates), broken internal links/images (including the
`episodes/fig/`-relative image convention Workbench actually uses, and the
fact that `.html` links point at rendered `.md` sources, not literal files),
and whether an episode (or `learners/setup.md`, `instructors/instructor-notes.md`,
`profiles/learner-profiles.md`) is still the unedited scaffold Sandpaper
generated, structurally complete but never actually written.

None of that requires a model. The AI layer (`checker/ai_review.py`) is for
the part a deterministic checker can't do: whether a challenge is
pedagogically sound, whether the tone matches the
[style guide](https://carpentries.github.io/sandpaper-docs/instructor/style.html),
whether something will confuse a learner encountering it fresh. It's given
the mechanical findings as context so it doesn't repeat them.

This is a local approximation, not a replacement for the real CI check —
sandpaper is still the final word.

## Setup

Uses [pixi](https://pixi.sh) for the whole environment, including Ollama
itself (installed from conda-forge, no separate `brew install ollama` step
needed):

```bash
pixi install
```

## Running the checker

### `wbcheck` (new subcommand CLI)

`wbcheck` splits a run into steps that share one results file,
`<lesson>/.wbcheck/results.json`. That directory ignores itself with its own
`.gitignore`, so the lesson repo doesn't need a change. Run it as
`pixi run wbcheck ...`, or as plain `wbcheck ...` inside `pixi shell`.

```bash
# Fast mechanical checks: prints the report, saves results. Exit 1 on errors.
wbcheck check ./my-lesson
wbcheck check ./my-lesson --source      # show the offending source line under each finding
wbcheck check ./my-lesson --blame       # record who last changed each file
wbcheck check https://github.com/librarycarpentry/lc-git.git   # temp clone; results saved under ./.wbcheck/

# Slow AI review, added to the same results file (runs `check` first if needed)
wbcheck review ./my-lesson --backend claude

# Re-render saved results without re-checking
wbcheck report ./my-lesson                         # terminal
wbcheck report ./my-lesson --md report.md --json results.json
wbcheck report ./my-lesson --html report.html --open
wbcheck report ./my-lesson --pdf report.pdf
```

Rule codes in the terminal report link to their guide section in terminals
that support hyperlinks (iTerm2, Ghostty, WezTerm, VS Code, recent GNOME
Terminal).

### Legacy flag-based CLI

Still works unchanged during the transition, and is what the `checklesson`
shell function and `/lesson-checker` skill call today.

```bash
# Mechanical checks only, terminal output
pixi run check ./my-lesson

# Or check a lesson straight from its git URL (clones to a temp dir, cleans up after)
pixi run check https://github.com/librarycarpentry/lc-git.git

# Markdown checklist you can paste into a PR description or read locally
pixi run check ./my-lesson --format markdown --output report.md

# Same, rendered to HTML with Quarto if you have it installed (falls back to
# a warning + the markdown file if you don't)
pixi run check ./my-lesson --format markdown --output report.md --html

# --open launches the rendered HTML in your default browser once it's built
# (requires --html; a no-op warning otherwise)
pixi run check ./my-lesson --format markdown --output report.md --html --open

# PDF, for sharing with someone who doesn't want a repo checkout or a browser
# tab -- also via Quarto, additionally needs a LaTeX distribution
# (`quarto install tinytex`, or an existing MacTeX/TeX Live on PATH)
pixi run check ./my-lesson --format markdown --output report.md --pdf

# One episode only
pixi run check ./my-lesson --episode 03-sharing.md

# Machine-readable, e.g. for a CI step of your own
pixi run check ./my-lesson --format json

# Annotate each file's findings with who last changed it, date, short SHA --
# turns the markdown report into something you can split straight into
# per-owner follow-up issues. Requires my-lesson to be a git repo; silently
# skipped (no annotations, no error) otherwise.
pixi run check ./my-lesson --format markdown --blame --output report.md
```

Exit code is `1` if any error-level finding was reported, `0` otherwise —
safe to use in a pre-commit hook or your own CI step.

### Reading the markdown/HTML report

Every report format (terminal, markdown, JSON) opens with which tool
generated it (`carpentries-workbench-checker vX.Y.Z`) and, when
`config.yaml` and `CITATION.cff` are present, who and what it's about:
lesson title, carpentry, life cycle, license, source repo, authors, and
contact -- so a report handed to someone else identifies itself and the
lesson without extra context. Missing fields (no `CITATION.cff`, an empty
`config.yaml`) just drop from the block rather than showing blank lines.
The `--html`/`--pdf` document's own title (the browser tab, the PDF's
cover/metadata title) is the lesson's title too, not a generic "Lesson
Check Report" -- it falls back to that generic title only when
`config.yaml` has none.

The markdown report (and the HTML/PDF built from it) has three parts:

1. **Files** -- one checkbox per location with an issue count, linking down
   into that file's own section, for file-level triage before reading detail.
2. **Action summary** -- a table, one row per *shared fix* across the whole
   lesson (same category, same exact hint text), not one row per finding.
   A problem repeated many times (the same duplicate-heading warning in 16
   places) shows up as one row with `Occurrences: 16`, not 16 near-identical
   lines -- this is what actually answers "what's off, what needs to
   change" at a glance, which per-finding detail can't.
3. **Per-file detail**, one `## location` section per file (matching the
   order you'd actually fix things in an editor). Within a file, findings
   that share an exact `hint` still collapse into one `**Change:**` +
   occurrence checklist instead of N separate cards, closed with a single
   `**Guide:**` link -- so a file with 8 findings that are really "one
   repeated problem + two one-offs" reads as 3 blocks, not 8 lines.

Every finding whose category has a canonical Workbench/Carpentries doc
(`config`, `front-matter`, `divs`, `headings`, `links`, `objectives`,
`style`) links to it via that `**Guide:**` line. `boilerplate` findings
don't get one, since it's a check this tool invented rather than something
sandpaper/pegboard document, so their instance-specific hints carry the
explanation instead. Each occurrence line links back to its source: a real
GitHub blob URL anchored to the line (`#L42`) when the lesson directory is
a GitHub repo, plain `` `path:line` `` text otherwise. Terminal output gets
the same line references as plain `path:line` tokens, which VS Code's
integrated terminal (and several others) auto-links to jump straight to
that line.

This structure (file-level triage, then a cross-file pattern summary, then
file-first detail with same-fix collapsing) came out of a `/validate-external`
round on the original per-finding-per-line design -- see
[`design/validation-prompt-report-scannability-2026-08-31.md`](design/validation-prompt-report-scannability-2026-08-31.md).

`--pdf` renders the same markdown through Quarto with a `pdf` target instead
of `html` -- same checklist, same clickable links (as real hyperlinks, not
just blue text). One difference: the ❌/⚠️/ℹ️ severity icons don't render in
PDF (LaTeX's default font has no emoji glyphs, so they're silently dropped);
severity is still legible from the checkbox/bullet plus the bold category
name, but it's not as visually distinct as the terminal/HTML output.

### The report's look: a Quarto format extension

`--html`/`--pdf` render through a bundled Quarto custom format extension at
[`_extensions/checker-report/`](_extensions/checker-report/) (`_extension.yml`
+ `checker-report.scss`), not inline options in `report.py`. `report.py`
copies that directory next to the generated `.qmd` at render time -- Quarto
only discovers `_extensions/` as a sibling of the file being rendered, so
this happens automatically; nothing to install separately.

The extension owns *how* every report looks (typography, link color, PDF
margins/colorlinks, the rule under each `## file` heading); `report.py`
still owns *what* it says. Colors are The Carpentries' own official values
(navy `#071159` for links, red `#FF4955` for the file-heading rule -- see
the extension's own README for sourcing); the logo mark itself isn't
embedded since the logo repo ships with no license and Carpentries'
own docs require prior approval to use a derived/modified copy of it.
To change the report's appearance further, edit the extension, not
`report.py`. `pixi run test` includes a couple of lightweight checks
(`_extension.yml` exists and parses, declares both `html` and `pdf`) that
don't need Quarto installed; they just guard against the extension
directory silently going missing or invalid.

### Adding the AI review

Off by default: it costs time, and for `claude` it costs API usage.

```bash
wbcheck review ./my-lesson --backend ollama                  # local, free
wbcheck review ./my-lesson --backend claude                  # Anthropic API
wbcheck review ./my-lesson --episode 03-sharing.md --backend claude --effort medium
pixi run check ./my-lesson --ai --backend claude             # legacy CLI, same review as prose
```

The review returns **structured findings**, not an essay. Each one has a
rule code by area, a severity, a verbatim quote from the episode, the
problem, a suggested fix, and a `scope` label that groups related findings
into one pull request's worth of work:

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

**Every finding is checked against the text.** The model has to quote the
episode verbatim, and findings whose quote isn't actually in the episode are
dropped (tolerant of whitespace, smart quotes, markdown emphasis, and `...`
elisions). The run reports how many were dropped. So every AI finding in a
report points at a real line you can check, and a hallucinated finding can't
get through.

AI findings are saved in the results file next to the mechanical ones
(`"source": "ai"`) and render in every report format with their quote.
Re-reviewing an episode replaces its earlier AI findings.

**What the model grades against** is pinned into every prompt from
[`checker/rubric/`](checker/rubric/): the Carpentries Lab reviewer checklist,
plus excerpts of the Collaborative Lesson Development Training and Workbench
docs. Nothing is fetched at review time, so the same lesson gets the same
rubric every run, and no network or Ollama is needed for the guidance itself.
To pick up upstream changes, run `pixi run refresh-rubric`, read the diff,
and commit it. The script fails loudly if an upstream section it expects has
moved.

The lesson glossary (`learners/reference.md`, treated as empty while it's
still the scaffold placeholder) goes into the prompt too, so glossary-gap
findings skip terms already defined.

| Backend | What it needs | Notes |
|---|---|---|
| `ollama` | `pixi run pull-models` (see below), `ollama serve` running | Fully local and free. Output is constrained to the findings schema, with one automatic retry if a local model still misses it |
| `claude` | `ANTHROPIC_API_KEY` set, or `ant auth login` | Default `claude-opus-5-5`, `--effort high` (`low`/`medium` are cheaper and faster; `xhigh`/`max` are more thorough). The rubric and glossary are prompt-cached across episodes. If a safety classifier declines an episode, the API retries it on a fallback model instead of failing |

`--model` overrides the default for whichever `--backend` you picked. The
old `codex` backend was removed. It couldn't enforce the findings schema,
and it shelled out to a CLI with the whole prompt as an argument.

## Recommended local models (16GB Apple Silicon)

Pull them with pixi:

```bash
pixi run pull-models          # qwen3.5:9b-q4_K_M (default, balanced)
pixi run pull-models-small     # qwen3.5:4b (faster, lighter)
pixi run pull-models-coding    # qwen2.5-coder:7b (for code-heavy lessons)
```

| Model | Download | Use it for | Why |
|---|---|---|---|
| `qwen3.5:9b-q4_K_M` (default) | ~6.6 GB | General episode review | Best balance of quality and footprint at this size — 256K context, leaves real headroom on 16GB while your browser/editor are also open |
| `qwen3.5:4b` | ~3.4 GB | Quick iterative checks | Noticeably faster, still coherent; use while drafting, switch to the 9B for a final pass |
| `qwen2.5-coder:7b` | ~4.7 GB | Lessons with heavy code blocks (shell, Python, R episodes) | Coder-tuned variant reviews code samples more carefully than the general model |
| `gpt-oss:20b` | ~14 GB | A stretch option if you want the best local quality and can close everything else | Runs on 16GB via MXFP4 quantization, but leaves little headroom — expect it to be slow with other apps open |

Don't run the checker's Ollama backend and something else memory-hungry
(another large model, a heavy IDE) at the same time on 16GB — swap will tank
throughput long before you run out of RAM outright.

## What each check maps to

| Category | What we check | Mirrors |
|---|---|---|
| `config` | Placeholder values left unfilled, `created` date, episode list vs. files on disk, episode files under `episodes/` with no `.md`/`.Rmd` extension (invisible to both Sandpaper and this checker's own glob otherwise) | `sandpaper::validate_lesson()` |
| `front-matter` | `title` / `teaching` / `exercises` present and numeric, episode length (`teaching`+`exercises`) roughly 20–60 min | `sandpaper::validate_lesson()`, [CLDT episode scope guidance](https://carpentries.github.io/lesson-development-training/aio.html) |
| `divs` | Required `questions`/`objectives`/`keypoints`, balanced `:::` fences, recognized div types, challenge/solution counts | `pegboard::validate_divs()` |
| `headings` | First heading is `##`, no `#`, no duplicate headings | `pegboard::validate_headings()` |
| `links` | Missing alt text, broken internal links/images (including `episodes/fig/`-relative images and `.html`→`.md` resolution), generic link text (`"click here"`) | `pegboard::validate_links()`, [Carpentries Lab reviewer checklist](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md) |
| `objectives` | Weak/unmeasurable objective verbs (`know`, `understand`, `appreciate`, ...) vs. action verbs (`explain`, `choose`, `predict`, ...) | CLDT's SMART objectives guidance |
| `style` | Heavy contraction use | Carpentries Lab reviewer checklist (accessibility, translation/ESL learners) |
| `boilerplate` | Unedited `sandpaper::create_lesson()` scaffold left in place: an episode's title or body still the generated default, or a `questions`/`objectives`/`keypoints` block that exists but only holds placeholder bullets (`keypoint1`, `Put questions here`, ...); same idea applied to `learners/setup.md`, `learners/reference.md`, `instructors/instructor-notes.md`, `profiles/learner-profiles.md`, which the checks above never look at since they aren't episodes | CLDT, a structurally-complete episode (passes every check above) can still be entirely unwritten, this is the gap between "the required blocks exist" and "someone wrote the lesson" |
| `config` | *(also)* missing lesson glossary (`reference.md`); a file under `episodes/` that's unlisted in `episodes:` *and* has none of the three required blocks -- a strong signal it's misplaced reference content (e.g. a glossary or resources page) rather than an unwritten episode, regardless of what it's named | Carpentries Lab reviewer checklist |

Div and heading checks skip content inside fenced code blocks (```` ``` ````/`~~~`) — a lesson that teaches Markdown, Workbench syntax, or shell `#` comments will contain literal `:::`/`#` text that isn't a real div or heading.

### Rule codes and finding IDs

Every check has a stable rule code, ruff-style, shown in brackets in the
terminal report (`[WB204]`) and inline in the markdown report. The registry
in [`checker/rules.py`](checker/rules.py) defines each code's name, why it
matters, and the most specific guide section that states the rule.

| Range | Covers |
|---|---|
| `WB0xx` | `config.yaml`, episode list, lesson-level files |
| `WB1xx` | episode front matter, scaffold/placeholder content, support files |
| `WB2xx` | fenced divs and headings |
| `WB3xx` | links and images |
| `WB4xx` | objectives and style |
| `AI2xx` | AI review findings, one code per review area (see [Adding the AI review](#adding-the-ai-review)) |

Codes are never renumbered or reused. Each finding in `--format json` output
also carries an `id`: a hash of its code, file, and message with line numbers
and counts stripped, plus an occurrence number for repeats in the same file.
The same problem keeps the same `id` when unrelated edits move it, which is
what issue filing and suppression key on (#21, #23).

The `objectives`, `style`, and glossary checks aren't things `sandpaper`/`pegboard` check at all — they come from [Collaborative Lesson Development Training](https://carpentries.github.io/lesson-development-training/aio.html) and [The Carpentries Lab's reviewer checklist](https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md), the same two sources pinned into the AI review's prompt (see `checker/rubric/`), so it grades against the same rubric a human Lab reviewer would.

## Testing

```bash
pixi run test
```

Unit tests cover the mechanical checks only (`checker/lesson_check.py`) — no
network access or local models needed. The AI review layer isn't covered by
automated tests since it calls out to live models; it's been manually
smoke-tested against a real public lesson for all three backends.

## Linting

```bash
pixi run lint        # ruff check checker tests
pixi run lint-fix    # same, with --fix for the auto-fixable subset
```

Runs in CI alongside the test suite. Covers unused imports/vars, import
order, missing docstrings on public functions/classes (`checker/` only,
`tests/*.py` is exempt, pytest's own naming convention documents test
intent), and outdated syntax patterns. `pixi run format` (`ruff format`)
exists too, but isn't run in CI or applied wholesale, it would reflow a lot
of intentionally-formatted code (long hint strings, grouped constant
tuples) for cosmetic reasons alone.

## Migrating from the old scripts

This replaces `content-checker/` (`content_check.py`, `content_check_cli.py`,
`content_check.sh`) and `llama-checker.py`, which are removed. The old
`content_check.sh -U <url>` remote-check and `-o <file>` output-to-file
options are now `pixi run check <url>` and `--output <file>`; the GUI/CLI
episode picker is gone in favor of `--episode <name>` (scripting-friendly,
and doesn't hardcode a contributor's home directory the way the old shell
script did).

`legacy/proposal_analysis.ipynb` (scores lesson proposal PDFs against a rubric via
the OpenAI API) is unrelated to lesson checking and untouched here — it
still uses the legacy `openai.Completion.create` API and could use its own
pass at some point.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Everyone participating is expected
to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[BSD 3-Clause](LICENSE)
