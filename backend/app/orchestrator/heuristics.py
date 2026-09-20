"""Episodic memory heuristic importance scoring and tag extraction."""

import re
from typing import List, Set

# Core keywords signaling preferences, rules, instructions, or decisions
PREFERENCE_KEYWORDS: Set[str] = {
    "remember",
    "prefer",
    "preference",
    "never",
    "always",
    "rule",
    "important",
    "decision",
    "don't",
    "dont",
    "do not",
    "hate",
    "love",
    "must",
    "should",
    "guideline",
    "convention",
    "standard",
    "workflow",
    "oop",
    "functional",
    "style",
}

# Technical keywords for tagging
TECH_KEYWORDS: Set[str] = {
    "python",
    "typescript",
    "javascript",
    "react",
    "vite",
    "fastapi",
    "postgres",
    "postgresql",
    "sqlite",
    "qdrant",
    "docker",
    "git",
    "css",
    "html",
    "tailwind",
    "api",
    "bug",
    "fix",
    "refactor",
    "test",
    "pytest",
    "deploy",
    "guidelines",
    "stop",
    "override",
    "docstring",
    "docstrings",
}

# Explicit patterns for preference overrides, negations, or guideline shifts
OVERRIDE_PATTERNS: List[str] = [
    "update my guidelines",
    "update guideline",
    "update guidelines",
    "no longer want",
    "no longer use",
    "no longer write",
    "stop using",
    "stop writing",
    "stop doing",
    "do not use",
    "do not write",
    "don't use",
    "dont use",
    "instead of",
    "switch to",
    "change my preference",
    "change preference",
    "from now on",
    "no more",
    "override",
]


def compute_importance_score(user_content: str, assistant_content: str = "") -> float:
    """Calculate heuristic importance score (0.0 to 1.0) for an episodic turn.

    Heuristic rules:
    - Explicit override / negation patterns: >= 0.85 (immediate consolidation signal)
    - Base score: 0.25
    - Length bonus: +0.1 if > 80 chars, +0.1 if > 250 chars
    - Directive/preference keywords: +0.35 if any detected
    - Code block presence: +0.1
    - Small talk penalty: -0.15 for short greeting-like messages
    """
    combined = f"{user_content} {assistant_content}".lower()
    user_lower = user_content.lower().strip()

    # Small talk check
    if len(user_lower) < 20 and any(
        user_lower.startswith(g) for g in ["hi", "hello", "hey", "yo", "sup", "howdy", "thanks", "ok"]
    ):
        return 0.15

    # Check for explicit guideline overrides/negations (highest priority: >= 0.85)
    if any(pattern in user_lower for pattern in OVERRIDE_PATTERNS):
        return 0.90

    score = 0.25

    # Keyword check in user prompt (strongest signal)
    words = set(re.findall(r"\b[a-zA-Z']+\b", user_lower))
    if any(k in words for k in PREFERENCE_KEYWORDS) or any(
        k in user_lower for k in ["i like", "i prefer", "make sure to", "don't ever", "never use"]
    ):
        score += 0.35

    # Length bonuses
    turn_length = len(user_content) + len(assistant_content)
    if turn_length > 100:
        score += 0.10
    if turn_length > 300:
        score += 0.10

    # Code block detection (indicates technical problem solving)
    if "```" in assistant_content or "```" in user_content:
        score += 0.10

    # Clamp score between 0.1 and 1.0
    return round(max(0.10, min(1.0, score)), 2)


def extract_tags(text: str) -> List[str]:
    """Extract lightweight keyword tags from text."""
    lower_text = text.lower()
    words = set(re.findall(r"\b[a-zA-Z0-9_\-]+\b", lower_text))

    tags: Set[str] = set()

    # Match technical keywords
    for kw in TECH_KEYWORDS:
        if kw in words or kw in lower_text:
            tags.add(kw)

    # Match preference flags
    for kw in ["preference", "rule", "decision", "workflow"]:
        if kw in words:
            tags.add(kw)

    if any(k in words for k in ["remember", "prefer", "never", "always"]):
        tags.add("preference")

    return sorted(list(tags))
