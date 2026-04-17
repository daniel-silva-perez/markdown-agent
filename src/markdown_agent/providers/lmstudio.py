import httpx
from markdown_agent.providers.base import ProviderError


class LMStudioProvider:
    """LM Studio exposes an OpenAI-compatible REST API."""

    name = "lmstudio"
    supports_json_mode = True

    def __init__(self, base_url: str = "http://localhost:1234", model: str = "local-model"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": "Bearer lm-studio"},
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            raise ProviderError(f"LM Studio request failed: {e}") from e
        except (KeyError, IndexError) as e:
            raise ProviderError(f"LM Studio response malformed: {e}") from e
