# AGENTS.md — Grounding and Rules for AI Coding Agents

This repository implements the **Personal Adaptive AI Agent** based on the architecture, technical requirements, and phased build plan defined in the `docs/` folder.

---

## 1. Documentation Index

- [PRD.md](file:///d:/dhum/docs/PRD.md) — Product Requirements Document (Goals, Personas, Assumptions A1–A8, Lifecycle)
- [TRD.md](file:///d:/dhum/docs/TRD.md) — Technical Requirements Document (System Architecture, Non-Functional Requirements, Env config)
- [APP_FLOW.md](file:///d:/dhum/docs/APP_FLOW.md) — Detailed interaction flows (Chat turn loop, Memory retrieval, Reflection/Consolidation, Tool execution gating)
- [UI_UX.md](file:///d:/dhum/docs/UI_UX.md) — Frontend specifications, layout, visual hierarchy, and component states
- [SCHEMA.md](file:///d:/dhum/docs/SCHEMA.md) — Structured Postgres schema (SQLModel), Qdrant vector collections, REST/WebSocket API specifications
- [PLAN.md](file:///d:/dhum/docs/PLAN.md) — Step-by-step phased implementation plan. **Follow this plan strictly one phase at a time.**

---

## 2. Fixed Technology Stack (TRD Section 2)

All AI coding agents working on this project must strictly adhere to this stack. **Do NOT substitute or introduce alternative frameworks without explicit approval.**

| Layer | Chosen Technology | Constraint / Note |
|---|---|---|
| **Backend Language** | Python 3.11+ | Must use strict type hints everywhere |
| **API Framework** | FastAPI | Async, Pydantic v2 schemas, OpenAPI auto-docs |
| **Orchestration** | Custom lightweight agent loop | **No LangChain / CrewAI / AutoGen black-boxes**. Keep memory injection & prompt construction fully transparent and inspectable. |
| **Structured DB** | PostgreSQL 16 | Via SQLModel (SQLAlchemy 2.0 + Pydantic) + Alembic migrations |
| **Vector DB** | Qdrant (self-hosted via Docker) | Port 6333 / 6334; fast filtered payload search |
| **Embeddings** | Pluggable (`voyage-3` hosted default, `bge-base-en-v1.5` local fallback) | Provider abstraction via `EmbeddingProvider` |
| **LLM Provider** | Anthropic API (`claude-sonnet-4-6` primary, `claude-haiku-4-5-20251001` light/consolidation) | Provider abstraction via `LLMProvider` (OpenAI-compatible fallback) |
| **Scheduler** | APScheduler (in-process) | Nightly consolidation, memory decay, summaries |
| **Frontend** | React + TypeScript + Vite + Tailwind CSS | Desktop-first, clean dark mode UI |
| **CLI** | Typer (Python) | Rich formatting, hits same backend REST API |
| **Containerization** | Docker + Docker Compose | Unified local development & deployment |
| **Sandbox** | `subprocess` with resource/timeout limits (v1) | Sandboxed tool execution |

---

## 3. Core Safety & Guardrails (MANDATORY)

### 3.1 Destructive Actions in the Personal Agent
- Any destructive or mutating tool action (file deletion, `git push`, arbitrary shell writes, package uninstallation, running risky commands) **MUST ALWAYS require explicit human confirmation** via the Approval Queue or Confirmation Card.
- Never auto-execute destructive operations without approval gating (`CONFIRM_DESTRUCTIVE_ACTIONS=true`).

### 3.2 AI Coding Agent Safety (While Modifying This Codebase)
- **NO DESTRUCTIVE SHELL COMMANDS**: Never run `rm -rf`, disk wipes, force-pushes (`git push --force`), dropping production tables, or deleting user files without explicit confirmation.
- **Transactional Memory Writes**: When implementing memory storage, ensure structured DB and vector DB operations maintain consistency.
- **Privacy & Secrets**: API keys and bearer tokens reside in `.env`. Never commit secrets, print them in logs, or embed them into memory vector stores.

---

## 4. Coding & Architecture Conventions

- **Typed Code**: Strict type hints in Python (`typing`, Pydantic models). Strict TypeScript in frontend (`noImplicitAny`, interface definitions matching backend schemas).
- **Module Boundaries**:
  - `backend/app/api/`: Routing and request validation only.
  - `backend/app/orchestrator/`: Agent turn loop, context window management, prompt assembly.
  - `backend/app/memory/`: Scoring heuristics, retrieval algorithms, Qdrant client, consolidation logic.
  - `backend/app/tools/`: Tool definitions, risk scoring, confirmation wrappers.
  - `backend/app/providers/`: Abstract base classes for LLM and Embeddings.
  - `backend/app/models/`: SQLModel data models.
  - `backend/app/db/`: Database session, engine, migrations.
- **Incremental Phasing**: Never implement features from future phases until the current phase passes its "Definition of Done".
