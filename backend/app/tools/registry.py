"""Tool registry and specifications for autonomous agent tools."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolSpec:
    """Specification and executable wrapper for an agent tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., Any]

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert ToolSpec to standard OpenAI function tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


TOOL_REGISTRY: Dict[str, ToolSpec] = {}


def register_tool(name: str, description: str, parameters: Dict[str, Any]):
    """Decorator to register a tool function in the global TOOL_REGISTRY."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        spec = ToolSpec(
            name=name,
            description=description,
            parameters=parameters,
            func=func,
        )
        TOOL_REGISTRY[name] = spec
        return func

    return decorator


def get_registered_tools() -> List[Dict[str, Any]]:
    """Return all registered tools formatted as OpenAI tool specifications."""
    return [spec.to_openai_schema() for spec in TOOL_REGISTRY.values()]
