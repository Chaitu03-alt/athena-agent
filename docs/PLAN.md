# Implementation Plan
## Personal Adaptive AI Agent

A phased build order designed to be handed to an AI coding agent (e.g., Antigravity, Claude Code) one phase at a time. Each phase is independently testable and produces a working, demoable increment — don't let the agent jump ahead to later phases before earlier ones pass their "definition of done."

---

## 0. Repository Setup (Phase 0)

### 0.1 Folder Structure
```
personal-agent/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers
│   │   ├── orchestrator/     # agent turn loop, prompt assembly
│   │   ├── memory/           # retrieval, write, scoring, consolidation, pruning
│   │   ├── tools/             # tool implementations (fs, shell, git, web, code exec)
│   │   ├── providers/         # LLM + embedding provider abstractions
│   │   ├── scheduler/         # APScheduler jobs
│   │   ├── models/            # SQLModel table definitions
│   │   ├── db/                # session/engine setup, Alembic migrations
│   │   └── main.py
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── views/             # ChatView, MemoryBrowser, ApprovalQueue, Settings
│   │   ├── api/                # typed API client
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── cli/
│   └── agent_cli/              # Typer CLI, calls backend API
├── docker-compose.yml
├── .env.example
├── CLAUDE.md / AGENTS.md       # grounding doc for AI coding agents working on this repo
└── docs/                       # this set of 6 documents lives here
```

### 0.2 `AGENTS.md` / `CLAUDE.md` (create this first)
Should contain: a link/summary of the PRD/TRD, the fixed tech stack (Section 2 of TRD), coding conventions (typed Python, typed TS, no framework substitutions without approval), and a reminder that **destructive actions in the product itself must always require confirmation** — including a reminder that this applies to what the coding agent does while building it (don't let it `rm -rf` or force-push without asking).

**Definition of done**: repo scaffolded, `docker compose up` boots empty Postgres + Qdrant + a "hello world" FastAPI health endpoint + empty React shell, all containers healthy.

---

## Phase 1 — MVP Chat + Raw Memory (no consolidation yet)

**Goal**: a working chat loop with persistent episodic logging and naive retrieval — no reflection engine yet.

1. Implement `models/` (all tables from Backend Schema doc) + Alembic migration.
2. Implement `providers/llm_provider.py` (Anthropic client) and `providers/embedding_provider.py` (hosted + local switch).
3. Implement basic Orchestrator: turn loop with prompt = system prompt + last N raw messages (no memory retrieval yet).
4. Implement `POST /api/sessions/{id}/messages` with streaming response (SSE or WebSocket).
5. Write every turn to `messages` + `memory_episodic` (importance score = simple heuristic v1: length + presence of keywords like "remember," "prefer," "always/never").
6. Build minimal Chat View in frontend (send/receive, streaming render, markdown+code highlighting).
7. Build CLI `agent chat` command hitting the same API.

**Definition of done**: You can have a multi-turn conversation via CLI or web UI; every turn is persisted; restarting the app preserves session history.

---

## Phase 2 — Real Memory Retrieval + Memory Browser

1. Implement Qdrant collections + write-path (embed episodic content on write).
2. Implement Memory Manager retrieval: hybrid scored search (App Flow §2.3) feeding into prompt assembly.
3. Update Orchestrator to inject retrieved memory into system prompt with clear source labeling.
4. Build Memory Browser UI (episodic tab first) with search/filter/pin/delete.
5. Add `MemoryChip` component in Chat View showing what was retrieved per response.

**Definition of done**: Ask the agent something referencing an earlier session; it retrieves and uses that context, and you can see exactly which memory items it used.

---

## Phase 3 — Reflection, Consolidation & Procedural Memory

1. Implement the consolidation job (App Flow §5) using `LLM_MODEL_LIGHT`.
2. Implement `memory_semantic` and `memory_procedural` write paths + Approval Queue table/endpoints.
3. Build Approval Queue UI.
4. Implement explicit feedback (👍/👎, correction) wired to priority consolidation.
5. Implement pruning/decay job (App Flow §6).
6. Add procedural memory injection into system prompt (always-on, small).

**Definition of done**: Correct the agent about a preference twice; within one reflection cycle (or via "reflect now"), a procedural rule proposal appears in the Approval Queue; after approval, future responses respect it.

---

## Phase 4 — Tool Use & Codebase RAG

1. Implement Tool Executor with risk classification (safe/destructive) and confirmation gating (App Flow §4).
2. Implement tools: file read/write, shell exec (sandboxed), git status/diff/log/commit-propose, code execution (Python/JS), web search.
3. Implement Project registration + codebase indexer + watcher (App Flow §7).
4. Wire `@project`/`@file` mention scoping in Chat input.
5. Build destructive-action `ConfirmationCard` UI end-to-end.

**Definition of done**: Point the agent at a real repo; ask it a question requiring reading actual project files; it retrieves real code context and can propose (with confirmation) a file edit or git commit.

---

## Phase 5 — Daily Workflow & Polish

1. Implement daily/weekly summary job + UI view.
2. Implement Settings screen (retention window, model selection, confirmation toggle, export/backup).
3. Implement Command Palette + slash commands.
4. Add usage/cost tracking (`GET /api/system/usage`).
5. Backup job (nightly Postgres dump + Qdrant snapshot to local disk).
6. Pass over accessibility (keyboard nav, contrast) and responsive breakpoints per UI/UX brief.

**Definition of done**: The app is comfortable for genuine daily use — summaries, backups, and settings all work without touching the database directly.

---

## Phase 6 (Optional / Stretch) — Local Fine-Tuning Loop

Only after Phases 1–5 are stable and you've accumulated real usage data:
1. Export curated, approved corrections/preferences from `memory_procedural` + high-confidence `memory_semantic` as a training set.
2. Stand up a local open-weight model (e.g., via Ollama/vLLM) as a secondary "personalized" model.
3. Periodic LoRA fine-tuning job using the exported dataset; evaluate against a held-out set of "should now behave differently" test prompts before promoting the new adapter to active use.
4. Add a model-comparison view (frontier model vs. fine-tuned local model responses side-by-side) so you can judge whether fine-tuning is actually adding value before relying on it.

**Note**: treat this phase as a genuine R&D effort, not a guaranteed win — memory-based adaptation (Phases 1–5) already covers most "self-learning" value with far less risk of overfitting or regressions.

---

## Testing Strategy (applies across all phases)

- **Unit tests**: memory scoring functions, retrieval ranking, risk classification, prompt assembly — pure functions, high coverage.
- **Integration tests**: full turn flow against a test Postgres/Qdrant (docker-compose test profile), including a consolidation dry-run.
- **Personal benchmark set** (build incrementally as you use it): a growing list of "the agent should remember/do X given Y" cases you can replay as a regression suite — this is your real product-quality signal for a system like this, more than generic unit tests.
- **Manual QA checklist per phase**: re-run the "Definition of done" bullet for that phase before moving on.

## Suggested Build Order Summary

| Phase | Deliverable | Est. relative effort |
|---|---|---|
| 0 | Scaffolding | Small |
| 1 | Chat + raw episodic logging | Medium |
| 2 | Real retrieval + Memory Browser | Medium |
| 3 | Consolidation + procedural memory + Approval Queue | Large |
| 4 | Tools + codebase RAG | Large |
| 5 | Daily workflow + polish | Medium |
| 6 | Optional fine-tuning loop | Large (optional) |

Hand each phase to the coding agent as its own task/session, pointing it at `AGENTS.md` plus the relevant sections of these six documents, and require it to hit that phase's Definition of Done before proceeding.