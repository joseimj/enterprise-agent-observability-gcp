"""Initial tenant-aware schemas and audit governance tables.

Revision ID: 0001_tenant_schemas
Revises:
"""
from alembic import op
from app.persistence.models import Base
revision = "0001_tenant_schemas"
down_revision = None
branch_labels = None
depends_on = None
SCHEMAS = ("agent_runtime", "governance", "audit", "integration", "observability")

def upgrade():
    for name in SCHEMAS: op.execute(f'CREATE SCHEMA IF NOT EXISTS {name}')
    Base.metadata.create_all(bind=op.get_bind())
    # Legacy v0.4 governance tables remain in public for compatibility.
    for table in ("agent_runtime.agent_runs", "agent_runtime.checkpoint_metadata", "integration.external_references", "observability.trace_links", "public.audit_events", "public.action_requests"):
        op.execute(f'ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE IF EXISTS {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"""DO $$ BEGIN
          IF to_regclass('{table}') IS NOT NULL THEN
            EXECUTE 'CREATE POLICY tenant_isolation ON {table} USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))';
          END IF;
        EXCEPTION WHEN duplicate_object THEN NULL; END $$""")

def downgrade():
    # Deliberately non-destructive: audit and agent state must not be silently erased.
    raise RuntimeError("Destructive downgrade prohibited for governance data")
