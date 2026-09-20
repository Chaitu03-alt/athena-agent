# Product Requirements Document (PRD)
## Personal Adaptive AI Agent ("Athena" — working name)

---

## 0. Key Assumptions (read this first)

Since this is a single-user, private tool, I made the following assumptions instead of asking a long list of questions. Change any of these and the downstream documents should be updated accordingly.

| # | Assumption | Rationale |
|---|---|---|
| A1 | **Single user, single tenant.** No multi-user auth system, no public deployment. | Stated goal: "private, daily use." |
| A2 | **Local-first deployment** on your own machine (or a personal VPS you control), via Docker Compose. | Privacy, cost control, full data ownership — essential for a memory system that stores your private work. |
| A3 | **Base LLM = hosted frontier model via API** (Claude as primary, OpenAI-compatible as fallback), *not* a self-hosted/fine-tuned base model for v1. "Continual learning" is implemented as an **architecture around** the frozen model (memory, retrieval, reflection, preference profile) — not weight updates. | You explicitly said foundation models can't be continuously retrained; this is the industry-accepted pattern (see MemGPT/Letta, Generative Agents). |
| A4 | **Optional Phase 4 stretch goal**: periodic parameter-efficient fine-tuning (LoRA) on a locally-hosted open-weight model, using curated interaction data, as a true "weight-level" learning loop — kept out of MVP scope. | Real fine-tuning loops are expensive/risky to build first; memory-based adaptation delivers 80% of the value at 10% of the engineering cost. |
| A5 | **Primary use cases**: (1) coding assistant with project/codebase awareness, (2) complex analytical/research tasks, (3) daily workflow assistant (notes, task tracking, recurring routines). | From your prompt. |
| A6 | **Interfaces**: a CLI (fast, scriptable, coding-friendly) + a local web dashboard (chat + memory browser + settings). No mobile app in v1. | Matches "coding tool" usage pattern; web UI needed to inspect/curate memory. |
| A7 | You are comfortable with Docker, Python, and basic self-hosting. | Implied by "build using AI coding tools." |
| A8 | Data stays local by default; only inference calls go to the LLM provider's API. Embeddings can be local or hosted (configurable). | Privacy-first default, pluggable for quality. |

If any assumption is wrong, flag it before implementation starts — it changes the Technical and Schema documents materially.

---

## 1. Vision Statement

Build a personal AI agent that behaves less like a stateless chatbot and more like an assistant that **actually gets better at working with you over time** — remembering your projects, your preferences, your recurring mistakes and corrections, your coding style, and your goals — without requiring you to re-explain context every session, and without needing to retrain the underlying model.

## 2. Problem Statement

Current LLM-based assistants (including default Claude/ChatGPT sessions) are **stateless across sessions** or rely on shallow "memory" features that store isolated facts. They:
- Forget project context between sessions.
- Don't learn your coding conventions, tone preferences, or recurring corrections.
- Can't distinguish "important, durable" knowledge from "one-off, noisy" chat.
- Give no visibility or control over what's "remembered."

## 3. Goals

1. Persistent, structured memory across sessions (episodic, semantic, procedural).
2. Automatic **consolidation** of raw interactions into durable knowledge (a background "reflection" process), not just raw log storage.
3. Measurable behavioral adaptation: agent's coding style, tool choices, and answers should visibly improve/personalize over weeks of use.
4. Full transparency & control: you can view, edit, pin, or delete anything the agent "knows" about you.
5. Deep integration with coding workflows (repo-aware context, code execution, git-aware).
6. Runs entirely under your control (local-first, no vendor lock-in on data).

## 4. Non-Goals (explicitly out of scope for v1)

- Multi-user support / team features.
- Mobile-native app.
- Real-time weight fine-tuning of a frontier model (not offered by providers) — see A3/A4.
- Full autonomous/unsupervised agent operation (no unattended long-horizon autonomy in v1; agent asks before high-impact actions).
- Building a custom foundation model.

## 5. Target User

You — a single technical user doing coding, analysis, and daily workflow management, who wants an assistant that compounds in usefulness over time.

## 6. Core Features (MVP — Phase 1–2)

### 6.1 Conversational Core
- Multi-turn chat with streaming responses, via CLI and web UI.
- Session concept: each conversation is a "session," logged and later mined for memory.

### 6.2 Memory System
- **Episodic memory**: every meaningful exchange stored with metadata (timestamp, session, topic tags, importance score).
- **Semantic memory**: durable facts/knowledge distilled from episodes (e.g., "User prefers pytest over unittest," "Project X uses FastAPI + Postgres").
- **Procedural memory**: learned workflows/preferences (e.g., "Always run linter before showing code," "User wants concise commit messages").
- Retrieval: hybrid semantic + keyword + recency + importance-weighted search injected into context per turn.
- Memory browser UI: search, view, edit, pin (never forget), delete, or mark "wrong" (triggers correction).

### 6.3 Reflection & Consolidation Engine
- Scheduled background job ("sleep cycle") that:
  - Reviews recent episodic memory.
  - Extracts candidate semantic/procedural updates.
  - Detects contradictions with existing memory and resolves/flags them.
  - Prunes low-value/noisy episodic entries after consolidation window.
- Manual "reflect now" trigger available.

### 6.4 Feedback Loop
- Explicit feedback: 👍/👎 per response, free-text correction ("actually I prefer X").
- Implicit feedback: when you edit/reject agent-suggested code or redo a task differently, that's logged as a correction signal.
- Feedback feeds directly into procedural memory updates (not just logs).

### 6.5 Tool Use / Actions
- Code execution sandbox (Python/JS at minimum).
- File system read/write within designated project directories.
- Git awareness (read status/diff/log; propose commits — never auto-push without confirmation).
- Web search (for research tasks).
- Shell command execution with confirmation gating for destructive/irreversible actions.

### 6.6 Codebase / Document Indexing (RAG)
- Point the agent at one or more project directories; it indexes code + docs into vector store for retrieval-augmented answers.
- Re-index on file change (watcher) or on demand.

### 6.7 Daily Workflow Support
- Lightweight task/note capture accessible from chat ("remember to...", "add task...").
- Daily/weekly summary generation (what was worked on, open threads, pending decisions).

## 7. Phase 3+ Features (post-MVP)

- Preference-profile-driven prompt personalization (auto-adjust system prompt sections based on learned procedural memory).
- Multi-model routing (cheap model for retrieval/summarization, frontier model for reasoning).
- Optional local LoRA fine-tuning loop on an open-weight model using curated corrections (A4).
- Voice interface.
- Scheduled proactive agent runs (e.g., morning briefing) — with strict user-approval gating for any external action.

## 8. Success Metrics (single-user, so qualitative + light quantitative)

- **Recall accuracy**: agent correctly retrieves relevant past context ≥90% of the time when tested against a personal benchmark set of "should remember this" cases.
- **Reduced re-explanation**: subjectively, you stop having to restate project context/preferences within 2–4 weeks of daily use.
- **Correction decay**: the same correction should not need to be given more than twice before the agent adapts.
- **Latency**: memory retrieval adds <500ms overhead to a turn (local vector search).
- **Zero silent data loss**: nothing in "pinned" memory is ever pruned.

## 9. Constraints & Risks

| Risk | Mitigation |
|---|---|
| Memory bloat / retrieval noise over time | Importance scoring + decay + consolidation pruning (see Backend Schema doc) |
| Hallucinated "facts" entering semantic memory | Consolidation engine requires confidence threshold + you can review/reject consolidation proposals before commit (approval queue in v1) |
| API cost creep (frontier model calls for consolidation too) | Use a cheaper/faster model for consolidation/summarization; reserve frontier model for primary reasoning |
| Local infra complexity (Docker, vector DB) | Provide one-command `docker compose up` setup; Implementation Plan gives exact steps |
| Privacy of stored personal/project data | Local-first storage; API calls contain only what's needed per turn; secrets never stored in plaintext memory |

## 10. User Stories (representative sample)

1. *As the user*, when I open a new session and mention a project by name, the agent should retrieve relevant prior decisions/context without me re-explaining.
2. *As the user*, when I correct the agent's code style once or twice, it should stop making that mistake in future sessions.
3. *As the user*, I want to see exactly what the agent "remembers" about me and delete anything wrong.
4. *As the user*, I want a daily summary of what I worked on and what's still open.
5. *As the user*, I want the agent to index my active repo so it can answer questions about my actual codebase, not generic advice.
6. *As the user*, I want destructive actions (file delete, git push, shell `rm`) to always require explicit confirmation.

## 11. Glossary

- **Episodic memory**: raw record of what happened in a specific interaction.
- **Semantic memory**: consolidated, general facts/knowledge (not tied to one moment).
- **Procedural memory**: learned "how to behave" rules/preferences.
- **Consolidation / Reflection**: background process converting episodic → semantic/procedural memory.
- **Importance score**: heuristic (recency + frequency + explicit signal + LLM-judged salience) determining retrieval priority and pruning eligibility.