-- src/db/migrations/002_guardrail_audit.sql
CREATE TABLE IF NOT EXISTS guardrail_audit (
    id              UUID PRIMARY KEY,
    prev_id         UUID REFERENCES guardrail_audit(id),
    action_plan_id  UUID NOT NULL,
    task_id         UUID NOT NULL,
    event_type      VARCHAR(30) NOT NULL,
    risk_tier       VARCHAR(10),
    actor           VARCHAR(255) NOT NULL DEFAULT 'system',
    outcome         VARCHAR(20),
    detail          JSONB NOT NULL DEFAULT '{}',
    content_hash    VARCHAR(64) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guardrail_audit_action_plan ON guardrail_audit(action_plan_id);
CREATE INDEX IF NOT EXISTS idx_guardrail_audit_created ON guardrail_audit(created_at DESC);

-- App user has INSERT only — enforce append-only at DB level
-- Run as superuser: REVOKE UPDATE, DELETE ON guardrail_audit FROM itauto;
