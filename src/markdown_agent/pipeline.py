"""Two-stage pipeline: Gate → Updater → Sync."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from markdown_agent.config import AgentConfig, build_provider
from markdown_agent.gate import GateDecision, run_gate
from markdown_agent.git import DiffSummary, get_diff
from markdown_agent.markdown import ParsedDoc, parse, validate_markdown
from markdown_agent.sync import sync_pointer_files
from markdown_agent.updater import run_updater


@dataclass
class RunResult:
    skipped: bool
    reason: str
    decision: GateDecision | None = None
    warnings: list[str] | None = None
    modified_files: list[str] | None = None


async def run_pipeline(
    repo_root: Path,
    cfg: AgentConfig,
    staged_only: bool = False,
    dry_run: bool = False,
) -> RunResult:
    agents_path = repo_root / cfg.agents_md
    claude_path = repo_root / cfg.claude_md
    gemini_path = repo_root / cfg.gemini_md

    # 1. Get diff
    diff: DiffSummary = get_diff(repo_root, staged_only=staged_only)

    # 2. Parse existing AGENTS.md (or start from scratch)
    current_text = agents_path.read_text() if agents_path.exists() else ""
    doc: ParsedDoc = parse(current_text)

    # 3. Stage 1 — significance gate
    gate_provider = build_provider(cfg, role="gate")
    decision = await run_gate(
        gate_provider,
        diff,
        doc.section_titles(),
        min_lines=cfg.min_significant_lines,
    )

    if not decision.significant:
        return RunResult(skipped=True, reason=decision.reason, decision=decision)

    if dry_run:
        return RunResult(
            skipped=False,
            reason=decision.reason,
            decision=decision,
            modified_files=["(dry-run — no files written)"],
        )

    # 4. Stage 2 — targeted section update
    update_provider = build_provider(cfg, role="update")
    updated_doc = await run_updater(update_provider, diff, decision, doc)

    # 5. Write AGENTS.md
    new_text = updated_doc.to_string()
    warnings = validate_markdown(new_text)
    agents_path.write_text(new_text)
    modified: list[str] = [cfg.agents_md]

    # 6. Sync pointer files
    synced = sync_pointer_files(agents_path, claude_path, gemini_path)
    modified.extend(p.name for p in synced)

    return RunResult(
        skipped=False,
        reason=decision.reason,
        decision=decision,
        warnings=warnings,
        modified_files=modified,
    )
