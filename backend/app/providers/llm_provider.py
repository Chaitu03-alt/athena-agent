"""LLM Provider abstraction and Anthropic streaming implementation."""

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional
import structlog
from app.config import settings

logger = structlog.get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens for a list of chat messages."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a complete non-streamed response."""
        pass


class AnthropicLLMProvider(LLMProvider):
    """Anthropic Claude API client with streaming support."""

    def __init__(self, api_key: str, model: Optional[str] = None) -> None:
        import anthropic

        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model or settings.LLM_MODEL_PRIMARY

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens using Anthropic client."""
        # Convert messages format if needed (Anthropic expects role: user/assistant)
        formatted_messages = []
        for msg in messages:
            if msg["role"] in ("user", "assistant"):
                formatted_messages.append({"role": msg["role"], "content": msg["content"]})

        kwargs: Dict[str, object] = {
            "max_tokens": 4096,
            "messages": formatted_messages,
            "model": self.model,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate single complete response."""
        full_text = []
        async for chunk in self.stream_chat(messages, system_prompt):
            full_text.append(chunk)
        return "".join(full_text)


class MockLLMProvider(LLMProvider):
    """Simulated LLM provider used for testing and local development when API key is not set."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or "mock-claude-sonnet-4-6"

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream simulated response."""
        last_message = messages[-1]["content"] if messages else ""
        lower_msg = last_message.lower()

        # Check if system prompt contains recalled guidelines or Qdrant context
        sys_str = system_prompt or ""
        lower_sys = sys_str.lower()
        has_strict_typing = "strict typing" in lower_sys
        has_oop = "object-oriented" in lower_sys or "class-based" in lower_sys or "oop" in lower_sys
        has_modular_functional = ("modular functional" in lower_sys or "functional style" in lower_sys) and not has_oop
        no_docstrings = any(t in lower_sys for t in ["do not write docstrings", "no docstrings", "stop writing docstrings", "never write docstrings", "omit docstrings", "without docstrings"])

        # Build dynamic simulated response
        if "remember" in lower_msg or "never" in lower_msg or ("prefer" in lower_msg and "python" not in lower_msg):
            reply = (
                f"Understood! I've noted that preference carefully in my episodic memory log: "
                f"\"{last_message}\". In our reflection cycle, this will be consolidated into permanent procedural memory rules."
            )
        elif any(w in lower_msg for w in ["code", "function", "python", "example", "write", "implement", "script", "create"]):
            if has_oop:
                guide_str = "object-oriented class-based design" + (" with strict typing" if has_strict_typing else "")
                doc_note = " and without docstrings" if no_docstrings else ""

                if no_docstrings:
                    code_body = (
                        "from typing import Generic, List, Optional, TypeVar\n\n"
                        "T = TypeVar('T')\n"
                        "R = TypeVar('R')\n\n"
                        "class DataFilterService(Generic[T]):\n"
                        "    def __init__(self, threshold: Optional[int] = None) -> None:\n"
                        "        self.threshold = threshold\n\n"
                        "    def filter_records(self, records: List[T]) -> List[T]:\n"
                        "        return [item for item in records if self._is_valid(item)]\n\n"
                        "    def _is_valid(self, item: T) -> bool:\n"
                        "        return True\n"
                    )
                else:
                    code_body = (
                        "from typing import Generic, List, Optional, TypeVar\n\n"
                        "T = TypeVar('T')\n"
                        "R = TypeVar('R')\n\n"
                        "class DataFilterService(Generic[T]):\n"
                        "    \"\"\"Modular OOP service encapsulating filtering logic.\"\"\"\n\n"
                        "    def __init__(self, threshold: Optional[int] = None) -> None:\n"
                        "        self.threshold = threshold\n\n"
                        "    def filter_records(self, records: List[T]) -> List[T]:\n"
                        "        \"\"\"Class method processing input records.\"\"\"\n"
                        "        return [item for item in records if self._is_valid(item)]\n\n"
                        "    def _is_valid(self, item: T) -> bool:\n"
                        "        return True\n"
                    )

                reply = (
                    f"Adhering to your active preferences for **{guide_str}{doc_note}**, here is an idiomatic solution:\n\n"
                    f"```python\n{code_body}```\n\n"
                    "This implementation uses explicit object-oriented classes and encapsulation per your updated preferences."
                )
            else:
                guidelines = []
                if has_strict_typing:
                    guidelines.append("strict typing with complete annotations")
                if has_modular_functional:
                    guidelines.append("modular functional composition")
                if no_docstrings:
                    guidelines.append("no docstrings")
                guide_str = " and ".join(guidelines) if guidelines else "clean architecture"

                if no_docstrings:
                    code_body = (
                        "from typing import Callable, Iterable, List, TypeVar\n\n"
                        "T = TypeVar('T')\n"
                        "R = TypeVar('R')\n\n"
                        "def pipe_transform(\n"
                        "    items: Iterable[T],\n"
                        "    transform_fn: Callable[[T], R],\n"
                        ") -> List[R]:\n"
                        "    return [transform_fn(item) for item in items]\n\n"
                        "def filter_valid(\n"
                        "    items: Iterable[T],\n"
                        "    predicate: Callable[[T], bool],\n"
                        ") -> List[T]:\n"
                        "    return [item for item in items if predicate(item)]\n"
                    )
                else:
                    code_body = (
                        "from typing import Callable, Iterable, List, TypeVar\n\n"
                        "T = TypeVar('T')\n"
                        "R = TypeVar('R')\n\n"
                        "def pipe_transform(\n"
                        "    items: Iterable[T],\n"
                        "    transform_fn: Callable[[T], R],\n"
                        ") -> List[R]:\n"
                        "    \"\"\"Pure transformation pipeline adhering to modular functional principles.\"\"\"\n"
                        "    return [transform_fn(item) for item in items]\n\n"
                        "def filter_valid(\n"
                        "    items: Iterable[T],\n"
                        "    predicate: Callable[[T], bool],\n"
                        ") -> List[T]:\n"
                        "    \"\"\"Functional filter step.\"\"\"\n"
                        "    return [item for item in items if predicate(item)]\n"
                    )

                reply = (
                    f"Adhering to your recalled preference for **{guide_str}**, here is an idiomatic solution:\n\n"
                    f"```python\n{code_body}```\n\n"
                    "This implementation follows your learned preferences."
                )
        elif "hello" in lower_msg or "hi" in lower_msg:
            learned_note = ""
            if has_strict_typing or has_modular_functional or has_oop:
                learned_note = " I have loaded your active preferences from procedural memory."
            reply = (
                f"Hello! I am your Personal Adaptive AI Agent.{learned_note} What would you like to work on today?"
            )
        else:
            recalled_highlights = []
            if "recalled memories" in lower_sys:
                recalled_highlights.append("vector context recalled from Qdrant")
            if has_strict_typing or has_modular_functional:
                recalled_highlights.append("active guidelines loaded (strict typing & modular functional style)")
            context_note = f" [{', '.join(recalled_highlights)}]" if recalled_highlights else ""

            reply = (
                f"I processed your query: \"{last_message}\".{context_note}\n\n"
                "How would you like to proceed with your code or project?"
            )

        # Stream words with slight delay to simulate streaming tokens
        words = reply.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield chunk
            await asyncio.sleep(0.02)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        prompt_str = (system_prompt or "") + " " + " ".join(m.get("content", "") for m in messages)
        lower_prompt = prompt_str.lower()
        if "consolidation" in lower_prompt or "reflection" in lower_prompt or "extract" in lower_prompt:
            import json
            import re
            
            # Simple rule-based extraction for mock mode
            extracted = []
            seen_statements = set()
            for m in messages:
                raw_content = m.get("content", "")
                # Only extract from actual conversation turns, never from the active rules context
                if "Conversation Turns to Consolidate" in raw_content:
                    content = raw_content.split("Conversation Turns to Consolidate")[-1]
                else:
                    content = raw_content

                # Check for preferences/rules only from user lines
                for line in content.split("\n"):
                    line_clean = line.strip()
                    if not line_clean.lower().startswith("user:"):
                        continue
                    low_line = line_clean.lower()
                    stmt = None
                    cat = "coding_style"
                    mtype = "procedural"
                    conf = 0.95

                    supersedes_stmt = None
                    if "oop" in low_line or "object-oriented" in low_line or "classes" in low_line:
                        stmt = "Prefer writing Python code in an object-oriented class-based style."
                        supersedes_stmt = "Prefer writing Python code in a modular functional style."
                    elif "typing" in low_line or "strict" in low_line:
                        stmt = "Prefer strict typing in Python code."
                    elif "docstring" in low_line or "docstrings" in low_line:
                        if any(neg in low_line for neg in ["no longer", "stop", "do not", "don't", "never", "omit", "skip", "no "]):
                            stmt = "Do not write docstrings for public functions."
                            supersedes_stmt = "Always write docstrings for public functions."
                        else:
                            stmt = "Always write docstrings for public functions."
                            supersedes_stmt = "Do not write docstrings for public functions."
                    elif "modular" in low_line or "functional" in low_line:
                        stmt = "Prefer writing Python code in a modular functional style."
                        supersedes_stmt = "Prefer writing Python code in an object-oriented class-based style."
                    elif "prefer" in low_line or "remember" in low_line:
                        rule_text = re.sub(r'^(user:\s*|hey athena,?\s*|remember that\s*|i prefer\s*)', '', line_clean, flags=re.IGNORECASE).strip()
                        stmt = f"Prefer {rule_text}" if not rule_text.lower().startswith("prefer") else rule_text
                        conf = 0.85
                    elif "uses " in low_line or "built with" in low_line or "stack" in low_line:
                        stmt = line_clean
                        cat = "project_fact"
                        mtype = "semantic"
                        conf = 0.90

                    if stmt and stmt not in seen_statements:
                        seen_statements.add(stmt)
                        extracted.append({
                            "type": mtype,
                            "statement": stmt,
                            "category": cat,
                            "confidence": conf,
                            "supersedes_statement": supersedes_stmt,
                        })

            if not extracted:
                extracted.append({
                    "type": "procedural",
                    "statement": "Consolidated developer guideline from conversation history.",
                    "category": "workflow",
                    "confidence": 0.80,
                })

            return json.dumps(extracted)

        full_text = []
        async for chunk in self.stream_chat(messages, system_prompt):
            full_text.append(chunk)
        return "".join(full_text)


def get_llm_provider(model: Optional[str] = None) -> LLMProvider:
    """Factory to retrieve configured LLM provider."""
    api_key = settings.ANTHROPIC_API_KEY
    if api_key and api_key.strip() and not api_key.startswith("your_anthropic_api_key"):
        logger.info("Using Anthropic LLM Provider", model=model or settings.LLM_MODEL_PRIMARY)
        return AnthropicLLMProvider(api_key=api_key, model=model)

    logger.info("Using Mock LLM Provider (no valid ANTHROPIC_API_KEY detected)")
    return MockLLMProvider(model=model)
