# v2.0 Local Runbook

## Prerequisites

Docker Compose, Entra application registration and valid tokens with `Agent.Operator`, `Agent.Approver`, `Agent.Auditor` roles. This lab uses local PostgreSQL credentials; never expose it to the public internet.

```bash
cp .env.example .env
# Set ENTRA_TENANT_ID and ENTRA_API_AUDIENCE in .env
docker compose -f docker-compose.yml -f docker-compose.v2.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.v2.yml exec api python scripts/init_checkpointer.py
```

**Existing volumes:** `docker-entrypoint-initdb.d` SQL runs only for an empty PostgreSQL data directory. Apply `governance/v1_schema.sql` and `governance/v11_schema.sql` with a migration account if upgrading an existing database; do not delete volumes containing valuable data.

## API walkthrough

```bash
export TOKEN='<Entra bearer token>'
curl -sS -X POST http://localhost:8000/v2/runs \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"account_id":"ACME"}'
# Save the run_id returned above
curl -sS -X POST "http://localhost:8000/v2/runs/$RUN_ID/decision" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"approved":true}'
curl -sS "http://localhost:8000/v2/runs/$RUN_ID" -H "Authorization: Bearer $TOKEN"
```

Approver and Auditor roles are required for the corresponding endpoints. Run the mock worker in the API container with a tenant ID from trusted deployment configuration:

```bash
docker compose -f docker-compose.yml -f docker-compose.v2.yml exec api \
  python -m app.v2_worker TRUSTED_TENANT_ID
```

## Verification and limitations

```bash
python -m compileall -q app
python -m pytest -q tests/test_v2_contracts.py
```

These are offline contract tests, **not** PostgreSQL concurrency, Entra, Azure deployment or actual ServiceNow integration tests. Validate the full workflow and RLS against a non-owner database role before production.
