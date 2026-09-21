from typing import Any, Dict, Optional

from app.tools.registry import register_tool
from app.memory.kv_store import KeyValueStore

@register_tool(
    name="memory_get",
    description="Retrieve a value from the persistent key-value profile memory by key.",
    parameters={
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key to look up in memory.",
            }
        },
        "required": ["key"],
    },
)
async def memory_get(key: str) -> Optional[Any]:
    """Retrieves a value from KeyValueStore."""
    return await KeyValueStore.get(key)


@register_tool(
    name="memory_set",
    description="Store or update a key-value pair in the persistent profile memory. Value must be JSON serializable.",
    parameters={
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key to store.",
            },
            "value": {
                "description": "The value to store. Can be a string, number, boolean, array, or object.",
            },
        },
        "required": ["key", "value"],
    },
)
async def memory_set(key: str, value: Any) -> Dict[str, str]:
    """Stores a value in KeyValueStore."""
    await KeyValueStore.set(key, value)
    return {"status": "success", "key": key}
