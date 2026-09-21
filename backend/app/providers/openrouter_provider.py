"""OpenRouter LLM provider implementation using AsyncOpenAI with custom base URL."""

import json
from typing import Any, Dict, List, Optional
import structlog

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore

from app.config import settings
from app.providers.base import LLMProvider, LLMResponse, ToolCallRequest

logger = structlog.get_logger(__name__)


class OpenRouterLLMProvider:
    """AsyncOpenAI client configured for OpenRouter endpoint with function-calling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "anthropic/claude-3.5-sonnet",
        base_url: str = "https://openrouter.ai/api/v1",
        client: Optional[Any] = None,
        **kwargs: Any,
    ):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model
        self.base_url = base_url
        if client is not None:
            self.client = client
        elif AsyncOpenAI is not None:
            self.client = AsyncOpenAI(
                api_key=self.api_key or "missing_key",
                base_url=self.base_url,
                **kwargs,
            )
        else:
            self.client = None

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call OpenRouter completions with function calling."""
        if self.client is None:
            raise RuntimeError("AsyncOpenAI is not installed or initialized.")

        payload: Dict[str, Any] = {
            "model": kwargs.pop("model", self.model),
            "messages": messages,
            **kwargs,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        response = await self.client.chat.completions.create(**payload)
        choice = response.choices[0]
        message = choice.message

        tool_calls: List[ToolCallRequest] = []
        if getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                call_id = tc.id
                name = tc.function.name
                args_str = tc.function.arguments or "{}"
                try:
                    arguments = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    arguments = {"raw": args_str}

                tool_calls.append(
                    ToolCallRequest(
                        id=call_id,
                        tool_name=name,
                        arguments=arguments,
                    )
                )

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            raw_response=response,
        )
