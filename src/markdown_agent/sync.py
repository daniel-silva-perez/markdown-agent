"""Manages CLAUDE.md and GEMINI.md alongside AGENTS.md."""
from __future__ import annotations

from pathlib import Path

_POINTER_LINE = "@AGENTS.md"
_POINTER_COMMENT = "# Tool-specific overrides go below this line\n"


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def sync_pointer_files(
    agents_path: Path,
    claude_path: Path,
    gemini_path: Path,
) -> list[Path]:
    """Ensure CLAUDE.md and GEMINI.md reference AGENTS.md.

    Strategy:
    - If file is empty or missing → write the pointer only.
    - If file already contains the pointer → leave overrides intact.
    - If file has content but no pointer → prepend the pointer line so the
      tool still reads AGENTS.md first, then sees the existing custom content.

    Returns list of files that were actually modified.
    """
    modified: list[Path] = []

    for path in (claude_path, gemini_path):
        current = _read(path)

        if not current.strip():
            # Empty or missing — write clean pointer
            path.write_text(f"{_POINTER_LINE}\n{_POINTER_COMMENT}")
            modified.append(path)
        elif _POINTER_LINE not in current:
            # Has content but no pointer — prepend
            path.write_text(f"{_POINTER_LINE}\n{_POINTER_COMMENT}\n{current}")
            modified.append(path)
        # else: pointer already present, leave as-is

    return modified
