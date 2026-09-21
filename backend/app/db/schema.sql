-- schema.sql
-- SQLite DDL for Athena Agent (Zero-Infra Architecture)

CREATE TABLE IF NOT EXISTS allowed_users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS soul_prompts (
    id TEXT PRIMARY KEY,
    prompt_text TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Partial unique index to ensure only one active soul prompt exists at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_soul_prompts_active 
ON soul_prompts(is_active) 
WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS user_kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL, -- JSON encoded
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    is_summary INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_session 
ON checkpoints(session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS tool_execution_log (
    id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL,
    result_json TEXT,
    status TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dropped_messages (
    id TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cron_jobs_meta (
    job_name TEXT PRIMARY KEY,
    last_run_at DATETIME,
    status TEXT,
    next_run_at DATETIME
);

CREATE TABLE IF NOT EXISTS telemetry_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
