# Modernization assessment - 2026-09-29

Scope: evaluate the codebase with a focus on the genAI path, and propose a
modernized CLI/TUI design covering issues #21 (addressable issues) and #22
(better TUI tool, AI bridging modules). Assessment only, nothing changed.

## Overall

The mechanical checker is in good shape: 149 tests, careful edge-case
handling, and good comments. The weak spots are architectural:

1. The AI review returns free-form prose, so nothing downstream (issues,
   TUI, dedupe) can address its findings individually. This is the main
   blocker for #21.
2. The RAG layer (LangChain + Chroma + live web fetch + Ollama embeddings)
   costs more than it's worth and makes every backend depend on Ollama.
3. `cli.py:main()` is about 220 lines of argparse and output branching. The
   report renderers work from in-memory findings instead of a saved,
   canonical results file, so you can't check once and then review, render
   or file issues later.

## genAI path (`checker/ai_review.py`)

### What's good
- The Lab reviewer checklist is pinned verbatim as the rubric instead of
  being left to retrieval (`LAB_CHECKLIST`). That was the right call.
- Episode and glossary text are delimited and labeled as untrusted
  (prompt-injection aware), and tests cover it.
- Mechanical findings are fed in with "don't repeat these", which is a
  sensible division of labor.
- Glossary gaps require a quoted phrase, so they can be verified.
- AI is opt-in, and a failure in one episode doesn't sink the run.

### Problems, most important first

1. **Unstructured output.** `review_episode()` returns a string (`:289`).
   Fix: ask for a JSON schema, e.g. a list of `{checklist_item, severity,
   quote, line_hint, problem, suggested_fix, scope}`. Claude supports this
   natively via `output_config.format` / `client.messages.parse()`. Ollama
   accepts a JSON schema in `format=`. Codex has not been verified for this.
2. **The quote is required but never checked.** Once output is structured,
   check each `quote` against the episode text with a substring match or
   whitespace-normalized fuzzy match, then drop or flag findings whose quote
   isn't really in the episode. This turns "trust the model" into
   "verified against the text", and it's the biggest trust improvement
   available.
3. **RAG is overbuilt and fragile.**
   - The three reference pages are fetched live on every run
     (`WebBaseLoader`, `:102`), so a run needs network access and review
     results change whenever upstream docs change.
   - The retrieval query is just `episode_text[:2000]` (`:117`), which
     mostly matches on front matter and the intro, not on content that
     needs guidance.
   - Every backend, including claude and codex, needs a running Ollama for
     embeddings. That dependency caused the 9/15 hang.
   - It pulls in 5 heavy deps: langchain, langchain-community,
     langchain-chroma, chromadb, tiktoken.
   - Fix: vendor curated excerpts of the style guide and CLDT into the repo
     (for example `checker/rubric/*.md`, versioned and dated) and pin them
     into the prompt the way the checklist already is. Current context
     windows make retrieval unnecessary at this size. Deleting the RAG
     layer removes all 5 deps and the Ollama requirement for API backends.
4. **Lesson-level criteria are asked once per episode.** Audience,
   prerequisites, setup and "objectives assessed across the lesson" are
   lesson-scoped, yet every episode call is asked to grade them. The result
   is duplicate or contradictory findings. Split the review into one
   lesson-level pass (config, learner profiles, setup, glossary, episode
   list with objectives) and per-episode passes (writing, exercises, local
   objectives).
5. **Prompt order works against caching.** Stable content (rubric,
   guidance, glossary) is mixed in with per-episode content. Put the stable
   prefix in `system` with `cache_control` and the episode last. Every
   episode after the first then reads the rubric from cache, which is
   cheaper and faster.
6. **Claude defaults are stale.**
   - The default model is `claude-opus-5` (`:84`). The current Opus is
     `claude-opus-5-5`, which is also cheaper ($4/$20 per MTok vs $5/$25).
   - Opus 5.5 defaults to `medium` effort, so the explicit `high` matters.
   - The `"opus" in model or "sonnet" in model` substring gate (`:225`) is
     brittle. Making effort a CLI flag with a sane default is simpler.
   - Refusals (`stop_reason == "refusal"`) aren't handled.
7. **Episodes run one at a time with no progress feedback beyond a stderr
   line.** Options: async concurrency, or the Batches API at half price for
   a whole-lesson review where latency doesn't matter.
8. **No evaluation of the AI review.** Tests only cover prompt string
   assembly. A small golden set of 3-4 episodes with known planted problems
   (vague objective, exercise that doesn't assess, dismissive "simply",
   undefined jargon) would show whether a prompt or model change helped.
   Without it, backend and model choice is guesswork.
9. **Codex passes the whole prompt as argv** (`:255`). It works, but the
   prompt is visible in `ps`, and it's the odd backend out. Consider
   dropping it once a bridge library covers OpenAI models.

### AI bridging libraries (the #22 question)

The goal is to replace LangChain with something thin that gives typed,
structured output across providers. Candidates:

| Library | Fit | Notes |
|---|---|---|
| `pydantic-ai` | Best for structured findings | Pydantic models as the output type, validation plus retry, works with Anthropic, OpenAI and Ollama (via its OpenAI-compatible endpoint). |
| `llm` (Simon Willison) | Best CLI/user ergonomics | Plugins for Ollama, Anthropic and OpenAI; keys and models managed by the user's existing `llm` setup; logs every prompt/response to SQLite for free; supports schemas. Structured-output support varies by plugin, so it needs checking. |
| `instructor` | Structured output only | Mature and narrow, a good choice if the direct SDKs stay. |
| `litellm` | Provider shim | Broad, heavier; not needed at 2-3 backends. |
| Direct SDKs | Minimal deps | `anthropic` plus the `ollama` Python client is about 40 lines total, with no abstraction to fight. |

Recommendation: **pydantic-ai**, because the finding schema is the center
of the redesign and validation retries are exactly what's needed. If you'd
rather keep deps minimal, direct SDKs with a shared Pydantic schema is a
fine second choice. Library versions and capabilities above are from
memory, so verify before committing.

## CLI/TUI redesign (#22)

### Core idea: JSON results as the pivot

```
wbcheck check  <lesson>            -> .wbcheck/results.json  (fast, mechanical)
wbcheck review <lesson> [--backend] -> merges AI findings into results.json
wbcheck report [--md|--html|--pdf|--sarif]   renders from results.json
wbcheck issues [--dry-run|--create]          files GitHub issues from results.json
wbcheck tui                                  browse/triage results.json
```

Every stage reads and writes one file. This removes the `--format`,
`--output`, `--html`, `--pdf` and `--open` tangle from `main()` and lets
you run the slow AI pass separately.

### Libraries
- **Typer** (or **cyclopts**) for subcommands and typed options with good
  `--help`. It replaces the argparse block.
- **Rich** for terminal output: tables, grouped panels, syntax-highlighted
  source excerpts at the finding's line, and a progress bar for the AI
  pass. It replaces the hand-rolled ANSI in `report.py`.
- **Textual** for `wbcheck tui`:
  - left pane: file / category tree with counts
  - center: finding list
  - right: source excerpt at the line, plus hint and guide link
  - keys: `i` ignore (writes to `.wbcheck.toml`), `space` select,
    `g` group the selection into one issue, `c` create issues
    (`gh issue create`), `o` open the file in `$EDITOR` at the line

  Textual apps can also run in a browser (`textual serve`), which helps
  with non-terminal collaborators.
- Package as a console script (`[project.scripts] wbcheck = ...`) so
  `uv tool install` / `pixi global` / `pipx` work, not just
  `pixi run check` inside the repo.

## Addressable issues (#21)

Needs four pieces, mostly mechanical:

1. **Rule codes.** Give every check a stable code, ruff-style (`WB101
   placeholder-keypoint`, `WB2xx` links, `AI3xx` AI checklist items). Each
   code carries a title, a why, a fix and a *specific* guide anchor. This
   is the same work as the open hub task on precise guide citations, so do
   them together.
2. **Stable finding IDs.** Hash rule code + file + normalized message (not
   the line number, which drifts), so re-runs can recognize findings that
   already have an issue filed.
3. **Grouping policy into PR-sized scopes:**
   - mechanical: one issue per (rule, file), or per file for small files
   - AI: use the model's `scope` field (e.g. "episode 3 exercises",
     "lesson glossary") to cluster related findings into one issue
   - each issue body gets: what's wrong, why it matters, checklist of
     locations with links, suggested fix, guide link, and a hidden
     `<!-- wbcheck:id=... -->` marker for dedupe
4. **`wbcheck issues`.** Dry-run prints the issue bodies. `--create` files
   them via `gh`, skipping IDs already present in open issues, with labels
   (`wbcheck`, rule family, `ai-suggested` for model findings, so humans
   know to verify).

Optional: **SARIF output** would put the mechanical findings as inline
annotations on lesson PRs via GitHub code scanning, which is a cheap
integration once rule codes exist.

## Smaller code-health notes
- `lesson_check.py` (1196 lines) parses markdown with regexes plus a
  code-fence mask. A real parser (`markdown-it-py` with the fenced-div
  plugin) would cut a class of false positives around fences, divs and
  links. Do this only if false positives keep showing up; the current
  approach is well tested.
- Repo root has leftover generated reports and `proposal_analysis.ipynb`.
  Gitignore `*-report.*` and `report.*`, and move or delete the notebook.
- Three stale local branches, one of which (`lesson-quality-checks`) has
  unclear status.

## Suggested sequencing

1. Finding schema + rule codes + stable IDs (unblocks everything else,
   folds in the guide-citation task).
2. JSON-as-pivot + Typer subcommands + Rich terminal output.
3. AI rework: drop RAG and vendor the rubric, structured output via
   pydantic-ai, quote verification, lesson vs episode split, caching, and
   the Opus 5.5 default.
4. `wbcheck issues` (#21).
5. Textual TUI (#22). It's the most fun but the least load-bearing, and it
   is much easier once steps 1-4 exist.
6. Golden-set eval for the AI review, before tuning prompts or models.
