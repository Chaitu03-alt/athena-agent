"""Base protocol and data models for LLM providers and tool calling."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class ToolCallRequest:
    """Represents a tool execution request initiated by an LLM."""
    id: str
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Alias for tool_name."""
        return self.tool_name


@dataclass
class LLMResponse:
    """Standardized response from an LLM provider."""
    content: Optional[str] = None
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    raw_response: Optional[Any] = None


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers with tool calling support."""

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion for the given messages and available tools."""
        ...
