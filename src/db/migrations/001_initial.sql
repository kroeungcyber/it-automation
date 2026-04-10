CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY,
    source VARCHAR(20) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    org_role VARCHAR(255) NOT NULL,
    raw_input TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    route VARCHAR(10),
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
