"""Groq LLM provider implementation using AsyncGroq."""

import json
from typing import Any, Dict, List, Optional
import structlog

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None  # type: ignore

from app.config import settings
from app.providers.base import LLMProvider, LLMResponse, ToolCallRequest

logger = structlog.get_logger(__name__)


class GroqLLMProvider:
    """AsyncGroq client wrapper with native function calling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        client: Optional[Any] = None,
        **kwargs: Any,
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model
        if client is not None:
            self.client = client
        elif AsyncGroq is not None:
            self.client = AsyncGroq(api_key=self.api_key or "missing_key", **kwargs)
        else:
            self.client = None

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call Groq chat completions with function calling."""
        if self.client is None:
            raise RuntimeError("AsyncGroq is not installed or initialized.")

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
