# New: GCP Edition v3.0 — LangGraph on Google Cloud

The latest update adds a **separate, security-conscious GCP implementation** while retaining the historical Azure source. See **[GCP v3 architecture, setup, and validation](gcp_edition/README.md)**. Offline GCP adapter tests: `python -m pytest -q tests/test_gcp_edition.py`. This is **not a verified GCP deployment** and inherited live-provider writes remain disabled.

---

# Enterprise Agent Observability — Recovery Validation Increment

**Latest change:** An end-to-end reliability gate was added to the security-remediated
monorepo. The lab now uses a tenant-aware PostgreSQL-backed ServiceNow simulator,
a distinct HTTP adapter with strict destination checks, an integration test
through **LangGraph → one-time approval → outbox → governed worker → audit**,
and tests for concurrent dispatch, RLS and expired lease quarantine.

**Validation status:** Offline HTTP-contract/security regressions can run in the
build environment. The **Docker/PostgreSQL/LangGraph integration suite is
implemented but has not been executed here** because Docker is unavailable.
Passing offline tests is not proof of production SaaS or Azure behavior.

```bash
python -m pytest -q tests/test_simulator_provider_contract.py \
  tests/test_security_remediation.py tests/test_worker_dispatch_offline.py \
  tests/test_servicenow_contract_first.py tests/test_servicenow_scripted.py

# Requires Docker Engine + Compose plugin:
bash scripts/run_reliability_lab.sh
```

See [Recovery Validation Runbook](docs/RECOVERY_VALIDATION.md) for tests,
architecture, remaining risks, and CI release gates. Historical sections below
are preserved for traceability; this section supersedes their local-lab advice.

---

# Enterprise Agent Observability — Security & Reliability Remediation

> **Current deliverable.** This update fixes verified vulnerabilities in the
> ServiceNow Scripted REST client, locks down legacy demo APIs, adds trusted
> business-tenant mapping, separates local PostgreSQL runtime/checkpoint roles,
> and wires a fenced, reconciliation-first governed worker. **Real ServiceNow
> writes remain disabled; production certification is pending.**

**Start with [Security Remediation Guide](docs/SECURITY_REMEDIATION.md).** The
prior version's READMEs and runbooks below describe historical development
steps; do not use their insecure demo header examples for public ingress.

For the offline security regression suite:

```bash
python -m pytest -q tests/test_security_remediation.py tests/test_worker_dispatch_offline.py \
  tests/test_servicenow_scripted.py tests/test_servicenow_contract_first.py
```

For a Docker-enabled integration runner:

```bash
bash scripts/run_reliability_lab.sh
```

Configuration for real writes requires an independently certified provider-side
idempotency contract. See the guide before changing the default simulator mode.

---

# Enterprise Agent Observability — ServiceNow Contract-First Edition

This repository extends the existing Azure/LangGraph/PostgreSQL reliability lab with an **offline-contract-tested ServiceNow Table API connector**. It preserves existing source code and adds an HTTP client, explicitly guarded write APIs, a governed read-only adapter, and test cases for transport ambiguity.

**No ServiceNow instance was used. No real ServiceNow writes are enabled in the governed worker.** See [ServiceNow connector documentation](docs/SERVICENOW_CONTRACT_FIRST.md), and [Reliability lab](docs/RELIABILITY_LAB.md).

Run focused tests:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests/test_servicenow_contract_first.py
```

Full reliability tests require Docker/PostgreSQL: `bash scripts/run_reliability_lab.sh`.

---

# Enterprise Agent Observability — v2.0

**LangGraph + Azure PostgreSQL + transactional approvals + governed mock execution.**

> Status: integration scaffold; no real external writes and no verified production deployment.

See [v2 Architecture](docs/V20_ARCHITECTURE.md) and [v2 Runbook](docs/V20_RUNBOOK.md).

## New in v2.0

- `/v2/runs` authenticated workflow start with durable LangGraph checkpoint.
- `/v2/runs/{run_id}/decision` one-time approval, atomic audit and outbox enqueue.
- `/v2/runs/{run_id}` inspection of graph, approval, outbox and audit.
- `app/v2_worker.py` tenant-scoped, lease-fenced, **mock** ServiceNow dispatcher.
- `docker-compose.v2.yml` mounts both governance schemas for new local database volumes.

All prior versions and integration reference artifacts remain included.

---

# Enterprise Agent Observability Platform — v1.0

**Azure Container Apps · LangGraph · Azure PostgreSQL Flexible Server · Entra ID · Salesforce Apex · Jira Groovy · ServiceNow · OpenTelemetry · Grafana · Dynatrace**

## New in v1.0
A **new authenticated `/v1` governed-agent API** combines LangGraph checkpointed interrupts, a simulated Customer Risk Assessment, approval/rejection, PostgreSQL audit events and Microsoft Entra JWT verification. This extends the v0.9 repository; earlier labs, Apex/Groovy/ServiceNow examples, Terraform and observability configuration remain included.

**Security and maturity statement:** The v1 flow is a functional integration scaffold, **not production-ready**. The evidence is deterministic fixture data; actions are simulated, not sent to Salesforce, Jira or ServiceNow. Entra must be configured for the new endpoints. The older demo routes retain their earlier authentication limitations and must not be exposed publicly. PostgreSQL checkpoint and audit persistence require an actual database and initialization. No real Azure deployment or SaaS integration has been verified.

## Quick start
Read [v1.0 Runbook](docs/V10_RUNBOOK.md) and [Architecture / Threat Model](docs/V10_ARCHITECTURE.md).

```bash
cp .env.example .env
# Configure ENTRA_TENANT_ID and ENTRA_API_AUDIENCE
docker compose -f docker-compose.yml -f docker-compose.v1.yml up --build -d
```

## API
- `POST /v1/runs` — requires `Agent.Operator` Entra app role; checkpoints at human approval.
- `POST /v1/runs/{run_id}/decision` — requires `Agent.Approver`; resumes the graph.
- `GET /v1/runs/{run_id}` — requires `Agent.Auditor`; state + audit timeline.

## Testing
`pytest -q tests/test_v1_contracts.py` runs unit contract tests; see runbook for PostgreSQL/Entra integration checks. Do not equate passing unit tests with end-to-end validation.

## Next milestone
Transactional outbox, one-time approvals, managed identity for PostgreSQL, real connectors behind the governed Tool Gateway, Azure API Management + Entra enforcement and end-to-end distributed traces.


## v1.1 — Transactional approval/outbox lab increment

Added `governance/v11_schema.sql`, `app/v11_governance.py`, `scripts/v11_worker.py`, and `tests/test_v11_contracts.py`. This is **an additive module**, not a completed end-to-end integration with the v1 API. The worker simulates writes only. See [architecture](docs/V11_ARCHITECTURE.md) and [runbook](docs/V11_RUNBOOK.md).


## Reliability Integration Laboratory

A Docker Compose integration profile and PostgreSQL-backed ServiceNow fault simulator are now included. Run `bash scripts/run_reliability_lab.sh` and read [the reliability lab runbook](docs/RELIABILITY_LAB.md). This suite is not equivalent to production validation.


## Scripted REST Idempotent Incident Contract

New sample ServiceNow Script Include and POST/GET REST resources live in `integrations/servicenow/idempotent/`. The matching *disabled-by-default* Python client lives in `app/connectors/servicenow_scripted.py`. Run `pytest -q tests/test_servicenow_scripted.py` for offline contract checks. See [idempotency architecture and manual configuration](docs/SERVICENOW_SCRIPTED_IDEMPOTENCY.md). **No live ServiceNow deployment or PostgreSQL dispatch integration is claimed.**
