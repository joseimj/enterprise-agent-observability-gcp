# Reliability Integration Gate — Engineering Runbook

**Scope:** Actual PostgreSQL 16, checkpoint-backed LangGraph state recovery,
transactional approval and outbox, concurrent governed workers, and a
ServiceNow-shaped **HTTP simulator** running in Docker. **Not a live ServiceNow,
Salesforce, Jira, Microsoft Entra, Azure, Grafana or Dynatrace certification.**

## Run locally or in GitHub Actions

```bash
bash scripts/run_reliability_lab.sh
```

Requires Docker Engine with the Docker Compose v2 plugin, image retrieval
access, and available local resources. The script uses a uniquely named
Compose project and transient volume, waits for healthy PostgreSQL and
simulator services, and runs `pytest -q tests/reliability -v`. Upon completion,
only that ephemeral project's containers and volumes are deleted; failures
print service diagnostics. To retain containers for debugging, set
`RELIABILITY_LAB_KEEP=1`. Run the CI workflows
`.github/workflows/security-remediation.yml` and
`.github/workflows/reliability-lab.yml` for offline and PostgreSQL gates.

**Note:** Container image and Python dependency downloads may fail in offline
or rate-limited environments. Failure to execute a gate is **not a passing
result**. The new Postgres/LangGraph integration suite has not been run in the
artifact-build environment, where Docker is unavailable.

## Technical changes

- New `app/reliability/simulator_provider.py` isolates HTTP client behavior
  from the worker's psycopg dependency and parses the simulator URL to prevent
  local-looking URLs from redirecting to arbitrary destinations.
- The mock server uses `sim_incidents_v2` with a PostgreSQL `PRIMARY KEY
  (tenant_id, idempotency_key)`. It intentionally does **not** migrate
  tenant-less `sim_incidents` records; it is an ephemeral local lab fixture.
- The POST body and GET query include a business-tenant label. The client
  verifies the label, idempotency key and incident number on every response.
  The simulator does **not** authenticate that label; it is an adversarial
  test environment and must never be exposed to untrusted networks.
- HTTP 409 is an idempotency contract conflict. The worker parks an item as
  `UNCERTAIN` rather than trying to confirm a mismatched payload by lookup.
- The integration runner exercises the **actual** v2 start/decision and
  governed worker, rather than building another independent toy workflow.

## Acceptance matrix

| Test | Guarantee under test | Test location |
| --- | --- | --- |
| LangGraph checkpoint reconstruction | Existing thread is available from new saver/graph instance | `test_checkpointer.py` |
| Start → approval → outbox → worker → audit | Durable end-to-end path; lost POST acknowledgment reconciles to one incident | `test_end_to_end_governed.py` |
| Concurrent approval | One authorization consumption and one outbox intent | `test_postgres_outbox.py` |
| Four concurrent dispatchers | One claimed action / one external record | `test_end_to_end_governed.py` |
| Expired lease with missing external record | No automatic second POST; quarantine as `UNCERTAIN` | `test_end_to_end_governed.py` |
| Negative human decision | No outbox record | `test_end_to_end_governed.py` |
| Cross-tenant incident lookup | Different tenant cannot retrieve incident for the same action key | `test_end_to_end_governed.py` |
| Runtime role and RLS enforcement | Runtime is not superuser or `BYPASSRLS`; cross-tenant reads/writes filtered or denied | `test_end_to_end_governed.py` |
| Connection reuse | `set_config(..., true)` tenant context does not survive transaction boundary | `test_end_to_end_governed.py` |
| HTTP transport correlation | Tenant/key mismatches, ambiguous POST, malformed JSON, 409 and endpoint URL validation | `test_simulator_provider_contract.py` |

## Interpret results correctly

The outbox is a durable intent record and recovery mechanism, not an
exactly-once guarantee for an external SaaS call. `UNCERTAIN` is intentionally
terminal until an authorized operator or future reconciler establishes the
provider-side result. A `404` during reconciliation **must not** trigger a
blind retry after an attempt may already have committed remotely.

The current tenant context is set using transaction-local PostgreSQL settings,
which are an effective barrier against cross-tenant reads from correctly
scoped code but **not a hardened trust boundary against a compromised runtime
credential**. LangGraph checkpoint tables are separately credentialed and
schema-scoped but not RLS-isolated across business tenants. For strong isolation,
use per-tenant database roles/databases, a trusted session-binding layer,
or an independently reviewed partitioning model. A tenant header/query in a
simulator or SaaS adapter is never a substitute for authenticated authorization.

## Remaining production gates

1. Execute and archive the real PostgreSQL/Compose test run from CI, triage
   any failures and attach a reproducible job URL.
2. Add an authenticated, provider-side unique idempotency contract and
   validate the scripts with ServiceNow ACL/Business Rules in an authorized
   instance; documentation-driven tests cannot prove provider behavior.
3. Certify Microsoft Entra audience, issuer, roles and business-tenant
   membership against a real identity configuration.
4. Prove checkpoint tenant isolation, Managed Identity and Key Vault
   configuration, private networking and recovery-point/availability targets
   in Azure Database for PostgreSQL Flexible Server.
5. Verify live OpenTelemetry trace linkage and rate/error alerts in Grafana
   and Dynatrace before a production write rollout.

Do not switch on `ENABLE_SERVICENOW_REAL_WRITES` or
`SERVICENOW_DEDUP_CERTIFIED` based solely on this test harness.
