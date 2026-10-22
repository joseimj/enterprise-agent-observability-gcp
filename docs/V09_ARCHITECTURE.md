# v0.9 — Durable LangGraph Execution Architecture

## Scope and design

This release adds a separate **demonstration** graph (`app/durable_workflow.py`) to the existing Customer Risk Agent. It exercises LangGraph's `interrupt()` and `Command(resume=...)` primitives with the official PostgreSQL checkpointer. Existing v0.8 endpoints and the older governance database are preserved, **not yet unified**. No real ServiceNow, Jira, or Salesforce write occurs.

## State lifecycle

`START -> evaluate -> approval [interrupt + checkpoint] -> execute_mock -> END`.

`evaluate` deterministically produces a proposed ServiceNow incident. `approval` pauses before the mock executor. The run is resumed by a second API request using the same tenant-prefixed thread ID. Approval is recorded in graph state, **not yet in the durable governance audit ledger**.

## Security boundaries

- **DEMO ONLY**: identity is supplied by HTTP headers. Never expose these endpoints publicly; header identity is forgeable. A production implementation must validate Entra-issued JWTs and authorization policy server-side.
- Thread prefixes reduce accidental cross-tenant collisions, but **are not database RLS**. LangGraph's saver tables are not protected by the v0.8 RLS policies. Production must enforce tenant separation with verified identity and isolated DB roles/instances or proven saver-level controls.
- Database checkpoint data may include sensitive content; use encryption, retention policies, access restrictions, and payload minimization.
- The simulated action does not provide exactly-once external effects. Real writes require transactional outbox, idempotency key, status reconciliation and an authorized Tool Gateway.
- No approval request or decision is recorded to the append-only audit ledger in v0.9. Do not describe this lab as regulatory-grade auditability.

## Azure infrastructure

`network_v09.tf` adds a dedicated delegated Container Apps subnet (`10.72.2.0/23`). The Container Apps managed environment is VNet-injected with internal ingress, and the PostgreSQL Flexible Server stays in its separate delegated subnet with linked private DNS. **Terraform is unverified against a live Azure subscription**. Azure database credentials and secret references are not yet wired into the Container App. Avoid deploying this release to production.

## Remaining engineering gates

1. Provision a least-privileged migration role and separate runtime role for LangGraph checkpoint tables.
2. Connect Azure Key Vault references and a private deployment runner to the database.
3. Validate Azure VNet, DNS, routing, TLS and PostgreSQL connectivity in a development subscription.
4. Replace demo identity headers with Entra JWT validation and resource-level authorization.
5. Integrate LangGraph tool calls with governed actions, durable audit, and idempotent outbox.
6. Test resume after actual container restart and simulate approval races in PostgreSQL.
