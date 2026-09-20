# UI/UX Design Brief
## Personal Adaptive AI Agent

This is a **personal power-tool**, not a consumer product — prioritize information density, keyboard-driven speed, and transparency into the memory system over marketing polish. Think "developer dashboard" aesthetic (closer to Linear/Raycast/a well-designed terminal companion) rather than a generic chatbot skin.

---

## 1. Design Principles

1. **Transparency over magic.** Every place the agent uses memory, show *what* it retrieved and *why* (collapsible "context used" panel per response). Never hide the reasoning behind adaptation.
2. **Fast, keyboard-first.** Cmd/Ctrl+K command palette for navigation, `/` for slash commands in chat (e.g., `/remember`, `/pin`, `/reflect`, `/index`).
3. **Low chrome, high content.** Minimal decoration; the chat and memory content are the product.
4. **Confirm before destructive.** Any irreversible action gets a distinct, hard-to-miss confirmation UI (not a generic browser `confirm()`).
5. **Dark-mode-first** (primary use context: coding at a desk), with light mode supported.

## 2. Screens / Views

### 2.1 Chat View (primary/default screen)
- Left sidebar: session list (searchable, grouped by project/date).
- Center: message thread. User messages right-aligned/plain; agent messages left-aligned with markdown + syntax-highlighted code blocks (copy button per block).
- Each agent message has a small **"🧠 N memories used"** chip — click to expand an inline panel showing exactly which episodic/semantic/procedural items were retrieved and their scores.
- Tool-call messages rendered distinctly (monospace, muted background) showing command run + result, collapsible if long.
- Destructive-action confirmations render as an inline card with a red-accented border, diff/command preview, and explicit **Confirm / Cancel** buttons (never auto-timeout).
- Input box: multi-line, supports `/` slash commands with autocomplete, file/project `@mention` autocomplete for RAG scoping.
- Top bar: current project context indicator (which repo, if any, is active), model indicator, token/cost usage for the session (small, unobtrusive).

### 2.2 Memory Browser
- Three tabs: **Episodic**, **Semantic**, **Procedural**.
- Table/list view: content, source session (linkable), created date, importance score, pinned status, consolidated status.
- Search bar (semantic + keyword toggle) and filters (date range, project, importance, tag).
- Row actions: Pin, Edit, Delete, "Why was this stored?" (shows originating turn).
- Procedural tab specifically shows rules as human-readable statements grouped by category (Coding Style, Communication Style, Workflow, Tooling), each with a confidence badge and version history (see old superseded versions).

### 2.3 Approval Queue
- Card-based list of pending consolidation/feedback-derived proposals.
- Each card: proposed new/changed memory statement, the evidence (linked episodic entries), and **Approve / Edit & Approve / Reject** actions.
- Conflict proposals visually distinct (amber border) and show the old vs. new statement side-by-side.

### 2.4 Projects / Indexing Settings
- List of registered project directories, index status (last indexed time, file count, size), re-index button, remove button.
- Toggle: auto-watch for changes on/off per project.

### 2.5 Daily/Weekly Summary View
- Chronological feed of generated summaries; each expandable into the underlying episodic entries.

### 2.6 Settings
- Model selection (primary/light), API keys status (masked, "connected" indicator, not editable in UI — points to `.env`), memory retention window slider, destructive-action confirmation toggle, embedding mode toggle, export/backup button.

## 3. Core Components (build as a shared component library)

- `ChatMessage` (user/assistant/tool variants)
- `MemoryChip` (expandable retrieval summary)
- `ConfirmationCard` (destructive action gate)
- `MemoryTable` / `MemoryRow`
- `ApprovalCard`
- `CommandPalette` (Cmd/Ctrl+K)
- `SlashCommandMenu`
- `ProjectBadge`
- `ImportanceBadge` / `ConfidenceBadge`
- `StreamingText` (token-by-token render with cursor)

## 4. Interaction Patterns

- Streaming responses render incrementally; a stop-generation control is always visible during streaming.
- Slash commands: `/remember <text>` (force-write to semantic memory, high confidence), `/pin`, `/forget <query>`, `/reflect`, `/index <path>`, `/summary`.
- `@project-name` or `@file-path` mention triggers scoped RAG retrieval for that turn only.
- Optimistic UI for feedback (👍/👎) — instant visual response, backend sync in background.

## 5. Visual Style Direction

- Typography: a clean monospace for code/tool output (e.g., JetBrains Mono / IBM Plex Mono), a neutral sans-serif for UI/prose (e.g., Inter).
- Color: neutral dark background (near-black, not pure black), single accent color for interactive elements, amber for warnings/conflicts, red reserved strictly for destructive-confirmation UI, green for success/approved.
- Avoid gradients/skeuomorphism; flat, high-contrast, information-dense.
- Generous use of subtle borders/dividers over heavy shadows to separate dense content blocks.

## 6. Accessibility

- Full keyboard navigability (tab order, focus rings visible).
- Sufficient color contrast (WCAG AA) even in dark mode.
- All icon-only buttons have accessible labels/tooltips.

## 7. Responsiveness

- Desktop-first (primary use is at a desk while coding). Web UI should remain usable on a laptop screen down to ~1280px width; tablet/mobile layout is a nice-to-have, not a requirement (per TRD 3.6/PRD non-goals).