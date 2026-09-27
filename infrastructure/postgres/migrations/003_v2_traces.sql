-- PricePilot V2 migration: AI agent tool traces.
-- Append-only per-turn planner traces for the admin surface (intent, plan,
-- backend, tool calls, step trail / reasoning, latency, errors).
-- Safe to run on V1.2. Fresh installs get this via init.sql + create_all.

CREATE TABLE IF NOT EXISTS conversation_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(64) NOT NULL,
    user_id UUID,
    turn_index INTEGER NOT NULL DEFAULT 1,
    intent VARCHAR(32),
    backend VARCHAR(32),
    requires JSONB NOT NULL DEFAULT '[]',
    tool_calls JSONB NOT NULL DEFAULT '[]',
    steps JSONB NOT NULL DEFAULT '[]',
    reply TEXT,
    error TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_conversation_traces_conv ON conversation_traces (conversation_id, turn_index);
CREATE INDEX IF NOT EXISTS ix_conversation_traces_created ON conversation_traces (created_at);