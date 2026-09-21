"""Resilient LLM Provider Chain with failover and logging on errors and 429 rate limits."""

from typing import Any, Dict, List, Optional
import structlog

from app.providers.base import LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)


class ProviderChain:
    """Orchestrates an ordered list of LLM providers with automatic failover."""

    def __init__(self, providers: List[LLMProvider]):
        if not providers:
            raise ValueError("ProviderChain requires at least one provider.")
        self.providers = list(providers)

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Attempt completion sequentially across providers until one succeeds."""
        last_exception: Optional[Exception] = None

        for index, provider in enumerate(self.providers):
            provider_name = getattr(provider, "__class__", type(provider)).__name__
            try:
                logger.info(
                    "Attempting completion with provider",
                    provider_index=index,
                    provider=provider_name,
                )
                response = await provider.complete(messages=messages, tools=tools, **kwargs)
                return response
            except Exception as exc:
                last_exception = exc
                logger.warning(
                    "Provider execution failed; triggering failover",
                    provider_index=index,
                    provider=provider_name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        error_message = f"All {len(self.providers)} providers in chain failed."
        if last_exception:
            error_message += f" Last error: {last_exception}"
        logger.error("Provider chain exhausted with failure", error=error_message)
        raise RuntimeError(error_message) from last_exception

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ):
        """Stream tokens using the first working provider that supports stream_chat."""
        for provider in self.providers:
            if hasattr(provider, "stream_chat"):
                try:
                    async for chunk in provider.stream_chat(messages, system_prompt):
                        yield chunk
                    return
                except Exception as exc:
                    logger.warning("Provider stream_chat failed; trying next provider", error=str(exc))
        # Fallback to complete
        resp = await self.complete(messages)
        yield resp.content or ""
