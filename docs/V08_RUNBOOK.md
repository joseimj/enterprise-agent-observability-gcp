# v0.8 — Operator Runbook

## Local lab
```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8000/health
```
The local Compose environment continues using the legacy `governance/schema.sql`. Do **not** run the new Alembic RLS migration against the running legacy governance API until its database access is converted to verified tenant-scoped sessions.

## Validate infrastructure without deploying
```bash
cd infrastructure/azure
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check
terraform validate
terraform plan
```
Review the PostgreSQL SKU and Azure region availability. `terraform apply` provisions a billable database. The private database is not reachable from the existing Container App until VNet integration is implemented.

## Database migration in an isolated development database
```bash
export AUDIT_DATABASE_URL='postgresql+psycopg://migration_admin:REDACTED@localhost:5432/agent_audit'
alembic -c migrations/alembic.ini upgrade head
```
Run this only as a migration role, on a dedicated database. Grant a separate runtime role SELECT/INSERT/UPDATE/DELETE on required tables and USAGE on schemas; never grant BYPASSRLS. Configure `app.tenant_id` inside each transaction using `tenant_session`. Validate that tenant A cannot read or insert tenant B data.

## Tests
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q tests/test_v08_persistence.py
```

## Known incomplete work
Azure Container Apps VNet integration, full LangGraph Postgres checkpointing, legacy governance migration, verified Entra identity, and end-to-end Azure tests are deferred. Do not claim production readiness until these gates pass.
