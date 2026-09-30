"""Rule help: one explanation per rule, built from checker/rules.py and
shared by `wbcheck explain`, `wbcheck rules`, the TUI detail pane, the
markdown report's appendix, and issue drafts.

This module returns content, not styling: plain text and markdown, which
callers escape or style for their destination. It imports no AI, network,
or UI packages, so help works offline in a core install.
"""

from __future__ import annotations

import difflib
import textwrap
from dataclasses import dataclass

from checker.fix import fix_capability
from checker.rules import AUTHORITY_LABELS, DETECTION_LABELS, REFERENCES, RULES, TOPICS, Rule

EXPLAIN_HINT = "For context and exceptions: wbcheck explain CODE"
AI_NOTE = (
    "AI findings are suggestions: each one's quote was matched in the file, which shows where it "
    "points, not that the judgment is right."
)
FIX_LABELS = {
    "none": "none; this needs an author's judgment.",
    "conditional-automatic": "`wbcheck fix --apply` can fix it where the source still matches what "
    "was checked; review the diff.",
    "editorial": "`wbcheck fix --suggest` offers a draft change that you confirm one at a time; "
    "`--yes` never applies it.",
}


@dataclass(frozen=True)
class Source:
    """One cited source section, resolved for display."""

    label: str
    url: str
    supports: str
    provenance: str
    checked_on: str


@dataclass(frozen=True)
class RuleHelp:
    """Everything shown about a rule, in display order."""

    rule: Rule
    fix: str
    sources: tuple[Source, ...]

    @property
    def classification(self) -> str:
        """Authority, detection, and topic: what kind of claim the rule makes."""
        r = self.rule
        return f"{AUTHORITY_LABELS[r.authority]} · {DETECTION_LABELS[r.detection]} · topic: {r.topic}"

    @property
    def labels(self) -> str:
        """The rule's default severity word plus its classification, for rule
        help. Next to a finding, show the finding's own severity instead:
        AI findings can be info under a rule whose default is warning."""
        return f"{self.rule.default_severity} (default) · {self.classification}"

    def sections(self) -> list[tuple[str, list[str], bool]]:
        """(heading, paragraphs, is_list) in display order; empty sections
        are left out."""
        r = self.rule
        out: list[tuple[str, list[str], bool]] = [
            ("What it checks", [r.checks], False),
            ("Why it matters", [r.why], False),
            ("What to do", [r.response], False),
        ]
        if r.exceptions:
            out.append(("When keeping it is reasonable", list(r.exceptions), True))
        if r.limitations:
            out.append(("Limits of this check", list(r.limitations), True))
        if r.context:
            out.append(("Context", [r.context], False))
        out.append(("Severity", [f"Reported as {r.default_severity} by default. {r.severity_reason}"], False))
        out.append(("Automatic fix", [FIX_LABELS[self.fix]], False))
        return out


def rule_help(code: str | None) -> RuleHelp | None:
    """Help for a registered rule code, or None."""
    rule = RULES.get(code or "")
    if rule is None:
        return None
    sources = tuple(
        Source(ref.label, ref.url, ref.supports, ref.provenance, ref.checked_on)
        for ref in (REFERENCES[key] for key in rule.references)
    )
    return RuleHelp(rule, fix_capability(rule.code), sources)


def resolve(query: str) -> Rule | None:
    """A rule by code (any case) or by its kebab-case name."""
    q = query.strip()
    return RULES.get(q.upper()) or next((r for r in RULES.values() if r.name == q.lower()), None)


def suggestions(query: str) -> list[str]:
    """Codes or names close to an unknown query, for a helpful error."""
    q = query.strip()
    candidates = [*RULES, *(r.name for r in RULES.values())]
    return difflib.get_close_matches(q.upper(), list(RULES), n=3) or difflib.get_close_matches(
        q.lower(), candidates, n=3, cutoff=0.5
    )


def search(query: str | None = None, topic: str | None = None) -> list[Rule]:
    """Rules whose code, name, or explanation mentions `query` (any case),
    optionally in one topic. Raises ValueError for an unknown topic."""
    if topic is not None and topic not in TOPICS:
        raise ValueError(f"unknown topic `{topic}`; one of: {', '.join(TOPICS)}")
    needle = (query or "").casefold()
    out = []
    for r in RULES.values():
        if topic and r.topic != topic:
            continue
        text = " ".join([r.code, r.name, r.title, r.checks, r.why, r.response, r.context, *r.exceptions])
        if needle in text.casefold():
            out.append(r)
    return out


# -- plain text (CLI) -------------------------------------------------------------


def _wrap(text: str, indent: str, bullet: bool = False, width: int = 88) -> list[str]:
    first = indent + ("- " if bullet else "")
    rest = indent + ("  " if bullet else "")
    return textwrap.wrap(text, width=width, initial_indent=first, subsequent_indent=rest) or [first.rstrip()]


def render_text(h: RuleHelp) -> str:
    """The full explanation as plain text, for `wbcheck explain`. URLs are
    printed in full so they work without terminal hyperlinks."""
    r = h.rule
    lines = [f"{r.code}  {r.title}", h.labels, ""]
    for heading, paragraphs, is_list in h.sections():
        lines.append(heading)
        for p in paragraphs:
            lines += _wrap(p, "  ", bullet=is_list)
        lines.append("")
    if h.sources:
        lines.append("Sources")
        for s in h.sources:
            lines += _wrap(f"{s.label} ({s.provenance}; checked {s.checked_on})", "  ", bullet=True)
            lines.append(f"    {s.url}")
            lines += _wrap(f"Supports: {s.supports}", "    ")
        lines.append("")
    if r.related:
        lines.append(f"Related: {', '.join(r.related)}")
    return "\n".join(lines).rstrip() + "\n"


# -- markdown (reports, issues) ------------------------------------------------------


def render_markdown(h: RuleHelp, heading: str = "###") -> str:
    """The full explanation as markdown, for the report appendix. Every
    source shows its plain URL, so printed and PDF copies still work."""
    r = h.rule
    lines = [f"{heading} {r.code}: {r.title}", "", f"_{h.labels}_", ""]
    for title, paragraphs, is_list in h.sections():
        lines.append(f"**{title}.** " + ("" if is_list else " ".join(paragraphs)))
        if is_list:
            lines += [f"- {p}" for p in paragraphs]
        lines.append("")
    if h.sources:
        lines.append("**Sources.**")
        lines += [f"- {s.label} ({s.provenance}; checked {s.checked_on}): <{s.url}>. {s.supports}"
                  for s in h.sources]
        lines.append("")
    if r.related:
        lines += [f"**Related:** {', '.join(r.related)}", ""]
    return "\n".join(lines)


def issue_summary(h: RuleHelp) -> list[str]:
    """A compact explanation for an issue body: why, what to do, the most
    relevant exception or limit, and sources. Once per rule, not per item."""
    r = h.rule
    lines = [f"- **{r.code}** {r.title}: {r.why} Next: {r.response}"]
    caveat = (r.exceptions or r.limitations or (None,))[0]
    if caveat:
        lines.append(f"  - Keep in mind: {caveat}")
    if h.sources:
        lines.append("  - Sources: " + " · ".join(f"[{s.label}]({s.url})" for s in h.sources))
    return lines
