# v1.0 Architecture and Threat Model

## Scope
The v1 API connects a checkpointed LangGraph customer-risk flow, Entra access-token validation, and a PostgreSQL audit table. It uses deterministic evidence fixtures and **never writes to external SaaS**. Existing Salesforce Apex, Jira Groovy and ServiceNow examples remain reference integrations. The existing `/risk/analyze` endpoint is still the v0.9 demonstration and is not governed by `/v1`.

## Authentication
Validate a tenant-specific Entra v2 issuer, JWT signature from the tenant OIDC JWKS, `aud`, `exp`, `iat`, `tid`, and `oid`. Require app roles `Agent.Operator`, `Agent.Approver`, `Agent.Auditor`. The issuer's directory tenant is the demo isolation boundary; a real SaaS with multiple business tenants must validate and map an independently authorized organization claim or membership. Never infer tenant identity from request headers.

## Execution
`POST /v1/runs` creates a run and checkpoints at LangGraph `interrupt`. `POST /v1/runs/{id}/decision` records a human decision and resumes via `Command(resume=...)`. `GET /v1/runs/{id}` reconstructs state and tenant-filtered audit events. Checkpoints and audit events are separate tables and transactions; this is **not** atomic end-to-end execution.

## Security gaps to close before production
- Approval idempotency and compare-and-swap claim to prevent concurrent decisions.
- Transactional outbox, dedicated dispatcher, per-tool idempotency keys and reconciliation before enabling external writes.
- Audit append-only grants, retention policy, tamper-evidence, partitioning and DB permissions.
- Separate DB roles; runtime must not own audit tables or have BYPASSRLS.
- Strict database TLS, Entra PostgreSQL auth, managed identity and private endpoint/VNet routing.
- Verify caller authorization for each account and tool, not only app-level role.
- Real Salesforce OAuth/Apex, Jira/Groovy and ServiceNow ACL/Scripted REST integration testing.
- Trace context propagation across services and OTel dual-export deployment in Azure.
- Do not log raw JWTs, customer PII, prompts, or secrets.

## RLS
`governance/v1_schema.sql` uses `FORCE ROW LEVEL SECURITY`; the API sets `app.tenant_id` transaction-locally before reads and writes. The default local Postgres superuser-style owner configuration is **not a production RLS security test**.
