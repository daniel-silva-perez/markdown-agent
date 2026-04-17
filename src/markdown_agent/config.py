from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    gate_model: str = "llama3.2:3b"
    update_model: str = "llama3.2"


@dataclass
class LMStudioConfig:
    base_url: str = "http://localhost:1234"
    gate_model: str = "local-model"
    update_model: str = "local-model"


@dataclass
class ClaudeConfig:
    api_key_env: str = "ANTHROPIC_API_KEY"
    gate_model: str = "claude-haiku-4-5-20251001"
    update_model: str = "claude-sonnet-4-6"


@dataclass
class OpenAIConfig:
    api_key_env: str = "OPENAI_API_KEY"
    gate_model: str = "gpt-4o-mini"
    update_model: str = "gpt-4o"
    base_url: str | None = None


@dataclass
class AgentConfig:
    provider: str = "ollama"
    # Files to manage
    agents_md: str = "AGENTS.md"
    claude_md: str = "CLAUDE.md"
    gemini_md: str = "GEMINI.md"
    # Gate thresholds
    min_significant_lines: int = 3
    skip_paths: list[str] = field(default_factory=lambda: [
        "tests/", ".git/", "*.lock", "*.sum", "__pycache__/",
    ])
    watch_interval: int = 30  # seconds between polls in watch mode
    # Provider sub-configs
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    lmstudio: LMStudioConfig = field(default_factory=LMStudioConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)


def _merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(project_root: Path) -> AgentConfig:
    config_path = project_root / ".markdown-agent.yml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open() as f:
            raw = yaml.safe_load(f) or {}

    cfg = AgentConfig()
    cfg.provider = os.environ.get("MARKDOWN_AGENT_PROVIDER", raw.get("provider", cfg.provider))

    for simple_key in ("agents_md", "claude_md", "gemini_md", "min_significant_lines", "watch_interval"):
        if simple_key in raw:
            setattr(cfg, simple_key, raw[simple_key])

    if "skip_paths" in raw:
        cfg.skip_paths = raw["skip_paths"]

    if "ollama" in raw:
        d = raw["ollama"]
        cfg.ollama = OllamaConfig(
            base_url=d.get("base_url", cfg.ollama.base_url),
            gate_model=d.get("gate_model", cfg.ollama.gate_model),
            update_model=d.get("update_model", cfg.ollama.update_model),
        )
    if "lmstudio" in raw:
        d = raw["lmstudio"]
        cfg.lmstudio = LMStudioConfig(
            base_url=d.get("base_url", cfg.lmstudio.base_url),
            gate_model=d.get("gate_model", cfg.lmstudio.gate_model),
            update_model=d.get("update_model", cfg.lmstudio.update_model),
        )
    if "claude" in raw:
        d = raw["claude"]
        cfg.claude = ClaudeConfig(
            api_key_env=d.get("api_key_env", cfg.claude.api_key_env),
            gate_model=d.get("gate_model", cfg.claude.gate_model),
            update_model=d.get("update_model", cfg.claude.update_model),
        )
    if "openai" in raw:
        d = raw["openai"]
        cfg.openai = OpenAIConfig(
            api_key_env=d.get("api_key_env", cfg.openai.api_key_env),
            gate_model=d.get("gate_model", cfg.openai.gate_model),
            update_model=d.get("update_model", cfg.openai.update_model),
            base_url=d.get("base_url"),
        )
    return cfg


def build_provider(cfg: AgentConfig, role: str = "update"):
    """Instantiate the configured provider. role='gate' or 'update'."""
    from markdown_agent.providers import (
        OllamaProvider, LMStudioProvider, ClaudeProvider, OpenAIProvider
    )

    name = cfg.provider
    if name == "ollama":
        model = cfg.ollama.gate_model if role == "gate" else cfg.ollama.update_model
        return OllamaProvider(base_url=cfg.ollama.base_url, model=model)
    if name == "lmstudio":
        model = cfg.lmstudio.gate_model if role == "gate" else cfg.lmstudio.update_model
        return LMStudioProvider(base_url=cfg.lmstudio.base_url, model=model)
    if name == "claude":
        import os
        api_key = os.environ.get(cfg.claude.api_key_env, "")
        return ClaudeProvider(
            api_key=api_key,
            gate_model=cfg.claude.gate_model,
            update_model=cfg.claude.update_model,
            _model_override=cfg.claude.gate_model if role == "gate" else cfg.claude.update_model,
        )
    if name == "openai":
        import os
        api_key = os.environ.get(cfg.openai.api_key_env, "")
        return OpenAIProvider(
            api_key=api_key,
            gate_model=cfg.openai.gate_model,
            update_model=cfg.openai.update_model,
            base_url=cfg.openai.base_url,
        )
    raise ValueError(f"Unknown provider: {name!r}. Choose: ollama, lmstudio, claude, openai")
