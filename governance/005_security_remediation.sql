-- Applied after 001/002/003 schemas and 004 runtime/checkpointer roles.
-- FAIL CLOSED: unconfirmed external writes are quarantined as UNCERTAIN.
ALTER TABLE v11_outbox DROP CONSTRAINT IF EXISTS v11_outbox_status_check;
ALTER TABLE v11_outbox ADD CONSTRAINT v11_outbox_status_check
    CHECK (status IN ('PENDING','IN_PROGRESS','SUCCEEDED','FAILED','UNCERTAIN'));
-- Keep policies enforced even when table owners access the schema.
ALTER TABLE v11_approvals FORCE ROW LEVEL SECURITY;
ALTER TABLE v11_outbox FORCE ROW LEVEL SECURITY;
ALTER TABLE v1_audit_events FORCE ROW LEVEL SECURITY;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- Credentials in 004 are for an isolated local lab only, never real deployment.
