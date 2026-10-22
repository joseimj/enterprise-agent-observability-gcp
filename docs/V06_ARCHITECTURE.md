# v0.6 Architecture and Trust Boundaries

## Intent
Add ServiceNow incident creation as a **governed action contract** and expose an API-based execution explorer, without claiming live SaaS writes. Salesforce Apex, Jira Groovy, and ServiceNow JavaScript reference implementations from v0.5 are retained.

## Action lifecycle
1. Agent proposes `servicenow.create_incident` with validated `account_id`, `summary`, and `priority`.
2. Gateway writes a `PENDING` action and an `ACTION_REQUESTED` audit event to PostgreSQL.
3. Separate approver identity accepts or rejects. Self-approval is prohibited.
4. Executor can run only an `APPROVED` action. **Current execution is simulated**, producing `ACTION_EXECUTED_MOCK`.
5. `/governance/runs/{run_id}/explorer` reconstructs actions and audit events; trace IDs correlate to Grafana/Tempo and Dynatrace.

## Security boundary
The `X-Tenant-Id`, `X-Actor-Id`, and `X-Role` headers are unverified demo claims. This release is not safe for public exposure. Do not treat it as OAuth, RBAC, or tenant authentication. PostgreSQL queries are tenant-scoped but do not implement row-level security.

## External write safety
Live ServiceNow writes are intentionally disabled. A future executor must use verified workload identity, per-tenant credentials, an outbox, idempotency keys, state reconciliation, bounded retries, audit-before-dispatch, and fail-closed policy checks. A timeout after dispatch is an unknown outcome, not a safe automatic retry.

## LangGraph checkpoints
Durable checkpoint integration remains outstanding; governance action persistence does **not** imply LangGraph can resume an interrupted graph. All agent writes are not yet routed through the gateway.

## OpenTelemetry
Use OTLP to export traces and logs to the existing Grafana/Dynatrace destinations. Never put PII or raw incident descriptions in span attributes. The audit database remains the authoritative event store; traces may be sampled.
