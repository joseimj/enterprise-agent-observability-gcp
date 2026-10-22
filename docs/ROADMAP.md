# Roadmap

## v0.4 delivered
PostgreSQL audit schema, governance API, approval/deny state transitions, mock execution, idempotency guard, tenant-scoped timeline, trace correlation, documentation and contract tests.

## v0.4.1 priorities
Route *all* LangGraph tool invocations through a gateway, attach `run_id` to `/risk/analyze`, persist graph checkpoints, integration tests with a real PostgreSQL container, React execution explorer, and load/fault tests.

## v0.5 production-hardening candidates
OIDC/JWT and mTLS, policy engine, PostgreSQL RLS, transactional outbox, connector reconciliation, immutable audit archive, per-tenant quotas, security evaluation suite, IaC and operational SLOs.


## v0.4.1 Apex + Groovy increment

- Added Salesforce Apex REST read endpoint and Apex unit tests (not executed against an org).
- Added Jira ScriptRunner Cloud Groovy read template (not executed in Jira).
- Added strict Pydantic integration contracts and offline unit tests.
- Added [Apex/Groovy integration guide](APEX_GROOVY_INTEGRATION.md).
- NEXT: authenticated live adapters, all LangGraph tool calls through Tool Gateway,
  external write outbox, human-approval continuation, and execution explorer.
