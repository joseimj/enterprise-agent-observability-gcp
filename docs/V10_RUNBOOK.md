# v1.0 Local Runbook (English)

## Prerequisites
Docker Compose, PostgreSQL 16, an Entra tenant, a registered API app with application roles `Agent.Operator`, `Agent.Approver`, `Agent.Auditor`, and correctly issued access tokens. Configure `ENTRA_TENANT_ID` and `ENTRA_API_AUDIENCE` in `.env` (never commit tokens). For real Azure deployment use the v0.9 Terraform as a starting scaffold; v1 has **not** been deployed to Azure.

## Startup
```bash
cp .env.example .env
# Set ENTRA_TENANT_ID and ENTRA_API_AUDIENCE in .env
docker compose -f docker-compose.yml -f docker-compose.v1.yml up --build -d
# Existing PostgreSQL volumes do not rerun init scripts:
docker compose -f docker-compose.yml -f docker-compose.v1.yml exec -T postgres psql -U agent -d agent_audit < governance/v1_schema.sql
# Initialize LangGraph saver (if not initialized earlier):
docker compose -f docker-compose.yml -f docker-compose.v1.yml exec api python scripts/init_checkpointer.py
```

## API
```bash
export TOKEN='<Entra API access token>'
curl -X POST localhost:8000/v1/runs -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"account_id":"ACME"}'
# Copy run_id from response, use token with Agent.Approver role:
curl -X POST localhost:8000/v1/runs/$RUN_ID/decision \
  -H "Authorization: Bearer $APPROVER_TOKEN" -H 'Content-Type: application/json' \
  -d '{"approved":true}'
# Use Agent.Auditor token:
curl localhost:8000/v1/runs/$RUN_ID -H "Authorization: Bearer $AUDITOR_TOKEN"
```

## Validation checklist
1. Verify 401 for missing/invalid token, 403 for missing role.
2. Verify interrupt state before approval and simulated action after approval.
3. Restart API container and confirm checkpoint and audit timeline persist.
4. Reject and confirm no external writes.
5. Verify different Entra tenant token is rejected.
6. Run concurrent approvals: **known limitation**; no guarantee of single-decision semantics yet.
7. Configure non-owner DB role and validate RLS with real PostgreSQL integration tests.

## Failure handling
If schema does not exist on an existing volume, apply the SQL manually as above. If checkpointer tables are missing, run the init script. If JWT verification fails, check issuer, audience, app role assignments and tenant-specific signing keys. Never bypass signature checks for convenience.
