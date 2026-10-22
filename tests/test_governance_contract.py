import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_governance_source_compiles():
    for file in ('app/governance.py','app/governance_api.py'):
        ast.parse((ROOT/file).read_text())

def test_policy_is_allowlist_and_denies_self_approval():
    source=(ROOT/'app/governance.py').read_text()
    assert "ALLOWED_TOOLS={'jira.create_followup', 'servicenow.create_incident'}" in source
    assert "Self-approval forbidden" in source
    assert "Action is not approved" in source

def test_audit_schema_has_tenant_and_idempotency():
    ddl=(ROOT/'governance/schema.sql').read_text()
    assert 'UNIQUE(tenant_id, idempotency_key)' in ddl
    assert 'tenant_id TEXT NOT NULL' in ddl
    assert 'trace_id TEXT' in ddl
