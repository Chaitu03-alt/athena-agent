# Technical Requirements Document (TRD)
## Personal Adaptive AI Agent

Builds on assumptions A1–A8 in the PRD. This document is the authoritative source for stack, architecture, and non-functional requirements — the coding agent should treat choices below as fixed unless you say otherwise.

---

## 1. High-Level Architecture

```
                          ┌─────────────────────────────┐
                          │        Interfaces           │
                          │  CLI (Typer)  |  Web UI      │
                          │  (React/Vite) |  (chat+mem)  │
                          └───────────────┬──────────────┘
                                          │ REST/WebSocket
                          ┌───────────────▼──────────────┐
                          │      API Gateway (FastAPI)    │
                          └───────────────┬──────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
   ┌──────────▼─────────┐     ┌───────────▼──────────┐     ┌──────────▼─────────┐
   │  Agent Orchestrator │     │   Memory Manager      │     │   Tool Executor     │
   │  (turn loop, prompt │◄───►│  (retrieval, write,   │     │  (code exec, fs,    │
   │  assembly, routing) │     │   scoring, decay)      │     │   shell, git, web)  │
   └──────────┬──────────┘     └───────────┬───────────┘     └──────────┬─────────┘
              │                           │                            │
   ┌──────────▼──────────┐   ┌────────────▼────────────┐    ┌──────────▼─────────┐
   │  LLM Provider Layer  │   │   Storage Layer          │    │   Sandbox (Docker/  │
   │  (Anthropic primary, │   │  - Postgres (structured) │    │   Firecracker/      │
   │   OpenAI-compat      │   │  - Qdrant (vectors)      │    │   subprocess+       │
   │   fallback)          │   │  - Local FS (artifacts)  │    │   resource limits)  │
   └───────────────────────┘   └───────────────────────────┘    └─────────────────────┘

   ┌────────────────────────────────────────────────────────────────────────────────┐
   │  Scheduler (APScheduler / cron)                                                 │
   │  - Reflection/Consolidation job (episodic → semantic/procedural)                │
   │  - Memory decay/pruning job                                                     │
   │  - Codebase re-index watcher                                                    │
   │  - Daily/weekly summary generation                                              │
   └────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Technology Stack (fixed for v1)

| Layer | Choice | Notes |
|---|---|---|
| Backend language | Python 3.11+ | Best ecosystem for LLM tooling, embeddings, agents |
| API framework | FastAPI | Async, typed, OpenAPI docs auto-generated |
| Orchestration | Custom lightweight agent loop (no heavy framework like LangChain) | Full control over memory injection and prompt construction; avoid black-box abstractions for a system whose core value **is** the memory logic |
| Structured DB | PostgreSQL 16 (SQLite acceptable for a true single-machine v1 to reduce setup friction) | Postgres recommended if you may add a second device later |
| ORM | SQLModel (SQLAlchemy + Pydantic) | Typed models shared between API and DB layer |
| Vector DB | Qdrant (self-hosted, Docker) | Fast, filterable metadata search, easy local deploy; Chroma acceptable lighter alternative |
| Embeddings | Pluggable: `voyage-3` (hosted, high quality) default; local `bge-base-en-v1.5` via `sentence-transformers` as privacy-mode fallback | Config flag `EMBEDDING_MODE=hosted|local` |
| LLM provider | Anthropic API (`claude-sonnet-4-6` default; configurable to Opus for heavy reasoning, Haiku for cheap consolidation passes) | Provider-abstraction layer so OpenAI-compatible APIs can be swapped in |
| Scheduler | APScheduler (in-process) for v1 single-user scale | Cron-like jobs, no need for Celery/Redis at this scale |
| Frontend | React + TypeScript + Vite + Tailwind CSS | Fast dev loop, matches frontend-design conventions |
| CLI | Typer (Python) | Rich terminal output, matches backend language |
| Containerization | Docker + Docker Compose | One-command local deployment |
| Code sandbox | `subprocess` with resource/time limits in v1; Docker-in-Docker sandbox container as hardening option | Balance setup complexity vs isolation |
| Secrets | `.env` file (gitignored) + `python-dotenv`; optional OS keychain integration later | Single-user, local — no need for a secrets manager service |
| Auth | Single local access token (bearer) for the web UI/API, no user accounts | A1 |
| Testing | pytest (backend), Vitest + React Testing Library (frontend) | |
| Observability | Structured JSON logging (`structlog`) + local log files; optional simple metrics dashboard (token usage, cost, latency) in v2 | |

## 3. Non-Functional Requirements

### 3.1 Performance
- Chat turn latency (excl. LLM generation time): retrieval + prompt assembly < 500ms p95.
- Vector search over up to 500K memory vectors must return top-k in < 150ms.
- Consolidation job must not block interactive chat (runs as background task/separate worker process).

### 3.2 Scalability
- Designed for **single-user** scale: thousands of sessions, hundreds of thousands of memory items over years of use. Not designed for concurrent multi-user load.

### 3.3 Reliability
- All memory writes are transactional (structured DB write + vector write must both succeed or both roll back — use outbox pattern if needed).
- Nightly automated backup of Postgres + Qdrant snapshot to local disk (and optionally an encrypted off-site copy).
- Agent must degrade gracefully if vector DB is unreachable (fall back to keyword search over structured DB rather than crashing).

### 3.4 Security & Privacy
- All data stored locally by default; nothing leaves the machine except the minimal per-turn payload sent to the LLM/embedding API.
- API keys stored in `.env`, never logged, never included in memory content sent back to the model as literal text.
- Destructive tool actions (file delete, `git push`, `rm`, package uninstall, etc.) require explicit user confirmation via an "approval" step in the orchestrator — never auto-executed.
- Web UI protected by a bearer token; not exposed to the public internet by default (bind to `localhost` / private LAN only).
- Optional at-rest encryption for the Postgres volume (LUKS/OS-level) — documented but not built by the app itself.

### 3.5 Maintainability
- Provider-abstraction interfaces (`LLMProvider`, `EmbeddingProvider`) so models can be swapped via config without code changes.
- Memory schema versioned with migrations (Alembic).
- Clear module boundaries: `orchestrator/`, `memory/`, `tools/`, `providers/`, `api/`, `scheduler/`.

### 3.6 Portability
- Entire system runs via `docker compose up`; only external dependency is API keys for chosen LLM/embedding provider (or fully local mode using a self-hosted open-weight model + local embeddings, documented as an advanced config).

## 4. System Requirements (host machine)

- OS: Linux or macOS (primary targets); Windows via WSL2.
- RAM: 8GB minimum, 16GB+ recommended (more if running local embedding model or local LLM).
- Disk: 20GB+ free for DB/vector storage growth over time.
- Docker + Docker Compose installed.
- Python 3.11+ (for local dev outside Docker).
- Node 20+ (frontend dev).

## 5. Integration Requirements

- **Anthropic API**: API key via env var `ANTHROPIC_API_KEY`.
- **Optional OpenAI-compatible fallback**: env var `OPENAI_API_KEY` + `OPENAI_BASE_URL` for alternative providers.
- **Embeddings provider**: `VOYAGE_API_KEY` if hosted mode chosen.
- **Git**: local `git` binary must be available on PATH for git-aware tools.
- **AI coding tool (e.g., Antigravity/Claude Code)**: this repo should include a `AGENTS.md`/`CLAUDE.md` style instructions file (see Implementation Plan) so any AI coding agent building this app has consistent grounding across sessions.

## 6. Explicit Non-Functional Non-Goals

- No horizontal scaling / load balancing.
- No SSO / enterprise auth.
- No GDPR/compliance tooling (single private user).
- No mobile-optimized UI in v1 (web UI is desktop-first, responsive as a bonus, not a requirement).

## 7. Configuration Summary (`.env` keys)

```
ANTHROPIC_API_KEY=
LLM_MODEL_PRIMARY=claude-sonnet-4-6
LLM_MODEL_LIGHT=claude-haiku-4-5-20251001   # used for consolidation/summarization passes
EMBEDDING_MODE=hosted        # hosted | local
VOYAGE_API_KEY=
DATABASE_URL=postgresql://...   # or sqlite:///./data/agent.db
QDRANT_URL=http://localhost:6333
APP_ACCESS_TOKEN=              # bearer token for web UI/API
SANDBOX_MODE=subprocess        # subprocess | docker
CONFIRM_DESTRUCTIVE_ACTIONS=true
```