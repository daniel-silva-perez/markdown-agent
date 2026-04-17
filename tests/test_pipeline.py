import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from markdown_agent.pipeline import run_pipeline
from markdown_agent.config import AgentConfig


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def cfg(repo_root):
    cfg = AgentConfig()
    cfg.provider = "ollama"
    cfg.min_significant_lines = 0
    return cfg


@pytest.mark.asyncio
async def test_pipeline_no_significant_change_skips(tmp_path, cfg, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("## Setup\nNo changes.")

    with patch("markdown_agent.git.get_diff") as mock_diff:
        from markdown_agent.git import DiffSummary
        mock_diff.return_value = DiffSummary(
            file_diffs=[],
            raw_diff="",
            total_insertions=0,
            total_deletions=0,
            change_types=set(),
            is_comment_only=True,
            is_whitespace_only=False,
        )
        result = await run_pipeline(tmp_path, cfg)
        assert result.skipped is True
        assert result.modified_files is None


@pytest.mark.asyncio
async def test_pipeline_dry_run_returns_decision(tmp_path, cfg, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("## Commands\nOld commands.")

    from markdown_agent.git import DiffSummary, FileDiff
    from markdown_agent.gate import GateDecision

    mock_diff = DiffSummary(
        file_diffs=[FileDiff("Makefile", 10, 1)],
        raw_diff="+ new target",
        total_insertions=10,
        total_deletions=1,
        change_types={"commands"},
        is_comment_only=False,
        is_whitespace_only=False,
    )
    mock_decision = GateDecision(
        significant=True,
        reason="new cmd",
        affected_sections=["Commands"],
        change_types=["commands"],
    )

    with patch("markdown_agent.pipeline.get_diff", return_value=mock_diff):
        with patch("markdown_agent.pipeline.run_gate", return_value=mock_decision) as mock_gate_run:
            result = await run_pipeline(tmp_path, cfg, dry_run=True)

    assert result.skipped is False
    assert result.decision is not None
    assert result.decision.affected_sections == ["Commands"]
