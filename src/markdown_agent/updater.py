from __future__ import annotations

from markdown_agent.gate import GateDecision
from markdown_agent.git import DiffSummary
from markdown_agent.markdown import ParsedDoc, patch_sections, add_section
from markdown_agent.providers.base import LLMProvider


_SYSTEM = """\
You are a Documentation Writer. Update ONLY the requested sections of AGENTS.md.

RULES:
- Output a JSON object where keys are section titles and values are the updated
  markdown body for that section. No prose outside the JSON.
- Preserve all existing information unless it is directly contradicted by the diff.
- Be concise. Do not pad with boilerplate. Do not document implementation details.
- For "NEW: <Title>" sections, create a focused, minimal entry.
- Body text is plain markdown (lists, code blocks, short paragraphs).
- Never include the section header in the body value — just the content below it.
- Keep each section body under 300 words unless it's naturally longer (e.g. a
  large list of commands).

OUTPUT SCHEMA:
{
  "Section Title": "updated body markdown...",
  "Another Section": "updated body markdown..."
}
"""


def _build_prompt(
    diff: DiffSummary,
    decision: GateDecision,
    doc: ParsedDoc,
) -> str:
    # Collect current content of affected sections only
    section_context = ""
    for title in decision.affected_sections:
        clean_title = title.removeprefix("NEW: ")
        sec = doc.get(clean_title)
        if sec:
            section_context += f"\n### Current: {sec.header}\n{sec.body.strip()}\n"
        else:
            section_context += f"\n### Current: {title}\n(does not exist yet)\n"

    return f"""\
REASON FOR UPDATE: {decision.reason}
CHANGE TYPES: {', '.join(decision.change_types)}
SECTIONS TO UPDATE: {', '.join(decision.affected_sections)}

CURRENT SECTION CONTENT:
{section_context}

DIFF THAT TRIGGERED THIS UPDATE:
```
{diff.raw_diff}
```

Rewrite only the listed sections. Output JSON with section titles as keys."""


async def run_updater(
    provider: LLMProvider,
    diff: DiffSummary,
    decision: GateDecision,
    doc: ParsedDoc,
) -> ParsedDoc:
    prompt = _build_prompt(diff, decision, doc)
    raw = await provider.complete(
        system=_SYSTEM,
        prompt=prompt,
        temperature=0.2,
        max_tokens=2048,
        response_format="json",
    )

    import json, re
    clean = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        updates: dict[str, str] = json.loads(clean)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", clean, re.DOTALL)
        if not m:
            raise ValueError(f"Updater returned non-JSON: {raw[:200]}")
        updates = json.loads(m.group())

    # Split into updates for existing vs new sections
    existing_updates: dict[str, str] = {}
    new_sections: dict[str, str] = {}

    for raw_title, body in updates.items():
        clean_title = raw_title.removeprefix("NEW: ")
        if doc.get(clean_title):
            existing_updates[clean_title] = body
        else:
            new_sections[clean_title] = body

    doc = patch_sections(doc, existing_updates)
    for title, body in new_sections.items():
        doc = add_section(doc, title, body)

    return doc
