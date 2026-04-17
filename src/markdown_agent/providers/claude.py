import os
import json
from markdown_agent.providers.base import ProviderError

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


class ClaudeProvider:
    name = "claude"
    supports_json_mode = False  # We wrap with instructions instead

    def __init__(
        self,
        api_key: str | None = None,
        gate_model: str = "claude-haiku-4-5-20251001",
        update_model: str = "claude-sonnet-4-6",
        _model_override: str | None = None,
    ):
        if not _ANTHROPIC_AVAILABLE:
            raise ProviderError("anthropic package not installed. Run: pip install anthropic")
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ProviderError("ANTHROPIC_API_KEY not set")
        self.gate_model = gate_model
        self.update_model = update_model
        self._model_override = _model_override

    def _resolve_model(self, response_format: str | None) -> str:
        if self._model_override:
            return self._model_override
        return self.gate_model if response_format == "json" else self.update_model

    async def complete(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> str:
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        full_system = system
        if response_format == "json":
            full_system += "\n\nRespond with valid JSON only. No explanation, no markdown fences."

        try:
            message = await client.messages.create(
                model=self._resolve_model(response_format),
                max_tokens=max_tokens,
                system=full_system,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return message.content[0].text
        except anthropic.APIError as e:
            raise ProviderError(f"Claude API error: {e}") from e
