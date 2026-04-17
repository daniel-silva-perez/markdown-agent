from __future__ import annotations

import asyncio
import stat
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from markdown_agent.config import load_config
from markdown_agent.pipeline import run_pipeline

app = typer.Typer(
    name="markdown-agent",
    help="AI agent that keeps AGENTS.md, CLAUDE.md, and GEMINI.md in sync with your codebase.",
    no_args_is_help=True,
)
console = Console()

_EXAMPLE_CONFIG = """\
# .markdown-agent.yml
provider: ollama          # ollama | lmstudio | claude | openai

agents_md: AGENTS.md
claude_md: CLAUDE.md
gemini_md: GEMINI.md

min_significant_lines: 3  # changes smaller than this are ignored

skip_paths:
  - "tests/"
  - "*.lock"
  - "__pycache__/"

ollama:
  base_url: http://localhost:11434
  gate_model: llama3.2:3b   # fast/small for significance gate
  update_model: llama3.2    # used for section rewrites

# lmstudio:
#   base_url: http://localhost:1234
#   gate_model: local-model
#   update_model: local-model

# claude:
#   api_key_env: ANTHROPIC_API_KEY
#   gate_model: claude-haiku-4-5-20251001
#   update_model: claude-sonnet-4-6

# openai:
#   api_key_env: OPENAI_API_KEY
#   gate_model: gpt-4o-mini
#   update_model: gpt-4o
"""

_STUB_AGENTS_MD = """\
# Project Documentation

## Overview

Describe your project here.

## Setup

```bash
# install dependencies
```

## Commands

| Command | Description |
|---------|-------------|
| `...`   | ...         |

## Architecture

Describe the project structure here.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| ...      | ...     | ...         |
"""

_GIT_HOOK = """\
#!/bin/sh
# markdown-agent pre-commit hook
markdown-agent run --staged
"""


def _find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists() or (p / ".markdown-agent.yml").exists():
            return p
    return start


@app.command()
def run(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Repository root (default: auto-detect)"),
    staged: bool = typer.Option(False, "--staged", "-s", help="Diff staged changes only (for pre-commit use)"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would change without writing files"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Override provider (ollama/lmstudio/claude/openai)"),
):
    """Analyse recent changes and update documentation files."""
    root = Path(repo) if repo else _find_repo_root(Path.cwd())
    cfg = load_config(root)
    if provider:
        cfg.provider = provider

    console.print(f"[dim]Repo:[/dim] {root}")
    console.print(f"[dim]Provider:[/dim] {cfg.provider}")

    with console.status("[bold cyan]Running significance gate…"):
        result = asyncio.run(run_pipeline(root, cfg, staged_only=staged, dry_run=dry_run))

    if result.skipped:
        console.print(Panel(
            f"[yellow]Skipped[/yellow] — {result.reason}",
            title="markdown-agent",
            border_style="yellow",
        ))
        return

    decision = result.decision
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold]Reason[/bold]", decision.reason if decision else "")
    table.add_row("[bold]Sections[/bold]", ", ".join(decision.affected_sections) if decision else "")
    table.add_row("[bold]Changes[/bold]", ", ".join(decision.change_types) if decision else "")
    table.add_row("[bold]Files written[/bold]", ", ".join(result.modified_files or []))

    if result.warnings:
        table.add_row("[bold yellow]Warnings[/bold yellow]", "\n".join(result.warnings))

    console.print(Panel(table, title="[green]Updated[/green]", border_style="green"))


@app.command()
def watch(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Repository root"),
    interval: int = typer.Option(0, "--interval", "-i", help="Poll interval in seconds (0 = use config)"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Override provider"),
):
    """Poll for changes and update documentation continuously."""
    root = Path(repo) if repo else _find_repo_root(Path.cwd())
    cfg = load_config(root)
    if provider:
        cfg.provider = provider
    poll = interval or cfg.watch_interval

    console.print(f"[cyan]Watching[/cyan] {root}  [dim](every {poll}s, Ctrl-C to stop)[/dim]")
    try:
        while True:
            result = asyncio.run(run_pipeline(root, cfg))
            if result.skipped:
                console.print(f"[dim]{_ts()} skip — {result.reason}[/dim]")
            else:
                files = ", ".join(result.modified_files or [])
                console.print(f"[green]{_ts()} updated — {result.reason} → {files}[/green]")
            time.sleep(poll)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


@app.command("install-hook")
def install_hook(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Repository root"),
):
    """Install a Git pre-commit hook that runs markdown-agent automatically."""
    root = Path(repo) if repo else _find_repo_root(Path.cwd())
    hooks_dir = root / ".git" / "hooks"
    if not hooks_dir.exists():
        console.print("[red]No .git/hooks directory found. Is this a Git repo?[/red]")
        raise typer.Exit(1)

    hook_path = hooks_dir / "pre-commit"
    if hook_path.exists():
        overwrite = typer.confirm(f"{hook_path} already exists. Overwrite?")
        if not overwrite:
            raise typer.Exit(0)

    hook_path.write_text(_GIT_HOOK)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    console.print(f"[green]Installed hook:[/green] {hook_path}")


@app.command()
def init(
    repo: Optional[Path] = typer.Option(None, "--repo", "-r", help="Repository root"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """Create .markdown-agent.yml and a stub AGENTS.md."""
    from markdown_agent.sync import sync_pointer_files

    root = Path(repo) if repo else Path.cwd()
    root.mkdir(exist_ok=True)
    cfg_path = root / ".markdown-agent.yml"
    agents_path = root / "AGENTS.md"
    claude_path = root / "CLAUDE.md"
    gemini_path = root / "GEMINI.md"

    for path, content in [(cfg_path, _EXAMPLE_CONFIG), (agents_path, _STUB_AGENTS_MD)]:
        if path.exists() and not force:
            console.print(f"[yellow]Skipped (exists):[/yellow] {path.name}")
        else:
            path.write_text(content)
            console.print(f"[green]Created:[/green] {path.name}")

    # Bootstrap pointer files
    synced = sync_pointer_files(agents_path, claude_path, gemini_path)
    for p in synced:
        console.print(f"[green]Created:[/green] {p.name}")

    console.print("\n[dim]Next: edit .markdown-agent.yml to choose your provider, then run:[/dim]")
    console.print("  [bold]markdown-agent run[/bold]")


def _ts() -> str:
    import datetime
    return datetime.datetime.now().strftime("%H:%M:%S")
