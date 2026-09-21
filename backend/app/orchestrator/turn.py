"""Agent turn execution loop with tool dispatching and security timeouts."""

import asyncio
import inspect
import json
from typing import Any, Dict, List, Optional
import structlog

from app.config import settings
from app.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from app.tools.registry import TOOL_REGISTRY, get_registered_tools
from app.tools.workspace import ToolSecurityError
from app.api.telemetry_bus import telemetry_bus

logger = structlog.get_logger(__name__)


class AgentTurn:
    """Executes a multi-step agent turn capped by MAX_TOOL_CALLS with strict per-tool timeouts."""

    def __init__(
        self,
        provider: LLMProvider,
        max_tool_calls: Optional[int] = None,
        tool_timeout: Optional[int] = None,
    ):
        self.provider = provider
        self.max_tool_calls = max_tool_calls or settings.MAX_TOOL_CALLS
        self.tool_timeout = tool_timeout or settings.TOOL_TIMEOUT_SECONDS

    async def _execute_tool(self, tool_call: ToolCallRequest) -> str:
        """Safely execute a single tool call with timeout and security boundaries."""
        spec = TOOL_REGISTRY.get(tool_call.tool_name)
        if not spec:
            return f"Error: Tool '{tool_call.tool_name}' is not registered."

        try:
            kwargs = tool_call.arguments or {}
            if inspect.iscoroutinefunction(spec.func):
                result = await asyncio.wait_for(
                    spec.func(**kwargs),
                    timeout=self.tool_timeout,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(spec.func, **kwargs),
                    timeout=self.tool_timeout,
                )

            return str(result)
        except asyncio.TimeoutError:
            logger.warning(
                "Tool execution timed out",
                tool=tool_call.tool_name,
                timeout=self.tool_timeout,
            )
            return f"Error: Tool execution timed out after {self.tool_timeout} seconds."
        except ToolSecurityError as sec_err:
            logger.warning(
                "Tool security violation",
                tool=tool_call.tool_name,
                error=str(sec_err),
            )
            return f"Security Error: {str(sec_err)}"
        except Exception as exc:
            logger.warning(
                "Tool execution error",
                tool=tool_call.tool_name,
                error=str(exc),
            )
            return f"Tool Error: {str(exc)}"

    async def execute(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the agent turn loop until a final assistant text response is produced
        or until MAX_TOOL_CALLS is reached.
        """
        conversation: List[Dict[str, Any]] = list(messages)
        if system_prompt and not any(m.get("role") == "system" for m in conversation):
            conversation.insert(0, {"role": "system", "content": system_prompt})

        tools = get_registered_tools()
        total_tool_calls = 0

        while total_tool_calls < self.max_tool_calls:
            response: LLMResponse = await self.provider.complete(
                messages=conversation,
                tools=tools if tools else None,
            )

            # If no tool calls requested, turn is complete
            if not response.tool_calls:
                conversation.append({
                    "role": "assistant",
                    "content": response.content or "",
                })
                return {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls_count": total_tool_calls,
                    "messages": conversation,
                }

            # Assistant message with tool calls
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.arguments)
                            if isinstance(tc.arguments, dict)
                            else str(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            conversation.append(assistant_msg)

            # Dispatch each tool call
            for tc in response.tool_calls:
                if total_tool_calls >= self.max_tool_calls:
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.tool_name,
                        "content": f"Error: Maximum tool call budget ({self.max_tool_calls}) reached.",
                    })
                    break
                
                await telemetry_bus.publish("tool_call", {
                    "tool_name": tc.tool_name, 
                    "arguments": tc.arguments if isinstance(tc.arguments, dict) else str(tc.arguments)
                })

                output = await self._execute_tool(tc)
                
                await telemetry_bus.publish("tool_result", {
                    "tool_name": tc.tool_name,
                    "result": output
                })
                
                total_tool_calls += 1
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.tool_name,
                    "content": output,
                })

        # Cap reached: execute final completion to conclude turn
        final_response: LLMResponse = await self.provider.complete(
            messages=conversation,
            tools=None,
        )
        content = final_response.content or "Tool call budget exceeded. Turn terminated."
        conversation.append({"role": "assistant", "content": content})

        return {
            "role": "assistant",
            "content": content,
            "tool_calls_count": total_tool_calls,
            "messages": conversation,
        }
