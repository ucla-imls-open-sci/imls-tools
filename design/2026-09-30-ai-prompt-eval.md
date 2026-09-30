# AI prompt evaluation for the standards review (2026-09-30)

CONTRIBUTING asks for a real `wbcheck review` when the AI prompt changes.
#57 changed `checker/ai_review.py`'s instructions (evidence limits for
audience, glossary, accessibility, and accuracy; no "reviewed separately"
claim) and the empty-glossary text. This compares the 0.2.1 prompt with the
new one on real episodes.

## Setup

- Old: wbcheck 0.2.1 (`9032b05`). New: `main` after #57 (`e620d72`).
- `--backend claude --effort medium` (default model), two runs per version per
  episode, eight reviews in all. Scratch copies of the lessons; nothing in a
  real lesson changed.
- Episode A: `lc-open-hw/episodes/introduction.md` (four figures) with the local
  glossary **removed**, to exercise the new empty-glossary wording.
- Episode B: `lc-reproducible-research/episodes/making-research-checkable.md`,
  local glossary present.

A local Ollama run was tried first and abandoned: the default
`qwen3.5:9b-q4_K_M` context is 4,096 tokens while the system prompt alone is
~8,400, so Ollama silently truncates every local review (filed as #66); with a
16k context every review hit wbcheck's 15-minute timeout on a 16GB Mac.

## Results

| | Old run 1 | Old run 2 | New run 1 | New run 2 |
|---|---|---|---|---|
| Episode A findings | 12 | 12 | 12 | 12 |
| Episode B findings | 10 | 12 | 12 | 11 |

All eight runs finished (31-47 s each) with no refusals, schema failures, or
dropped quotes.

By area:

- **Glossary (AI206).** New findings say "not in the local glossary" and ask
  the author to check, rather than asserting the term is missing. In the
  no-glossary episode they're framed as unexplained acronyms/jargon (FAIR,
  STL), not as a missing glossary. The new prompt produced more glossary
  suggestions on episode B (2 and 4 vs 1 and 1), all at info.
- **Accessibility (AI207).** Both versions critique alt text from the source.
  Old run 2 guessed at image content ("This appears to be a diagram of
  multiple domains"); the new runs stay with what the source says ("may not
  convey any labels...", "does not describe what the figure shows"). Both
  versions sometimes file contractions or heading levels under AI207, which
  overlaps the mechanical checks; unchanged by this prompt.
- **Audience (AI203).** The old prompt gave none; the new one gave three, all
  info and all phrased as an assumed prerequisite ("assumes learners are
  familiar with library values"), which is the intended framing. It's a new
  kind of finding authors will see.
- **Accuracy (AI208).** No measurable change: 5 of 10 (old) vs 5 of 9 (new)
  hints say what to run or check. The instruction added ("say what to run or
  check") didn't move this at `--effort medium`.

## Verdict

The prompt change is safe to ship: same volume and reliability, better-hedged
glossary and accessibility findings, audience findings phrased as questions.
It doesn't make accuracy findings reliably actionable; a follow-up could put
that requirement in the output schema rather than the prose instructions.

Limits: two episodes, two runs each, one model, one effort level. This is a
before/after sanity check, not the golden-set evaluation in #29. The
judgments themselves weren't checked by a human expert.
