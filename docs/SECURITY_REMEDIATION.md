# Security & Reliability Remediation — Engineering Record

**Scope:** FastAPI authentication, Microsoft Entra authorization, ServiceNow
Scripted REST client, PostgreSQL role separation, LangGraph governed outbox
worker and offline adversarial tests.

**Maturity:** Hardened laboratory implementation; **NOT** certified for
production, real ServiceNow writes or untrusted public ingress.

## Fix inventory

| Finding | Remediation | Proof available |
|---|---|---|
| F01: insecure legacy governance routes | `/governance`, `/durable`, and non-one-time `/v1` routers are absent unless `DEPLOYMENT_ENV=local` **and** `ENABLE_INSECURE_DEMO_ROUTES=true`. `/risk/analyze` and `/metrics` require Entra bearer tokens and application roles; Salesforce read API now verifies identity itself. | Static tests; FastAPI route test in a dependency-complete environment |
| F02: malformed POST acknowledgement | Every incomplete, malformed, mismatched or unexpected POST acknowledgement becomes `ServiceNowUncertainWrite`; never retry merely because a response was malformed. | MockTransport regression tests |
| F03: cross-tenant response correlation | Both POST and GET require exact `tenant_id`, `action_key` and valid 32-character `sys_id`. | Negative correlation tests |
| F04: connector not wired | New `app/reliability/governed_worker.py` consumes the same `v11_outbox` as LangGraph-v2 and supports simulator / opt-in scripted ServiceNow provider. Legacy simulator dispatcher delegates to it. The old `v2_worker.run_once` and `scripts/v11_worker.run_once` require explicit local mock-worker opt-in; otherwise they cannot falsely mark an action complete. | Worker state-machine tests; real DB suite prepared but not executed in this container |
| F05: database superuser and Entra directory conflation | V2 API uses `agent_runtime_lab` with `NOBYPASSRLS`; checkpointer uses separate `agent_checkpoint_lab` with its own schema; Entra `tid` is no longer treated as business tenant. Instead, verified `oid` must be mapped through trusted, deployment-managed membership configuration. | Unit tests and SQL/Compose assertions; live RLS validation pending |
| F07: lease retry risk | On reclaimed leases (`attempts > 1`), perform lookup first. If lookup is missing or unavailable, park `UNCERTAIN`; **do not POST again**. | Fake-DB worker tests |
| Additional: conflicting idempotency payload | Provider 409 is terminal ambiguity requiring operator review; a subsequent GET must not certify a different payload as successful. | Regression test |

## Security model

The FastAPI v2 endpoints validate Entra JWT signatures, issuer, audience, expiry,
OID and application roles. **Directory tenant (`tid`) is not a business tenant.**
For laboratory purposes, `BUSINESS_TENANT_MEMBERSHIP_JSON` is a trusted mapping
from verified user object ID (`oid`) to a single business tenant. Missing
membership is rejected. This JSON configuration is *not* an enterprise
multi-tenant authorization service; deploy a proper tenant entitlement system
before public exposure. A different business tenant sharing the same Entra
directory must have separate verified membership.

RLS is applied to audit, approval and outbox tables. The runtime role does not
own the tables and cannot bypass RLS. **Important:** PostgreSQL session
variables set by the application, including `app.tenant_id`, are not a trusted
identity boundary against a compromised runtime account. A compromised app
role could set the variable itself. Protect the runtime and parameterize SQL;
for hard isolation use per-tenant database roles or databases, or a validated
`SECURITY DEFINER`/trusted-session model. LangGraph checkpoint rows in the
dedicated `agent_checkpoints` schema have no RLS in this increment. The
checkpoint credential must be isolated from untrusted access, or checkpoint
storage should be physically partitioned by tenant.

## New-database bootstrap

The **local** PostgreSQL initialization order is:

1. `001-schema.sql` — legacy demo schema
2. `002-v1-schema.sql` — audit events with RLS
3. `003-v11-schema.sql` — approvals and transactional outbox
4. `004-reliability-roles.sql` — non-superuser runtime and separate checkpointer roles
5. `005-security-remediation.sql` — terminal `UNCERTAIN` state and additional hardening

The `agent` bootstrap user **remains a superuser for local database
initialization only**; it must not be given to the v2 API or worker. The base
Docker Compose file no longer injects this administrator DSN into FastAPI; the
v2 override explicitly selects the least-privilege runtime login. Legacy demo
DB helpers no longer fall back to built-in administrator credentials. The
ServiceNow **simulator** intentionally has an isolated development-only
connection to that account. Never copy these local credentials into Azure.

### Existing Docker volume migration

Postgres executes `/docker-entrypoint-initdb.d` scripts **only when the data
directory is first created**. Existing volumes require a controlled manual
migration; the following commands apply the new role and constraint files
without removing data:

```bash
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.v2.yml -f docker-compose.integration.yml"
$COMPOSE up -d postgres
$COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U agent -d agent_audit \
  < governance/reliability_roles.sql
$COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U agent -d agent_audit \
  < governance/005_security_remediation.sql
```

These commands are for the local laboratory only. For real Azure use an audited
migration identity, Key Vault, TLS, non-public networking, and independent
credentials per workload.

### Initialize checkpoint tables

Run the initialization using **only** the `agent_checkpoint_lab` connection
and its dedicated search path; the runtime role cannot create tables:

```bash
docker compose -f docker-compose.yml -f docker-compose.v2.yml \
  exec api python scripts/init_checkpointer.py
```

Ensure the API container uses the `docker-compose.v2.yml` checkpoint URL.

## Work execution and safe enabling

Default mode: `SERVICENOW_PROVIDER_MODE=simulator`. Only this mode can be used
without a certified ServiceNow installation. The executable integration worker
is `python -m app.reliability.governed_worker`; its
`WORKER_BUSINESS_TENANT_ID` **must originate from trusted worker deployment
configuration**, never a caller-controlled request body or header.

Old mock-only workers (`app.v2_worker` and `scripts.v11_worker`) now require
`DEPLOYMENT_ENV=local` **and** `ENABLE_LEGACY_MOCK_WORKER=true`. They must never
be run against production outbox tables. The new worker is authoritative.

For a **real** Scripted REST endpoint, three independent settings are needed:

```dotenv
SERVICENOW_PROVIDER_MODE=scripted
ENABLE_SERVICENOW_REAL_WRITES=true
SERVICENOW_DEDUP_CERTIFIED=true
SERVICENOW_ORIGIN=https://your-authorized-instance.service-now.com
SERVICENOW_OAUTH_BEARER_TOKEN=<injected-by-secret-store>
```

**Do not set these flags without a real instance test proving the unique index,
ACLs, cross-scope permissions, membership mapping, conflict responses, and
read-after-write lookup consistency.** A configuration flag is an operator
attestation, not a technical certification. In production implement OAuth
client-credentials token rotation and Key Vault references rather than a
literal bearer token environment variable.

### State transitions

- Outbox `PENDING` -> `IN_PROGRESS` after a fenced lease claim.
- First-attempt confirmed POST -> `SUCCEEDED`, with audit recorded in the same
  PostgreSQL transaction.
- First-attempt uncertain POST -> lookup by action key. Confirmed matching
  lookup -> `SUCCEEDED`; otherwise `UNCERTAIN` with audit and manual review.
- Reclaimed lease (`attempts > 1`) -> **lookup before POST**. Confirmed
  lookup -> `SUCCEEDED`; missing/unavailable -> `UNCERTAIN`; never resend.
- HTTP 409 (same key, different payload) -> `UNCERTAIN`, **never clear the
  conflict using lookup**.
- Fencing requires matching attempt and unexpired lease at commit. A stale
  worker cannot overwrite a newer worker's result.

**Caveat:** the outbox ensures durable intent and fenced progress, *not* exactly
once delivery across independently committed databases. Recovery of terminal
`UNCERTAIN` actions requires a separately authorized, audited reconciliation
procedure. No auto replay is implemented.

## Offline tests and integration tests

```bash
python -m pytest -q \
  tests/test_security_remediation.py \
  tests/test_worker_dispatch_offline.py \
  tests/test_servicenow_scripted.py \
  tests/test_servicenow_contract_first.py

# On a Docker-enabled workstation / CI runner:
bash scripts/run_reliability_lab.sh
```

The Docker suite exercises real PostgreSQL and the simulator. **Passing offline
MockTransport or fake-DB tests does not certify ServiceNow JavaScript execution,
instance ACLs, indexing or Azure infrastructure.**

## Remaining risks / release gates

1. Run Docker integration tests and RLS/concurrency checks with real PostgreSQL.
2. Run the ServiceNow JavaScript against an authorized staging instance, verify
   uniqueness races, insert Business Rules and ACLs, then certify idempotency.
3. Introduce an enterprise membership/entitlement service for multi-business-
   tenant authorization and database tenant session binding.
4. Harden checkpoint storage tenant isolation and Entra app-only versus
   delegated claims, ensure worker/service identities are tenant-scoped.
5. Implement OAuth renewal, managed identity/Key Vault, private networking,
   credential rotation, audit retention and privacy controls in Azure.
6. Review legacy demo `/governance`, `/durable`, `/v1` data stores and samples
   before deliberate local-only activation. All old how-to docs are historical.
7. Configure an authenticated telemetry scrape identity for Prometheus:
   `/metrics` now requires an `Agent.Auditor` bearer token.

**No code in this repository is certified for production writes yet.**
