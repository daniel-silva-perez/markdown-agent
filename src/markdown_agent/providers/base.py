from typing import Protocol, runtime_checkable


class ProviderError(Exception):
    pass


@runtime_checkable
class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def supports_json_mode(self) -> bool: ...

    async def complete(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> str:
        """Return completion text. Raises ProviderError on failure."""
        ...
