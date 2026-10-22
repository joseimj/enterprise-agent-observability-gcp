CREATE TABLE IF NOT EXISTS audit_events (
  event_id UUID PRIMARY KEY, run_id UUID NOT NULL, tenant_id TEXT NOT NULL,
  actor_id TEXT NOT NULL, event_type TEXT NOT NULL, tool_name TEXT,
  action_id UUID, status TEXT NOT NULL, trace_id TEXT,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_run ON audit_events(tenant_id, run_id, created_at);
CREATE TABLE IF NOT EXISTS action_requests (
  action_id UUID PRIMARY KEY, run_id UUID NOT NULL, tenant_id TEXT NOT NULL,
  actor_id TEXT NOT NULL, tool_name TEXT NOT NULL,
  arguments JSONB NOT NULL, arguments_hash TEXT NOT NULL,
  idempotency_key TEXT NOT NULL, status TEXT NOT NULL,
  approved_by TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, idempotency_key)
);
