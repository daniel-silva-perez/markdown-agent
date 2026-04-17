import pytest
from markdown_agent.markdown import parse, patch_sections, add_section, validate_markdown


SAMPLE = """\
# Project

Some preamble text.

## Setup

Install deps:
```bash
pip install -e .
```

## Commands

| Command | Description |
|---------|-------------|
| `test`  | Run tests  |

## Architecture

Top-level only.

### Deep Section

Deep content here.
"""


def test_parse_splits_by_h2_and_h3():
    doc = parse(SAMPLE)
    # Level-1 heading becomes a section, so preamble may be empty
    titles = [s.title for s in doc.sections]
    assert "Setup" in titles
    assert "Commands" in titles
    assert "Architecture" in titles
    assert "Deep Section" in titles


def test_parse_empty_returns_preamble():
    doc = parse("No headings here.")
    assert doc.preamble == "No headings here."
    assert doc.sections == []


def test_parse_no_content_after_header():
    doc = parse("## Only")
    assert doc.sections[0].body.strip() == ""


def test_get_by_title_case_insensitive():
    doc = parse(SAMPLE)
    assert doc.get("setup") is not None
    assert doc.get("SETUP") is not None
    assert doc.get("nonexistent") is None


def test_patch_sections_updates_body():
    doc = parse(SAMPLE)
    doc = patch_sections(doc, {"Setup": "New setup body.", "Commands": "New commands."})
    assert doc.get("Setup").body.strip() == "New setup body."
    assert doc.get("Commands").body.strip() == "New commands."
    # Unaffected section preserved
    arch = doc.get("Architecture").body
    assert "Top-level only" in arch


def test_patch_unknown_section_ignored():
    doc = parse(SAMPLE)
    doc = patch_sections(doc, {"Nonexistent": "Should be ignored."})
    assert all(s.title != "Nonexistent" for s in doc.sections)


def test_add_section():
    doc = parse(SAMPLE)
    doc = add_section(doc, "New Section", "Body of new section.", level=2)
    assert doc.get("New Section") is not None
    assert doc.get("New Section").body.strip() == "Body of new section."


def test_to_string_roundtrips():
    doc = parse(SAMPLE)
    rebuilt = parse(doc.to_string())
    assert [s.title for s in doc.sections] == [s.title for s in rebuilt.sections]


def test_validate_markdown_clean():
    warnings = validate_markdown(SAMPLE)
    assert warnings == []


def test_validate_markdown_unclosed_fence():
    warnings = validate_markdown("## Setup\n```bash\necho hi\n")
    assert any("Unclosed code fence" in w for w in warnings)


def test_validate_markdown_empty_href():
    warnings = validate_markdown("## Setup\n[link]()")
    assert any("Empty link href" in w for w in warnings)
