"""Turn saved results into GitHub issues sized for one pull request each (#21).

Grouping:
  auto (default)  a mechanical rule found in AUTO_RULE_MIN_FILES or more files
                  gets one lesson-wide issue (e.g. "rewrite vague objectives");
                  everything else is grouped as `file`.
  file            mechanical findings: one issue per file.
                  AI findings: one issue per (file, scope), the model's own
                  label for "fix these together".
  rule            one issue per rule code, across files (e.g. every missing
                  alt text in the lesson), for sweeping one kind of fix.

Every finding's stable ID (see Finding.id) is embedded in the issue body as
an HTML comment, `<!-- wbcheck:id=... -->`. Before filing, existing issues
labelled `wbcheck` (open or closed) are scanned for those markers and any
finding already filed is left out, so re-running doesn't file it again, and
a finding closed as won't-fix stays closed. This relies on the ID staying
the same (see Finding.id) and on the marker and label being left in place.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field

from checker import __version__
from checker.report import SEVERITY_ICON_PLAIN, SEVERITY_ORDER, Finding, _markdown_location_link
from checker.results import Results
from checker.rules import get_rule

WBCHECK_LABEL = "wbcheck"
AI_LABEL = "ai-suggested"
LABEL_COLORS = {WBCHECK_LABEL: "5319e7", AI_LABEL: "fbca04"}
ID_MARKER_RE = re.compile(r"<!-- wbcheck:id=([0-9a-f]{12}) -->")
OTHER_SCOPE = "other suggestions"
AUTO_RULE_MIN_FILES = 3
TOOL_URL = "https://github.com/ucla-imls-open-sci/carpentries-workbench-checker"
_GITHUB_BASE_RE = re.compile(r"^https://github\.com/(?P<repo>[^/]+/[^/]+)/blob/(?P<sha>[0-9a-f]+)$")


@dataclass
class IssueDraft:
    """One issue to file: title, markdown body, labels, and the IDs of the
    findings it covers."""

    key: str
    title: str
    body: str
    labels: list[str]
    findings: list[Finding] = field(default_factory=list)

    @property
    def finding_ids(self) -> list[str]:
        """IDs of every finding in this issue."""
        return [f.id for f in self.findings]


def repo_from_results(results: Results) -> str | None:
    """`owner/name` of the lesson's GitHub origin, from the blob base
    recorded at check time; None if the lesson wasn't a GitHub repo."""
    match = _GITHUB_BASE_RE.match(results.github_base or "")
    return match["repo"] if match else None


def _sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (f.location or "", f.line if f.line is not None else -1))


def _counts_label(findings: list[Finding]) -> str:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    names = {"error": "error", "warning": "warning", "info": "note"}
    parts = [
        f"{counts[s]} {names[s]}{'s' if counts[s] != 1 else ''}"
        for s in sorted(counts, key=lambda s: SEVERITY_ORDER.get(s, 9))
    ]
    return ", ".join(parts)


def _group(findings: list[Finding], group_by: str) -> dict[str, list[Finding]]:
    wide_codes: set[str] = set()
    if group_by == "auto":
        files_per_code: dict[str, set[str]] = {}
        for f in findings:
            if f.source != "ai" and f.code:
                files_per_code.setdefault(f.code, set()).add(f.location or "lesson")
        wide_codes = {c for c, files in files_per_code.items() if len(files) >= AUTO_RULE_MIN_FILES}
    groups: dict[str, list[Finding]] = {}
    for f in findings:
        location = f.location or "lesson"
        if group_by == "rule" or (f.code in wide_codes and f.source != "ai"):
            key = f"rule:{f.code or f.category}"
        elif f.source == "ai":
            key = f"ai:{location}:{(f.scope or 'general').strip().lower()}"
        else:
            key = f"file:{location}"
        groups.setdefault(key, []).append(f)
    # A one-suggestion scope isn't worth its own issue: fold a file's AI
    # singletons into one "other suggestions" issue for that file.
    for key in [k for k, v in groups.items() if k.startswith("ai:") and len(v) == 1]:
        location = key[len("ai:"):].rpartition(":")[0]
        merged = groups.setdefault(f"ai:{location}:{OTHER_SCOPE}", [])
        if merged is not groups[key]:
            merged.extend(groups.pop(key))
    return groups


def _title(key: str, findings: list[Finding]) -> str:
    kind, _, rest = key.partition(":")
    if kind == "rule":
        rule = get_rule(rest)
        name = f"{rest} {rule.title}" if rule else rest
        n_files = len({f.location for f in findings})
        return f"{name} ({len(findings)} in {n_files} file{'s' if n_files != 1 else ''})"
    if kind == "ai":
        location, _, scope = rest.rpartition(":")
        label = scope if scope == OTHER_SCOPE else (findings[0].scope or scope)
        return f"{location}: {label} (AI review, {len(findings)} suggestion(s))"
    codes = ", ".join(sorted({f.code or f.category for f in findings}))
    return f"{rest}: {_counts_label(findings)} ({codes})"


def _finding_item(f: Finding, github_base: str | None, dirty: frozenset[str]) -> list[str]:
    where = _markdown_location_link(f.location or "lesson", f.line, github_base, dirty)
    box = "- [ ]" if f.severity in ("error", "warning") else "-"
    lines = [f"{box} {SEVERITY_ICON_PLAIN.get(f.severity, '')} **{f.code or f.category}** {where}: {f.message}"]
    if f.quote:
        lines.append(f"  > {f.quote}")
    if f.hint:
        lines.append(f"  Fix: {f.hint}")
    lines.append(f"  <!-- wbcheck:id={f.id} -->")
    return lines


def _body(key: str, findings: list[Finding], results: Results) -> str:
    dirty = frozenset(results.dirty_files)
    match = _GITHUB_BASE_RE.match(results.github_base or "")
    at_commit = f" at commit `{match['sha'][:12]}`" if match else ""
    checked = (results.generated or "")[:10]
    lines = [
        f"<!-- wbcheck:group={key} -->",
        f"Found by [`wbcheck`]({TOOL_URL}) v{__version__} on {checked}{at_commit}. "
        "Each item links to the line it's about.",
        "",
    ]
    if any(f.source == "ai" for f in findings):
        lines += [
            "> [!NOTE]",
            "> These come from an AI review of the episode. Each one quotes the lesson text it's about, "
            "and the quote was checked against the file, but the judgment is a suggestion: "
            "check it before acting, and close any item you disagree with.",
            "",
        ]
    lines += ["### To fix", ""]
    for f in _sort_findings(findings):
        lines += _finding_item(f, results.github_base, dirty)
    codes = sorted({f.code for f in findings if f.code})
    rules = [r for r in (get_rule(c) for c in codes) if r is not None]
    if rules:
        lines += ["", "### Why these matter", ""]
        for rule in rules:
            guides = " · ".join(f"[{label}]({url})" for label, url in rule.guides)
            lines.append(f"- **{rule.code}** {rule.title}: {rule.why}" + (f" ({guides})" if guides else ""))
    lines += [
        "",
        "Re-run `wbcheck check` after fixing; items that no longer appear are done. "
        "`wbcheck issues` won't refile anything listed here.",
    ]
    return "\n".join(lines) + "\n"


def plan_issues(
    results: Results,
    group_by: str = "auto",
    min_severity: str = "warning",
    source: str = "all",
    already_filed: set[str] | None = None,
) -> tuple[list[IssueDraft], int]:
    """Issue drafts for `results`, skipping findings below `min_severity`,
    from other sources, or already filed. Returns the drafts and how many
    findings were skipped as already filed."""
    if group_by not in ("auto", "file", "rule"):
        raise ValueError(f"unknown group_by `{group_by}`, expected auto, file, or rule")
    threshold = SEVERITY_ORDER[min_severity]
    filed = already_filed or set()
    # Stale AI findings (file changed since the review) may no longer
    # describe the text, so they're never filed; re-review first.
    selected = [
        f
        for f in results.findings
        if SEVERITY_ORDER.get(f.severity, 9) <= threshold
        and (source == "all" or f.source == source)
        and not f.stale
    ]
    skipped = sum(1 for f in selected if f.id in filed)
    fresh = [f for f in selected if f.id not in filed]
    drafts = []
    for key, findings in _group(fresh, group_by).items():
        labels = [WBCHECK_LABEL] + ([AI_LABEL] if any(f.source == "ai" for f in findings) else [])
        drafts.append(IssueDraft(key, _title(key, findings), _body(key, findings, results), labels, findings))
    drafts.sort(key=lambda d: (min(SEVERITY_ORDER.get(f.severity, 9) for f in d.findings), d.key))
    return drafts, skipped


def draft_for_findings(results: Results, findings: list[Finding]) -> IssueDraft:
    """One issue covering exactly `findings` (e.g. a hand-picked selection
    in the TUI), regardless of the usual grouping."""
    if not findings:
        raise ValueError("no findings to draft an issue for")
    locations = sorted({f.location or "lesson" for f in findings})
    codes = ", ".join(sorted({f.code or f.category for f in findings}))
    if len(locations) == 1:
        title = f"{locations[0]}: {_counts_label(findings)} ({codes})"
    else:
        title = f"{_counts_label(findings)} across {len(locations)} files ({codes})"
    key = "selection:" + hashlib.sha1(",".join(sorted(f.id for f in findings)).encode()).hexdigest()[:12]
    labels = [WBCHECK_LABEL] + ([AI_LABEL] if any(f.source == "ai" for f in findings) else [])
    return IssueDraft(key, title, _body(key, findings, results), labels, list(findings))


# -- GitHub, via the gh CLI ------------------------------------------------------


class GhError(RuntimeError):
    """A gh CLI call failed."""


def _gh(args: list[str], input_text: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, input=input_text, timeout=60
        )
    except FileNotFoundError as exc:
        raise GhError("the GitHub CLI `gh` is not installed (https://cli.github.com)") from exc
    except subprocess.TimeoutExpired as exc:
        raise GhError(f"gh {' '.join(args[:2])} timed out") from exc
    if result.returncode != 0:
        raise GhError(result.stderr.strip() or f"gh {' '.join(args[:2])} failed")
    return result.stdout


ISSUE_SCAN_LIMIT = 10_000


def filed_ids(repo: str) -> set[str]:
    """Finding IDs already present in any `wbcheck`-labelled issue in `repo`,
    open or closed. Raises GhError rather than return a partial set if the
    repo has more wbcheck issues than we read, since a partial set would
    let already-filed findings be filed again."""
    out = _gh([
        "issue", "list", "--repo", repo, "--label", WBCHECK_LABEL, "--state", "all",
        "--limit", str(ISSUE_SCAN_LIMIT), "--json", "body",
    ])
    issues = json.loads(out or "[]")
    if len(issues) >= ISSUE_SCAN_LIMIT:
        raise GhError(
            f"{repo} has {ISSUE_SCAN_LIMIT}+ wbcheck issues; can't check them all for duplicates"
        )
    ids: set[str] = set()
    for issue in issues:
        ids.update(ID_MARKER_RE.findall(issue.get("body") or ""))
    return ids


def ensure_labels(repo: str, labels: set[str]) -> None:
    """Create the wbcheck labels if missing (no-op when they exist)."""
    existing = {row["name"] for row in json.loads(_gh(["label", "list", "--repo", repo, "--limit", "500",
                                                       "--json", "name"]) or "[]")}
    for label in sorted(labels - existing):
        _gh(["label", "create", label, "--repo", repo, "--color", LABEL_COLORS.get(label, "ededed"),
             "--description", "Filed by wbcheck" if label == WBCHECK_LABEL else "AI review suggestion, verify"])


def create_issue(repo: str, draft: IssueDraft) -> str:
    """File `draft` in `repo`; returns the new issue's URL."""
    args = ["issue", "create", "--repo", repo, "--title", draft.title, "--body-file", "-"]
    for label in draft.labels:
        args += ["--label", label]
    return _gh(args, input_text=draft.body).strip()
