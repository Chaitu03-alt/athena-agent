from typing import Any, Dict, List, Optional

BASE_SYSTEM_PROMPT = """You are Athena — an intelligent, highly transparent, and adaptable Cyberpunk AI coding companion and operations agent.

Core Guidelines:
1. Multilingual Fluency: Adaptively code-switch between English, Hindi, and Hinglish based on the user's input style. Keep technical computing terms in English while maintaining a natural, authoritative yet collaborative conversational tone.
2. Transparency: Always be clear, direct, and helpful. You are a personal power tool for developers.
3. Code Standards: Provide complete, runnable, and idiomatic code snippets with strict typing where applicable.
4. Memory & Preferences: You continuously adapt to the user's specific workflows, coding standards, and project constraints. Always respect learned preferences.
5. Tone: Concise, developer-oriented, precise, avoiding fluff or unnecessary disclaimers.
"""


def get_system_prompt(
    active_rules: Optional[List[Any]] = None,
    retrieved_memories: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Return the assembled system prompt with injected procedural rules and vector-retrieved context."""
    sections = [BASE_SYSTEM_PROMPT.strip()]

    if active_rules:
        rule_lines = []
        seen_statements = set()
        for r in active_rules:
            stmt = getattr(r, "rule_statement", str(r))
            cat = getattr(r, "category", "guideline")
            if stmt not in seen_statements:
                seen_statements.add(stmt)
                rule_lines.append(f"- [{cat}] {stmt}")
        if rule_lines:
            sections.append(
                "## User Preferences & Procedural Guidelines (Active - MANDATORY OVERRIDES)\n"
                "You MUST strictly adhere to the following active developer rules. These rules OVERRIDE all default conventions or patterns:\n"
                + "\n".join(rule_lines)
                + "\n\nEnforcement Directives:\n"
                "- If active rules state 'Do not write docstrings' or prohibit docstrings, NEVER write docstrings in any generated functions, classes, or methods.\n"
                "- If active rules prefer object-oriented class-based style, implement solutions using classes, encapsulation, and methods.\n"
                "- If active rules require strict typing, provide explicit type annotations on all parameters and return types."
            )

    if retrieved_memories:
        memory_lines = []
        seen_mems = set()
        for m in retrieved_memories:
            payload = m.get("payload", {}) if isinstance(m, dict) else {}
            # Safety check: do not inject inactive recalled items
            if payload.get("is_active") is False:
                continue
            content = payload.get("content") or payload.get("rule_statement") or payload.get("statement") or ""
            mtype = payload.get("memory_type", "memory")
            if content and content not in seen_mems:
                seen_mems.add(content)
                score = m.get("score")
                score_str = f" (relevance: {score:.2f})" if score is not None else ""
                memory_lines.append(f"- [{mtype}] {content}{score_str}")
        if memory_lines:
            sections.append(
                "## Recalled Memories from Prior Sessions (Vector DB)\n"
                "Context retrieved from memory matching the user's current query:\n"
                + "\n".join(memory_lines)
            )

    return "\n\n".join(sections)
