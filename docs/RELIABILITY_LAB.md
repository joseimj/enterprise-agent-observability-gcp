# Real PostgreSQL Reliability Laboratory

## Scope and boundaries
This is a repeatable, local integration-test addition to the v2.0 monorepo. It exercises
PostgreSQL transactions, concurrent approval consumption, outbox leases, tenant RLS,
LangGraph checkpoint restoration, and ambiguous provider responses using a durable
ServiceNow **simulator**. It does NOT execute real ServiceNow, Salesforce or Jira writes.

## Execution

```bash
bash scripts/run_reliability_lab.sh
```

Requires Docker Engine, Docker Compose v2 and network access to retrieve pinned/base images.
On an existing Docker volume, the `docker-entrypoint-initdb.d` SQL will **not** re-run.
Apply `governance/reliability_roles.sql` manually with the database owner to prepare an existing
volume, or use an empty test volume. Do not run `docker compose down -v` against valued data.

## Tests
- Real PostgreSQL, non-owner `agent_runtime_lab` role, FORCE RLS, row visibility and insert rejection.
- Four concurrent approval attempts: only one succeeds, and exactly one outbox row is inserted.
- Three competing workers: one lease claim, fenced completion.
- Outbox survives connection closure.
- LangGraph checkpoint survives re-instantiation and resumes an interrupted run.
- Durable mock provider commits before returning HTTP 504; dispatcher reconciles by key.
- Provider refuses duplicate key with a conflicting payload.

## Design limitations
- `agent_runtime_lab` is a local demo role with a plaintext password, not an Entra workload identity.
- LangGraph checkpoint setup uses the local database owner for table creation and execution:
  this must be split into separate migration/runtime identities in Azure.
- The provider simulator uses PostgreSQL to emulate the external system's durable idempotency.
  Real ServiceNow APIs may require a custom Scripted REST API / deduplication table to supply
  equivalent key-based lookup and create semantics.
- The dispatcher parks unconfirmed actions in FAILED (manual reconciliation) and records an audit
  event. Automatic workers only claim PENDING or expired IN_PROGRESS actions. A real provider
  still needs idempotency server-side, especially if a worker crashes after a POST and before parking.
- Existing v2 API endpoints still require Microsoft Entra JWT configuration.
- Container restarts, actual fault injection, Entra integration, tracing export and cloud
  networking have not been run in the assistant environment.

## CI
The optional `.github/workflows/reliability-lab.yml` workflow runs the same integration suite on pull requests and manual dispatch. This workflow has not been executed in this environment.

## Future proof points
Add real process-kill/lease-expiry tests, DB outage/recovery, multiple-tenant load tests,
state repair reconciler, verified OTLP pipelines, and signed production connector contracts.
