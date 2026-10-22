# Architecture Decision Record — Governance and Audit (v0.4)

## Scope
The existing v0.3 customer-risk workflow remains intact. v0.4 adds a **separate** governance API and PostgreSQL audit store. The sample action is `jira.create_followup`, but execution is **mocked**; no real Jira ticket is created.

## Trust boundaries
- FastAPI accepts demo identity headers (`X-Tenant-Id`, `X-Actor-Id`, `X-Role`). These headers are **not authentication**. Only run behind localhost / a trusted development network.
- Production requires OIDC/JWT verification at a trusted gateway, policy enforcement based on verified claims, and service-to-service authentication.
- Every audit read and action mutation is scoped by `tenant_id`; production also needs PostgreSQL row-level security, least-privilege roles, and tenant isolation testing.
- Approval requires a distinct actor. The demo has no separation-of-duties policy beyond this check.

## State machine
`PENDING → APPROVED → EXECUTED` or `PENDING → DENIED`. Denied actions cannot execute. Repeated execute returns `EXECUTED` without another event. Repeated idempotency key returns the existing action unless the payload differs.

## Consistency and guarantees
A database transaction persists action status and the audit event together. This guarantees transactional consistency **within PostgreSQL only**. External writes need a transactional outbox, a worker, downstream idempotency keys and reconciliation before any production use. No immutable/WORM guarantee is claimed: production should add append-only permissions, signed hashes or archival storage, retention policies, backups, and independent audit access controls.

## Observability correlation
Audit records include the current OpenTelemetry trace ID when a valid span exists. For governance requests, automatic FastAPI instrumentation creates a server span. Use the trace ID to investigate performance in Grafana Tempo or Dynatrace; audit events remain independently durable.

## Threat model
Risks: forged identity headers, cross-tenant data disclosure, replay, unauthorized execution, prompt-injected tool parameters, audit tampering, sensitive data in telemetry, and incomplete recording of actions outside the gateway. Mitigations needed before production: verified identity, strict tool gateway routing, JSON-schema validation, policy-as-code, RLS, outbox, retention, redaction, access reviews, and negative tests.

## Not implemented
A visual React execution explorer, real Salesforce/Jira writes, LangGraph persistent checkpoints, automated Dynatrace workflows, and production IAM are future work. API timeline is available now.
