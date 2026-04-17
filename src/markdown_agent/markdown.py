from __future__ import annotations

import re
from dataclasses import dataclass, field


_SECTION_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


@dataclass
class Section:
    header: str        # e.g. "## Commands"
    level: int         # heading depth
    title: str         # e.g. "Commands"
    body: str          # content below the header (no trailing newline)
    index: int         # original order


@dataclass
class ParsedDoc:
    preamble: str                          # content before first heading
    sections: list[Section] = field(default_factory=list)

    def get(self, title: str) -> Section | None:
        t = title.lstrip("#").strip().lower()
        return next((s for s in self.sections if s.title.lower() == t), None)

    def section_titles(self) -> list[str]:
        return [s.title for s in self.sections]

    def to_string(self) -> str:
        parts = []
        if self.preamble.strip():
            parts.append(self.preamble.rstrip())
        for sec in sorted(self.sections, key=lambda s: s.index):
            parts.append(f"\n{sec.header}\n")
            if sec.body.strip():
                parts.append(sec.body.strip())
        return "\n".join(parts).rstrip() + "\n"


def parse(text: str) -> ParsedDoc:
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return ParsedDoc(preamble=text, sections=[])

    preamble = text[: matches[0].start()]
    sections: list[Section] = []

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        header = m.group(0)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        sections.append(Section(header=header, level=level, title=title, body=body, index=i))

    return ParsedDoc(preamble=preamble, sections=sections)


def patch_sections(doc: ParsedDoc, updates: dict[str, str]) -> ParsedDoc:
    """Replace section bodies in-place. updates keys are section titles (case-insensitive)."""
    title_map = {k.lower(): v for k, v in updates.items()}
    for sec in doc.sections:
        key = sec.title.lower()
        if key in title_map:
            sec.body = "\n" + title_map[key].strip() + "\n"
    return doc


def add_section(doc: ParsedDoc, title: str, body: str, level: int = 2) -> ParsedDoc:
    header = "#" * level + " " + title
    sec = Section(
        header=header,
        level=level,
        title=title,
        body="\n" + body.strip() + "\n",
        index=len(doc.sections),
    )
    doc.sections.append(sec)
    return doc


def validate_markdown(text: str) -> list[str]:
    """Return a list of warning strings. Empty = valid."""
    warnings = []
    lines = text.splitlines()

    # Check for unclosed code fences
    fence_count = sum(1 for l in lines if l.strip().startswith("```"))
    if fence_count % 2 != 0:
        warnings.append("Unclosed code fence (odd number of ``` markers)")

    # Check for broken links
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r"\[([^\]]+)\]\(([^)]*)\)", line):
            href = m.group(2)
            if href == "" or href.isspace():
                warnings.append(f"Line {i}: Empty link href in [{m.group(1)}]()")

    # Check consecutive blank lines (> 2 is sloppy)
    blanks = 0
    for i, line in enumerate(lines, 1):
        if not line.strip():
            blanks += 1
            if blanks > 2:
                warnings.append(f"Line {i}: More than 2 consecutive blank lines")
                blanks = 0
        else:
            blanks = 0

    return warnings
