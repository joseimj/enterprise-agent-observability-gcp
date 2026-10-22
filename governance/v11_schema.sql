-- Apply with a migration role; application/worker roles must not own these tables.
CREATE TABLE IF NOT EXISTS v11_approvals (
 tenant_id text NOT NULL, run_id uuid NOT NULL, status text NOT NULL DEFAULT 'PENDING',
 decided_by text, decided_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,run_id), CHECK(status IN ('PENDING','APPROVED','DENIED'))
);
CREATE TABLE IF NOT EXISTS v11_outbox (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, run_id uuid NOT NULL,
 action_key text NOT NULL, tool text NOT NULL, payload jsonb NOT NULL,
 status text NOT NULL DEFAULT 'PENDING', attempts integer NOT NULL DEFAULT 0,
 leased_until timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz, UNIQUE(tenant_id,action_key),
 CHECK(status IN ('PENDING','IN_PROGRESS','SUCCEEDED','FAILED'))
);
CREATE INDEX IF NOT EXISTS v11_outbox_ready ON v11_outbox(status,leased_until,created_at);
DO $$ BEGIN
 FOR t IN SELECT unnest(ARRAY['v11_approvals','v11_outbox']) LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('DROP POLICY IF EXISTS tenant_policy ON %I',t);
  EXECUTE format('CREATE POLICY tenant_policy ON %I USING (tenant_id = current_setting(''app.tenant_id'',true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'',true))',t);
 END LOOP;
END $$;
-- Worker must set app.tenant_id from a trusted tenant registry, not an untrusted request.
-- Avoid using owner/BYPASSRLS for application or worker access.
