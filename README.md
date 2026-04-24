# markdown-agent

[![GitHub Repo](https://img.shields.io/badge/GitHub-Repo-181717?logo=github&logoColor=white)](https://github.com/daniel-silva-perez/markdown-agent)
[![GitLab Repo](https://img.shields.io/badge/GitLab-Repo-FC6D26?logo=gitlab&logoColor=white)](https://gitlab.com/danielsilvaperez/markdown-agent)
[![Python CLI](https://img.shields.io/badge/Python-CLI-3776AB?logo=python&logoColor=white)](https://www.python.org/)

AI-assisted documentation maintenance for codebases that use `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`.

`markdown-agent` watches what changed in a repo, decides whether the diff is meaningful enough to matter, and then updates the relevant sections of your instruction files instead of forcing you to rewrite them by hand after every refactor.

## Why It Exists

Multi-agent and multi-assistant repos drift fast:

- commands change
- file layout moves
- architectural notes go stale
- one assistant file gets updated while the others quietly rot

This project keeps those markdown surfaces synchronized from the repo itself.

## What It Does

- detects the repo root automatically
- reads Git diffs, including staged diffs for pre-commit use
- runs a significance gate before doing any rewrite work
- updates only the sections that actually need attention
- keeps `CLAUDE.md` and `GEMINI.md` aligned with `AGENTS.md`
- supports local and hosted model providers

## Supported Providers

Configured through `.markdown-agent.yml`:

- Ollama
- LM Studio
- Claude
- OpenAI

## CLI Commands

Initialize config and stub docs:

```bash
markdown-agent init
```

Update docs from the current repo diff:

```bash
markdown-agent run
```

Dry run without writing files:

```bash
markdown-agent run --dry-run
```

Watch the repo continuously:

```bash
markdown-agent watch
```

Install a Git pre-commit hook:

```bash
markdown-agent install-hook
```

## Installation

```bash
pip install -e .
```

With development dependencies:

```bash
pip install -e ".[dev]"
```

## How It Works

The pipeline is intentionally small and explicit:

1. collect a diff from Git
2. fast-skip tiny or non-meaningful changes
3. ask a model which markdown sections are affected
4. rewrite only those sections
5. sync pointer files so the assistant-specific docs stay aligned

Core files:

- `src/markdown_agent/cli.py` — Typer command surface
- `src/markdown_agent/git.py` — diff collection and significance heuristics
- `src/markdown_agent/gate.py` — decide whether the change warrants documentation updates
- `src/markdown_agent/updater.py` — section-level markdown rewriting
- `src/markdown_agent/sync.py` — pointer-file synchronization
- `src/markdown_agent/providers/` — model-provider adapters

## Development

Run tests:

```bash
pytest
```

The package targets Python 3.11+ and is built with Hatchling.
