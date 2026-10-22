# v0.8 — Azure PostgreSQL Persistence Architecture

## Scope
This release extends v0.7, preserving the FastAPI/LangGraph risk workflow, Salesforce Apex, Jira Groovy, ServiceNow JavaScript, and Grafana/Dynatrace telemetry. It introduces a private Azure Database for PostgreSQL Flexible Server Terraform module, SQLAlchemy models, Alembic migrations, and a transaction-scoped tenant context helper.

## Ownership boundaries
- **PostgreSQL**: operational audit, action approvals, agent-run metadata, integration references, and trace correlation identifiers.
- **LangGraph checkpointer**: actual graph state persistence is **not wired** in this release. `checkpoint_metadata` is metadata only; use a supported PostgresSaver implementation in a subsequent iteration.
- **Tempo/Loki/Dynatrace**: high-volume traces and logs; PostgreSQL must not become a general-purpose telemetry sink.
- **Salesforce, Jira, ServiceNow**: systems of record; only approved actions may write to these systems.

## Security model
All tenant-aware models carry `tenant_id`. The migration enables and forces PostgreSQL RLS on new tables and legacy public governance tables if present. The application uses `set_config(..., true)` inside a transaction. **The database runtime role must not be the table owner, a superuser, or hold BYPASSRLS**; an administrator role runs migrations. A verified identity provider must supply tenant context; do not trust a caller-supplied header.

## Migration compatibility and limitations
The original `governance/schema.sql` is still used by Docker Compose for local initialization. Existing v0.7 governance functions are not yet migrated to the new SQLAlchemy session helper, so the new RLS policies can block them when deployed against the migrated database. Do not deploy this migration to the existing governance service without first converting those queries to tenant-scoped sessions and assigning separate migration/runtime roles. This is an explicit integration gate.

## Network topology
Terraform provisions a private VNet, PostgreSQL delegated subnet and private DNS zone. **Container Apps VNet integration is not yet configured**, so the existing Azure Container App cannot reach this private server. Provision compatible Container Apps environment networking and DNS before deploying application connectivity.

## Additional production gates
Use Microsoft Entra authentication or a rotated, least-privilege database credential. Configure HA, diagnostic settings, backup/restore drills, PgBouncer or pooling, and schema migration CI. Treat `random_password` as sensitive Terraform state even though it is also stored in Key Vault; use encrypted remote state with limited access. The example does not configure HA or restore testing.
