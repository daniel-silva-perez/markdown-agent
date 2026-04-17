import os
from markdown_agent.providers.base import ProviderError

try:
    import openai as _openai
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


class OpenAIProvider:
    name = "openai"
    supports_json_mode = True

    def __init__(
        self,
        api_key: str | None = None,
        gate_model: str = "gpt-4o-mini",
        update_model: str = "gpt-4o",
        base_url: str | None = None,
    ):
        if not _OPENAI_AVAILABLE:
            raise ProviderError("openai package not installed. Run: pip install openai")
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            raise ProviderError("OPENAI_API_KEY not set")
        self.gate_model = gate_model
        self.update_model = update_model
        self.base_url = base_url

    async def complete(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> str:
        kwargs: dict = {}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        client = _openai.AsyncOpenAI(api_key=self._api_key, **kwargs)
        model = self.gate_model if response_format == "json" else self.update_model

        params: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            params["response_format"] = {"type": "json_object"}

        try:
            resp = await client.chat.completions.create(**params)
            return resp.choices[0].message.content or ""
        except _openai.APIError as e:
            raise ProviderError(f"OpenAI API error: {e}") from e
