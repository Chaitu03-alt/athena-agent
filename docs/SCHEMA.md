# Backend Schema Document
## Personal Adaptive AI Agent

Covers the structured (Postgres/SQLite) schema, the vector DB (Qdrant) collection design, and the REST/WebSocket API surface. This is the contract an AI coding agent should implement against exactly.

---

## 1. Structured Database Schema (Postgres, via SQLModel/Alembic)

### 1.1 `sessions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| title | text | auto-generated from first message, editable |
| project_id | UUID FK → projects.id, nullable | active project context, if any |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### 1.2 `messages`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| session_id | UUID FK → sessions.id | |
| role | enum(`user`,`assistant`,`tool`,`system`) | |
| content | text | markdown/plain |
| tool_call_json | jsonb, nullable | structured tool call/result if role=tool |
| created_at | timestamptz | |
| token_count | int, nullable | for cost tracking |

### 1.3 `memory_episodic`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| session_id | UUID FK → sessions.id | |
| message_id | UUID FK → messages.id, nullable | source message, if applicable |
| content | text | the raw episodic content (summarized turn or event) |
| embedding_id | text | pointer to vector in Qdrant (`episodic` collection point id) |
| entry_type | enum(`turn`,`tool_call`,`decision`,`correction`,`daily_summary`) | |
| importance_score | float | 0.0–1.0, computed heuristic + optional LLM judgment |
| feedback | enum(`none`,`positive`,`negative`,`corrected`), default `none` | |
| pinned | bool, default false | |
| consolidated | bool, default false | |
| project_id | UUID FK → projects.id, nullable | |
| tags | text[] | keyword tags extracted at write time |
| created_at | timestamptz | |
| archived_at | timestamptz, nullable | soft-delete/pruning marker |

### 1.4 `memory_semantic`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| statement | text | e.g., "User's project X uses FastAPI + Postgres" |
| embedding_id | text | pointer to vector in Qdrant (`semantic` collection) |
| confidence | float | 0.0–1.0 |
| source_episodic_ids | UUID[] | provenance — which episodic entries led to this |
| category | text, nullable | e.g., "project_fact", "personal_fact", "general_knowledge" |
| superseded_by | UUID FK → memory_semantic.id, nullable | version chain |
| pinned | bool, default false | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### 1.5 `memory_procedural`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| rule_statement | text | e.g., "Prefer pytest over unittest for new test code" |
| category | enum(`coding_style`,`communication_style`,`workflow`,`tooling`,`other`) | |
| confidence | float | |
| source | enum(`explicit_user`,`implicit_correction`,`consolidation_inference`) | |
| source_episodic_ids | UUID[] | |
| superseded_by | UUID FK → memory_procedural.id, nullable | |
| active | bool, default true | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### 1.6 `approval_queue`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| proposal_type | enum(`semantic_add`,`semantic_update`,`procedural_add`,`procedural_update`,`conflict`) | |
| payload_json | jsonb | proposed content, diff vs. existing if update/conflict |
| status | enum(`pending`,`approved`,`rejected`,`edited_approved`) | |
| created_at | timestamptz | |
| resolved_at | timestamptz, nullable | |

### 1.7 `projects`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | text | |
| path | text | absolute local path |
| last_indexed_at | timestamptz, nullable | |
| watch_enabled | bool, default true | |
| file_count | int, nullable | |
| created_at | timestamptz | |

### 1.8 `tool_calls_log`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| message_id | UUID FK → messages.id | |
| tool_name | text | |
| args_json | jsonb | |
| risk_level | enum(`safe`,`destructive`) | |
| confirmed | bool, nullable | null if not applicable (safe tools) |
| result_json | jsonb, nullable | |
| status | enum(`success`,`error`,`rejected`) | |
| created_at | timestamptz | |

### 1.9 `feedback_events`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| episodic_id | UUID FK → memory_episodic.id | |
| feedback_type | enum(`thumbs_up`,`thumbs_down`,`explicit_correction`,`implicit_edit`) | |
| detail | text, nullable | free-text correction if provided |
| created_at | timestamptz | |

**Indexes**: btree on all FKs; GIN index on `tags` (episodic) and `payload_json` (approval_queue); btree on `created_at` columns for time-window queries; partial index on `memory_episodic (consolidated, pinned, archived_at)` to speed pruning-eligibility scans.

## 2. Vector Database Schema (Qdrant)

### Collection: `episodic_vectors`
- Vector dim: matches embedding model (e.g., 1024 for `voyage-3`, 768 for local `bge-base`).
- Payload fields (mirrors relevant structured columns for filtering without a join): `episodic_id`, `project_id`, `entry_type`, `importance_score`, `pinned`, `created_at` (epoch).

### Collection: `semantic_vectors`
- Payload: `semantic_id`, `category`, `confidence`, `pinned`.

### Collection: `project_code_{project_id}` (one per registered project)
- Payload: `file_path`, `chunk_type` (function/class/module/doc), `start_line`, `end_line`, `git_commit_hash` at index time.

**Retrieval query pattern** (used by Memory Manager): vector similarity search with payload filters (e.g., `project_id = X`, `pinned = true OR importance_score > 0.4`), combined client-side with recency/importance re-ranking as described in the App Flow doc §2.3.

## 3. API Surface (REST, FastAPI — representative, not exhaustive)

### Chat
- `POST /api/sessions` — create session
- `GET /api/sessions` — list sessions
- `POST /api/sessions/{id}/messages` — send message (returns streamed response via SSE/WebSocket `GET /ws/sessions/{id}`)
- `GET /api/sessions/{id}/messages` — history

### Memory
- `GET /api/memory/episodic?query=&project_id=&tags=&from=&to=`
- `GET /api/memory/semantic?query=&category=`
- `GET /api/memory/procedural?category=&active=`
- `PATCH /api/memory/{type}/{id}` — edit content
- `POST /api/memory/{type}/{id}/pin`
- `DELETE /api/memory/{type}/{id}` — soft delete

### Approval Queue
- `GET /api/approvals?status=pending`
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject`
- `PATCH /api/approvals/{id}` — edit then approve

### Projects / Indexing
- `POST /api/projects` — register `{name, path}`
- `POST /api/projects/{id}/reindex`
- `DELETE /api/projects/{id}`

### System
- `POST /api/system/reflect` — trigger consolidation now
- `GET /api/system/summary/today`
- `GET /api/system/health` — DB/vector DB/LLM connectivity check
- `GET /api/system/usage` — token/cost stats

**Auth**: all endpoints require `Authorization: Bearer <APP_ACCESS_TOKEN>` header (A1/local single-user — simple static token, not OAuth).

## 4. Data Retention & Lifecycle Summary

| Data | Retention | Deletion |
|---|---|---|
| Episodic (unconsolidated) | Until consolidated | N/A |
| Episodic (consolidated, unpinned) | 90 days default (configurable), then archived | Soft-delete → hard-delete after 30-day recovery window |
| Episodic (pinned) | Forever | Manual only |
| Semantic / Procedural | Forever (versioned, superseded not deleted) | Manual only |
| Approval queue (resolved) | 180 days | Auto-purge |
| tool_calls_log | 1 year | Auto-purge (audit trail) |