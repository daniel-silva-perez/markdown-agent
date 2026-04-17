import pytest
from unittest.mock import AsyncMock
from markdown_agent.gate import GateDecision, _fast_skip, _parse_response, run_gate
from markdown_agent.git import DiffSummary, FileDiff
from markdown_agent.providers.base import ProviderError


def make_diff(
    files=None,
    comment_only=False,
    whitespace_only=False,
    min_lines=3,
):
    if files is None:
        files = [FileDiff("src/main.py", 10, 2)]
    return DiffSummary(
        file_diffs=files,
        raw_diff="+ added line\n- removed line",
        total_insertions=sum(f.insertions for f in files),
        total_deletions=sum(f.deletions for f in files),
        change_types=set(),
        is_comment_only=comment_only,
        is_whitespace_only=whitespace_only,
    )


def test_fast_skip_whitespace():
    d = make_diff(whitespace_only=True)
    result = _fast_skip(d, min_lines=3)
    assert result is not None
    assert result.significant is False
    assert "Whitespace" in result.reason


def test_fast_skip_comment_only():
    d = make_diff(comment_only=True)
    result = _fast_skip(d, min_lines=3)
    assert result is not None
    assert result.significant is False
    assert "Comment" in result.reason


def test_fast_skip_too_few_lines():
    d = make_diff(files=[FileDiff("src/main.py", 1, 0)])
    result = _fast_skip(d, min_lines=3)
    assert result is not None
    assert "Too few" in result.reason


def test_fast_skip_no_significant_files():
    d = make_diff(files=[FileDiff("__pycache__/foo.pyc", 50, 10)])
    result = _fast_skip(d, min_lines=3)
    assert result is not None
    assert result.significant is False


def test_fast_skip_none_passes_through():
    d = make_diff(files=[FileDiff("src/main.py", 10, 2)])
    assert _fast_skip(d, min_lines=3) is None


def test_parse_response_valid_json():
    raw = '{"significant": true, "reason": "New deps", "affected_sections": ["Setup"], "change_types": ["dependencies"]}'
    result = _parse_response(raw)
    assert result.significant is True
    assert result.reason == "New deps"
    assert result.affected_sections == ["Setup"]


def test_parse_response_strips_fences():
    raw = '```json\n{"significant": false, "reason": "typo", "affected_sections": [], "change_types": []}\n```'
    result = _parse_response(raw)
    assert result.significant is False


def test_parse_response_invalid_raises():
    with pytest.raises(ProviderError):
        _parse_response("not json at all")


@pytest.mark.asyncio
async def test_run_gate_uses_fast_skip():
    provider = AsyncMock()
    diff = make_diff(whitespace_only=True)
    result = await run_gate(provider, diff, [], min_lines=3)
    assert result.significant is False
    provider.complete.assert_not_called()


@pytest.mark.asyncio
async def test_run_gate_calls_provider():
    provider = AsyncMock()
    provider.complete.return_value = '{"significant": true, "reason": "new cmd", "affected_sections": ["Commands"], "change_types": ["commands"]}'
    diff = make_diff(files=[FileDiff("Makefile", 5, 1)])
    result = await run_gate(provider, diff, ["Commands"], min_lines=3)
    assert result.significant is True
    assert result.affected_sections == ["Commands"]
    provider.complete.assert_called_once()
    call_kwargs = provider.complete.call_args.kwargs
    assert call_kwargs["response_format"] == "json"
