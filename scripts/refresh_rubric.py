"""Regenerate checker/rubric/*.md from the live Carpentries guidance pages.

The AI review pins these excerpts into every prompt instead of fetching and
embedding the pages at run time (issue #25), so reviews are reproducible and
need no network or Ollama for the guidance itself. Refreshing is a deliberate
step: run this, read the diff, commit it.

    pixi run refresh-rubric

Sections are chosen by anchor id; if an upstream page renames one, this
fails loudly rather than silently dropping guidance.
"""

from __future__ import annotations

import datetime
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, Tag

RUBRIC_DIR = Path(__file__).resolve().parent.parent / "checker" / "rubric"

SOURCES = {
    "cldt.md": (
        "Collaborative Lesson Development Training (CLDT)",
        "https://carpentries.github.io/lesson-development-training/aio.html",
        [
            "target-audience",
            "defining-prerequisite-knowledge",
            "learning-objectives",
            "smart-objectives",
            "planning-your-episodes",
            "assessments",
            "writing-explanatory-text",
            "less-is-more",
            "other-important-considerations-for-lesson-content",
        ],
    ),
    "workbench.md": (
        "Carpentries Workbench documentation",
        "https://carpentries.github.io/sandpaper-docs/episodes.html",
        ["required-elements", "exerciseschallenges"],
    ),
}

# Workbench callouts that are exercises *for CLDT trainees* (or instructor
# asides), not guidance about lessons. Left in, the reviewing model can
# mistake them for instructions or rubric items.
DROP_CLASSES = {"challenge", "discussion", "solution", "instructor-note", "accordion", "spoiler", "testimonial"}


def _drop_noise(section: Tag) -> None:
    for div in section.find_all(["div", "details"]):
        if div.decomposed:
            continue
        classes = set(div.get("class") or [])
        if classes & DROP_CLASSES:
            div.decompose()


def _to_markdown(section: Tag) -> str:
    """Headings, paragraphs, and list items as plain markdown; everything else skipped."""
    lines: list[str] = []
    for el in section.find_all(["h2", "h3", "h4", "p", "li"]):
        # skip paragraphs nested in list items (the li already carries their text)
        if el.name == "p" and el.find_parent("li") is not None:
            continue
        if el.name == "li":
            # only this item's own text; nested list items get their own lines
            own = [c for c in el.children if not (isinstance(c, Tag) and c.name in ("ul", "ol"))]
            raw = " ".join(c.get_text(" ", strip=True) if isinstance(c, Tag) else str(c) for c in own)
        else:
            raw = el.get_text(" ", strip=True)
        text = " ".join(raw.split())
        if not text:
            continue
        if el.name in ("h2", "h3", "h4"):
            level = {"h2": "##", "h3": "###", "h4": "####"}[el.name]
            lines += ["", f"{level} {text}", ""]
        elif el.name == "li":
            depth = len(el.find_parents(["ul", "ol"])) - 1
            lines.append(f"{'  ' * depth}- {text}")
        else:
            lines += [text, ""]
    return "\n".join(lines).strip() + "\n"


def build(filename: str, title: str, url: str, ids: list[str]) -> str:
    """Fetch `url` and render the named sections as one markdown document."""
    soup = BeautifulSoup(urllib.request.urlopen(url, timeout=30).read(), "html.parser")
    parts = [
        f"# {title} (excerpts)",
        "",
        f"Source: {url}",
        f"Retrieved: {datetime.date.today().isoformat()} by scripts/refresh_rubric.py. "
        "Edit by re-running the script, not by hand.",
        "",
    ]
    for section_id in ids:
        anchor = soup.find(id=section_id)
        if anchor is None:
            raise SystemExit(f"{filename}: section #{section_id} not found at {url}, upstream page changed?")
        section = anchor if anchor.name == "section" else anchor.find_parent("section")
        if section is None:
            raise SystemExit(f"{filename}: #{section_id} is not inside a <section> at {url}")
        _drop_noise(section)
        parts.append(_to_markdown(section))
    return "\n".join(parts)


LAB_CHECKLIST_URL = "https://raw.githubusercontent.com/carpentries-lab/reviews/main/docs/reviewer_guide.md"
LAB_CHECKLIST_PAGE = "https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md"


def build_lab_checklist() -> str:
    """The Carpentries Lab reviewer checklist, verbatim from its markdown
    source: everything under `## Reviewer Checklist` up to the next `## `."""
    source = urllib.request.urlopen(LAB_CHECKLIST_URL, timeout=30).read().decode()
    lines, keep = [], False
    for line in source.splitlines():
        if line.startswith("## "):
            keep = line.strip() == "## Reviewer Checklist"
            continue
        if keep:
            lines.append(line)
    if not lines:
        raise SystemExit(f"lab-checklist.md: no '## Reviewer Checklist' section at {LAB_CHECKLIST_URL}")
    header = [
        "# The Carpentries Lab reviewer checklist",
        "",
        f"Source: {LAB_CHECKLIST_PAGE}",
        f"Retrieved: {datetime.date.today().isoformat()} by scripts/refresh_rubric.py. "
        "Edit by re-running the script, not by hand.",
    ]
    return "\n".join(header + lines).strip() + "\n"


def main() -> None:
    """Write every rubric file and report its size."""
    RUBRIC_DIR.mkdir(exist_ok=True)
    text = build_lab_checklist()
    (RUBRIC_DIR / "lab-checklist.md").write_text(text)
    print(f"wrote {RUBRIC_DIR / 'lab-checklist.md'} ({len(text.split())} words)")
    for filename, (title, url, ids) in SOURCES.items():
        text = build(filename, title, url, ids)
        (RUBRIC_DIR / filename).write_text(text)
        print(f"wrote {RUBRIC_DIR / filename} ({len(text.split())} words)")


if __name__ == "__main__":
    main()
