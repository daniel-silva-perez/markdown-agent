# markdown-agent

Python CLI for keeping agent instruction files aligned with meaningful codebase changes.

`markdown-agent` watches repository diffs, decides whether the changes matter enough to update docs, and then refreshes relevant sections of `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` instead of forcing manual documentation cleanup after every refactor.

## Why It Exists

Multi-agent repositories drift quickly:

- commands change
- file layouts move
- architecture notes go stale
- one assistant file gets updated while others fall behind

This project makes documentation maintenance part of the development workflow.

## What It Does

- Detects the repo root automatically
- Reads Git diffs, including staged diffs for pre-commit use
- Runs a significance gate before rewriting documentation
- Updates only affected sections
- Keeps assistant-specific files aligned
- Supports local and hosted model providers

## Providers

Configured through `.markdown-agent.yml`:

- Ollama
- LM Studio
- Claude
- OpenAI

## CLI

```bash
markdown-agent init
markdown-agent run
markdown-agent run --dry-run
markdown-agent watch
markdown-agent install-hook
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

The package targets Python 3.11+ and is built with Hatchling.

## Recruiter Signals

- Practical AI-assisted developer tooling
- Clear diff-driven architecture
- Local and hosted model provider boundaries
- Testable Python CLI design
