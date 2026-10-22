-- LOCAL LAB ONLY. Use a dedicated owner and least-privilege runtime login.
-- Executed by PostgreSQL initial bootstrap user. Not a production credential model.
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='agent_runtime_lab') THEN
  CREATE ROLE agent_runtime_lab LOGIN PASSWORD 'runtime-local-only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $$;
GRANT CONNECT ON DATABASE agent_audit TO agent_runtime_lab;
GRANT USAGE ON SCHEMA public TO agent_runtime_lab;
GRANT SELECT, INSERT, UPDATE ON v11_approvals,v11_outbox,v1_audit_events TO agent_runtime_lab;
-- Non-owner runtime grants should never include BYPASSRLS.

-- Checkpointer owns ONLY a dedicated schema. This does not provide RLS on
-- checkpoint rows; use per-business-tenant database isolation where required.
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='agent_checkpoint_lab') THEN
  CREATE ROLE agent_checkpoint_lab LOGIN PASSWORD 'checkpoint-local-only'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS agent_checkpoints AUTHORIZATION agent_checkpoint_lab;
GRANT CONNECT ON DATABASE agent_audit TO agent_checkpoint_lab;
GRANT USAGE, CREATE ON SCHEMA agent_checkpoints TO agent_checkpoint_lab;
