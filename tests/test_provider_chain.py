"""Tests for Resilient ProviderChain with automatic failover and error recovery."""

from typing import Any, Dict, List, Optional
import pytest

from app.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from app.providers.chain import ProviderChain
from app.orchestrator.turn import AgentTurn


class MockFailingProvider:
    """Simulates a provider that raises a 429 Rate Limit error."""

    def __init__(self, error_code: int = 429):
        self.call_count = 0
        self.error_code = error_code

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.call_count += 1
        raise RuntimeError(f"HTTP {self.error_code}: Too Many Requests / Rate limit exceeded")


class MockSuccessProvider:
    """Simulates a healthy provider returning an LLMResponse."""

    def __init__(self, response_text: str = "Success from fallback provider"):
        self.call_count = 0
        self.response_text = response_text

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            content=self.response_text,
            tool_calls=[],
        )


class MockToolCallingProvider:
    """Simulates a provider that issues a tool call on first turn, then final answer on second."""

    def __init__(self):
        self.turn = 0

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.turn += 1
        if self.turn == 1:
            return LLMResponse(
                content="Writing notes...",
                tool_calls=[
                    ToolCallRequest(
                        id="call_write_1",
                        tool_name="file_write",
                        arguments={"path": "agent_test.txt", "content": "Autonomous turn success."},
                    )
                ],
            )
        return LLMResponse(
            content="File written and verified.",
            tool_calls=[],
        )


@pytest.mark.asyncio
async def test_provider_chain_429_failover():
    """Verify mock 429 triggers transparent fallback to second provider in chain."""
    failing_provider = MockFailingProvider(error_code=429)
    success_provider = MockSuccessProvider(response_text="Recovered by fallback provider")

    chain = ProviderChain([failing_provider, success_provider])
    messages = [{"role": "user", "content": "Hello Athena"}]

    response = await chain.complete(messages=messages)

    # Provider 1 should have been called and failed
    assert failing_provider.call_count == 1
    # Provider 2 should have been called and succeeded
    assert success_provider.call_count == 1
    # Output should come from Provider 2
    assert response.content == "Recovered by fallback provider"


@pytest.mark.asyncio
async def test_provider_chain_exhaustion_raises():
    """Verify ProviderChain raises RuntimeError when all providers fail."""
    provider1 = MockFailingProvider(error_code=429)
    provider2 = MockFailingProvider(error_code=500)

    chain = ProviderChain([provider1, provider2])
    messages = [{"role": "user", "content": "Test failover exhaustion"}]

    with pytest.raises(RuntimeError) as exc_info:
        await chain.complete(messages=messages)

    assert "All 2 providers in chain failed" in str(exc_info.value)
    assert provider1.call_count == 1
    assert provider2.call_count == 1


@pytest.mark.asyncio
async def test_agent_turn_with_provider_chain_and_tool_execution():
    """Verify AgentTurn correctly drives tool execution and multi-step turn loop."""
    failing_provider = MockFailingProvider(error_code=429)
    tool_calling_provider = MockToolCallingProvider()

    # Resilient chain with failing first provider
    chain = ProviderChain([failing_provider, tool_calling_provider])
    turn = AgentTurn(provider=chain, max_tool_calls=5, tool_timeout=15)

    result = await turn.execute([{"role": "user", "content": "Save note"}])

    assert result["role"] == "assistant"
    assert "File written and verified." in result["content"]
    assert result["tool_calls_count"] == 1
    assert len(result["messages"]) >= 3
