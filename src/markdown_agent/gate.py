from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from markdown_agent.git import DiffSummary
from markdown_agent.providers.base import LLMProvider, ProviderError


_SYSTEM = """\
You are a Documentation Gate. Your only job is to decide whether a Git diff
is significant enough to update AGENTS.md, and if so, which sections need changes.

RULES:
- Return JSON only. No prose, no markdown fences.
- Mark significant=false for: typos/whitespace/comment-only changes, test-only
  changes with no new commands, lock file updates, changelog updates.
- Mark significant=true for: new dependencies, new CLI commands, new environment
  variables, structural changes (new modules/packages), new build/test targets,
  changed public APIs, new configuration options.
- affected_sections must be section TITLES from the existing AGENTS.md (provided
  below). If no existing section fits, you may suggest a new title — prefix it
  with "NEW: ".
- reason must be one short sentence.

OUTPUT SCHEMA:
{
  "significant": true | false,
  "reason": "...",
  "affected_sections": ["Title1", "Title2"],
  "change_types": ["dependencies" | "commands" | "environment" | "structure" | "api"]
}
"""


@dataclass
class GateDecision:
    significant: bool
    reason: str
    affected_sections: list[str] = field(default_factory=list)
    change_types: list[str] = field(default_factory=list)


def _fast_skip(diff: DiffSummary, min_lines: int) -> GateDecision | None:
    """Pre-LLM heuristic skips — no token spend needed."""
    if diff.is_whitespace_only:
        return GateDecision(False, "Whitespace-only change")
    if diff.is_comment_only:
        return GateDecision(False, "Comment/docstring-only change")
    if diff.total_meaningful_lines < min_lines:
        return GateDecision(False, f"Too few meaningful lines changed ({diff.total_meaningful_lines})")
    # All changed files are pure noise
    if not diff.significant_files:
        return GateDecision(False, "Only lock files / cache files changed")
    return None


def _build_prompt(diff: DiffSummary, existing_sections: list[str]) -> str:
    files_summary = "\n".join(
        f"  {'[NEW] ' if f.is_new else '[DEL] ' if f.is_deleted else ''}{f.path} (+{f.insertions}/-{f.deletions})"
        for f in diff.significant_files[:30]
    )
    sections_list = "\n".join(f"  - {s}" for s in existing_sections) if existing_sections else "  (none yet)"

    return f"""\
EXISTING AGENTS.MD SECTIONS:
{sections_list}

CHANGED FILES:
{files_summary}

DETECTED CHANGE TYPES (heuristic): {', '.join(diff.change_types) or 'unknown'}

DIFF (first 300 lines):
```
{diff.raw_diff}
```

Decide: is this diff significant enough to update AGENTS.md?"""


def _parse_response(raw: str) -> GateDecision:
    # Strip accidental markdown fences
    clean = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        # Attempt to extract JSON object from surrounding text
        m = re.search(r"\{.*\}", clean, re.DOTALL)
        if not m:
            raise ProviderError(f"Gate returned non-JSON: {raw[:200]}")
        data = json.loads(m.group())

    return GateDecision(
        significant=bool(data.get("significant", False)),
        reason=str(data.get("reason", "")),
        affected_sections=list(data.get("affected_sections", [])),
        change_types=list(data.get("change_types", [])),
    )


async def run_gate(
    provider: LLMProvider,
    diff: DiffSummary,
    existing_sections: list[str],
    min_lines: int = 3,
) -> GateDecision:
    fast = _fast_skip(diff, min_lines)
    if fast:
        return fast

    prompt = _build_prompt(diff, existing_sections)
    raw = await provider.complete(
        system=_SYSTEM,
        prompt=prompt,
        temperature=0.1,
        max_tokens=512,
        response_format="json",
    )
    return _parse_response(raw)
