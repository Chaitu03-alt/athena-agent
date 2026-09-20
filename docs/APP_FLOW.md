# App Flow Document
## Personal Adaptive AI Agent

Describes every major user-facing and background flow in enough sequential detail that a coding agent can implement each without design ambiguity.

---

## 1. First-Time Setup Flow

1. User runs `docker compose up` after copying `.env.example` → `.env` and filling in API keys.
2. On first boot, backend runs DB migrations (Alembic) and creates Qdrant collections (see Backend Schema doc).
3. Backend seeds an empty procedural-memory profile ("no preferences learned yet") and a default system prompt template.
4. User opens web UI at `http://localhost:PORT`, enters the bearer token (shown in terminal logs on first boot).
5. Onboarding screen asks (optional, skippable): name, primary project directories to index, preferred code language(s)/frameworks, communication style preference (concise vs. detailed). These seed initial procedural memory as "explicit user-stated preferences" (highest confidence tier).
6. User lands on empty chat screen, ready to use.

## 2. Standard Chat Turn Flow (core loop)

1. User sends a message (CLI or web UI) → API Gateway → Agent Orchestrator.
2. **Pre-processing**: Orchestrator extracts lightweight signals from the message (topic keywords, referenced project/file names, explicit commands like "remember that...").
3. **Memory Retrieval** (parallel):
   a. Semantic search (vector) over episodic + semantic memory using the message embedding, filtered by recency/importance thresholds.
   b. Keyword/metadata search over structured tables (e.g., exact project name match).
   c. Procedural memory profile always loaded (small, always-on context — not retrieved per query).
   d. Results merged, deduplicated, ranked by combined score `= α·semantic_sim + β·recency + γ·importance`, top-K (default K=8) selected.
4. **Prompt Assembly**: System prompt = base persona + procedural memory profile + retrieved memory snippets (labeled with source/date) + relevant codebase RAG chunks (if project context detected) + conversation history (recent turns, windowed).
5. **LLM Call**: sent to primary model via provider layer; streamed back to UI/CLI token-by-token.
6. **Tool-Use Sub-loop** (if the model requests a tool call): see Section 4.
7. **Response rendered** to user.
8. **Post-turn logging**: the full turn (user msg, assistled response, retrieved memory IDs used, tool calls made) is written to episodic memory with an initial importance score (heuristic: contains a decision/preference/correction → high; small talk → low).
9. Turn added to session history buffer for the current session.

## 3. Feedback Flow

**Explicit feedback:**
1. User clicks 👍/👎 on a response, or types a correction ("actually, I prefer X over Y").
2. Orchestrator tags the associated episodic memory entry with the feedback.
3. If 👎 or a correction: entry is queued for **priority consolidation** (doesn't wait for the nightly batch) — a lightweight job immediately proposes a procedural-memory update.
4. Proposed update appears in an **Approval Queue** in the web UI ("Agent wants to learn: 'Prefer pytest over unittest' — Approve / Reject / Edit").
5. On approval, procedural memory table updated with new/revised rule, versioned (old rule marked superseded, not deleted).

**Implicit feedback:**
1. When a tool-generated code suggestion is later edited by the user (detected via file diff after suggestion) or discarded, this is logged as an implicit negative signal linked to that episodic entry.
2. Implicit signals feed into importance scoring but require higher confidence/frequency (≥2 occurrences) before triggering an approval-queue proposal (to avoid noisy over-adaptation from one-off edits).

## 4. Tool-Use Flow

1. Model response includes a structured tool-call request (function-calling format).
2. Orchestrator validates the request against the tool's schema.
3. **Risk classification**: each tool call classified as `safe` (read-only: file read, search, code lint) or `destructive` (file write/delete, shell exec, git push, package install/uninstall).
4. If `destructive` and `CONFIRM_DESTRUCTIVE_ACTIONS=true` (default): orchestrator pauses, surfaces a confirmation prompt to the user with the exact command/diff to be executed. Execution proceeds only after explicit "confirm."
5. If `safe`: executes immediately.
6. Tool Executor runs the action (in sandbox per config), captures stdout/stderr/result, returns it to the model as a tool result message.
7. Model incorporates the result and continues generating (may chain multiple tool calls before final response).
8. Every tool call + result is logged to episodic memory (with a `tool_call` type flag) for future retrieval ("last time I asked to deploy, what command did we use?").

## 5. Reflection / Consolidation Flow (background)

1. Scheduler triggers nightly (configurable) or on-demand ("reflect now" button/CLI command).
2. Consolidation job pulls all episodic entries since last run that are:
   - Not yet consolidated, AND
   - (importance score ≥ threshold OR tagged with explicit/implicit feedback OR marked "decision-like" by heuristic).
3. Light model (`LLM_MODEL_LIGHT`) is prompted, in batches, to:
   a. Propose new semantic-memory facts, OR
   b. Propose new/updated procedural-memory rules, OR
   c. Flag contradictions with existing semantic/procedural memory.
4. Proposals with confidence above an auto-approve threshold (e.g., purely additive, non-conflicting facts) are written directly.
5. Proposals that conflict with existing memory, or fall below the auto-approve threshold, go to the **Approval Queue** for manual review next time you open the UI.
6. Processed episodic entries marked `consolidated=true`; low-importance consolidated entries older than the retention window (default 90 days) become eligible for pruning (Section 6).
7. Job writes a short run summary (what was learned) to a `system` memory channel, visible in the UI under "What I learned recently."

## 6. Memory Decay / Pruning Flow

1. Runs after consolidation, or on its own schedule.
2. Episodic entries eligible for pruning if: `consolidated=true` AND `pinned=false` AND `age > retention_window` AND `importance < decay_threshold`.
3. Eligible entries are soft-deleted (moved to a compressed archive table/cold storage, not permanently destroyed) — recoverable for 30 days, then hard-deleted.
4. Pinned memory (`pinned=true`, user-marked "never forget") is always exempt.

## 7. Codebase Indexing Flow

1. User registers a project directory (CLI: `agent index add ./path` or via UI settings).
2. Indexer walks the directory (respecting `.gitignore`), chunks files (code-aware chunking: function/class boundaries where possible), embeds chunks, stores in a dedicated Qdrant collection tagged with `project_id`.
3. A filesystem watcher (or periodic diff against last indexed git commit) detects changes and re-embeds only changed files.
4. During chat, if the user's message references a known project (by name or by working directory context from CLI), RAG retrieval over that project's collection is added to the prompt alongside general memory retrieval.

## 8. Daily/Weekly Summary Flow

1. Scheduled job (e.g., end of day) gathers the day's episodic entries + consolidation output.
2. Light model generates a structured summary: what was worked on, decisions made, open questions/TODOs, notable corrections learned.
3. Summary stored as a special episodic entry (`type=daily_summary`) and surfaced at the top of the web UI / via `agent summary today` CLI command.

## 9. Error & Edge-Case Flows

- **LLM API failure/timeout**: retry with exponential backoff (max 3), then surface a clear error to the user; turn is not logged as a false episodic memory.
- **Vector DB unreachable**: fall back to structured-DB keyword search only; log a warning; UI shows a subtle "memory search degraded" indicator.
- **Conflicting procedural rules**: consolidation flags the conflict explicitly rather than silently overwriting; requires manual resolution in Approval Queue.
- **Destructive tool call rejected by user**: logged as a rejected action (useful signal — "agent shouldn't have suggested this").
- **Empty/cold-start memory** (first weeks of use): retrieval simply returns fewer/no results; orchestrator does not fabricate context.