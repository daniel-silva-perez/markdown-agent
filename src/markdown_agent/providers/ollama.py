import json
import httpx
from markdown_agent.providers.base import ProviderError


class OllamaProvider:
    name = "ollama"
    supports_json_mode = True

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
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
            "prompt": f"{system}\n\n{prompt}",
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if response_format == "json":
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json()["response"]
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama request failed: {e}") from e
        except (KeyError, json.JSONDecodeError) as e:
            raise ProviderError(f"Ollama response malformed: {e}") from e
