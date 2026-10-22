# v1.1 — Transactional Approval and Outbox (Lab Increment)

## Scope

This increment adds a PostgreSQL-backed one-time approval record and a transactional outbox. It **does not yet replace the v1 REST decision endpoint**, and the worker performs **mock execution only**. This is an additive implementation to be wired into the durable LangGraph API in the next integration step.

## Invariants

1. `v11_approvals` has one row per `(tenant_id, run_id)`.
2. Approval consumption uses `UPDATE ... WHERE status='PENDING' RETURNING`; concurrent decisions cannot both succeed.
3. The outbox insertion occurs in the **same database transaction** as the approval decision.
4. The outbox enforces `UNIQUE(tenant_id, action_key)`; the action key is deterministic per run and tool.
5. A worker claims a row using `FOR UPDATE SKIP LOCKED` and a lease.
6. Both tables have tenant RLS; use separate least-privileged migration and runtime roles.

## Reliability limitations

A lease expiry can cause **at-least-once** delivery. The unique outbox key prevents duplicate *enqueueing*, not duplicate external side effects. Real ServiceNow/Salesforce/Jira connectors must use a provider-supported idempotency mechanism or query/reconcile the remote state before retrying. A crash between remote success and local completion requires reconciliation. Human approver identity must come from verified Entra claims, not the request body. Audit events should be written in the same transaction as approval/outbox state changes when integrating this into v1 endpoints.

## Security boundaries

Never put raw prompts, customer PII, OAuth tokens, or credentials in the outbox payload. Encrypt sensitive data, enforce payload allowlists, validate tenant membership and per-action authorization, and audit each state transition. Do not expose the worker's tenant selector to end users. RLS does not protect against a database owner or BYPASSRLS role.

## Next integration milestone

Replace the v1 decision endpoint with an atomic approval/outbox transaction and have LangGraph's resumed node return `QUEUED`, not execute a remote write. Add an authenticated status endpoint and an audited reconciliation worker. This requires an integration test with real PostgreSQL and concurrent approvals before production use.
