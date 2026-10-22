# v2.0 — Transactionally Governed LangGraph Architecture

## Objective

Provide an end-to-end **mock execution** path: Entra-protected API → LangGraph checkpoint → PostgreSQL approval → atomic audit + outbox → tenant-scoped worker → durable audit. Salesforce CRM remains Salesforce-hosted; agent and integration workloads target Azure.

## Guarantees and boundaries

- An approval is consumed exactly once in the database (`UPDATE ... WHERE status='PENDING'`). The approved outbox action and audit event are committed in the same transaction.
- The graph resumes **after** the approval transaction commits. A graph resume failure returns `RECONCILIATION_REQUIRED`; the action stays queued. Graph checkpoint and outbox are **not** in one distributed transaction.
- The worker uses `FOR UPDATE SKIP LOCKED` and an attempt-number fencing check. Its completion and audit event share a transaction. An expired worker cannot mark a newer attempt successful.
- The current worker only **simulates** a ServiceNow incident write. Actual external exactly-once execution is NOT guaranteed by a PostgreSQL outbox alone; production adapters need provider-side idempotency keys or read-before-retry reconciliation.
- Tenant scoping is enforced using PostgreSQL RLS when the runtime role does not own tables or have BYPASSRLS. The tenant value must come from validated Entra claims, not client input. The LangGraph checkpointer uses a tenant-qualified thread identifier but does not itself provide PostgreSQL RLS isolation.
- Audit and outbox use the same database transaction; the LangGraph checkpoint is separate. Operators must reconcile inconsistent graph/outbox state.

## Security hardening before production

Use distinct non-owner migration, API, and worker database roles; force TLS and private networking; enable managed identity/Entra where supported; protect all `/v1` and `/v2` routes at APIM and application; rotate secrets through Key Vault; implement rate limiting and approvals separation of duties; avoid logging customer PII in traces; add Azure PostgreSQL HA and restore drills.

## Integrations

Salesforce/Apex, Jira/Groovy and ServiceNow artifacts remain in the repository. This v2 demonstration does not enable real mutations against those systems. Grafana/Dynatrace dual OTLP export from earlier versions is retained but has not been validated against cloud endpoints in this build.
