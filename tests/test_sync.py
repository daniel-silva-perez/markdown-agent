import pytest
from pathlib import Path
from markdown_agent.sync import sync_pointer_files, _POINTER_LINE, _POINTER_COMMENT


def test_sync_creates_missing_pointer_files(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.touch()
    claude = tmp_path / "CLAUDE.md"
    gemini = tmp_path / "GEMINI.md"

    modified = sync_pointer_files(agents, claude, gemini)
    assert claude in modified
    assert gemini in modified
    assert _POINTER_LINE in claude.read_text()
    assert _POINTER_LINE in gemini.read_text()


def test_sync_preserves_existing_override(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.touch()
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(f"{_POINTER_LINE}\n{_POINTER_COMMENT}\n# custom override\n")

    modified = sync_pointer_files(agents, claude, Path(tmp_path / "GEMINI.md"))
    assert claude not in modified
    assert "# custom override" in claude.read_text()


def test_sync_prepends_pointer_if_missing(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.touch()
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("# Only custom content\n")

    modified = sync_pointer_files(agents, claude, Path(tmp_path / "GEMINI.md"))
    assert claude in modified
    content = claude.read_text()
    assert content.startswith(_POINTER_LINE)
    assert "# Only custom content" in content
