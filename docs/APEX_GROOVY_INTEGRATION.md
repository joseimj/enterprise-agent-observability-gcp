# Salesforce Apex + Jira Groovy: Integration Design

## Scope and status

This increment adds **source-level integration examples and validated Python data contracts**.
The live Salesforce and Jira ScriptRunner endpoints are **not wired into the local LangGraph
workflow**. Docker Compose continues to use deterministic mock services. No production
Salesforce/Jira credentials are required for local execution.

## Read path

1. FastAPI receives a customer-risk request and establishes a W3C trace context.
2. A future authenticated connector uses Salesforce REST Apex (`/services/apexrest/agent-risk/v1/accounts/{id}`)
   or the configured ScriptRunner Jira endpoint.
3. Apex uses `with sharing` and `WITH USER_MODE` to respect Salesforce data permissions.
4. Groovy validates the account key, issues a bounded Jira JQL search, and returns selected fields.
5. Python Pydantic contracts validate response shapes before they enter LangGraph.
6. The connector records duration, sanitized status, and correlation identifiers; no secrets,
   full prompts, or raw customer records should enter OTel attributes.

## Write path and approval boundary

- All mutating tools MUST pass through the FastAPI governance gateway.
- Record the requested action and a hash of validated arguments; require separate approver identity.
- Recheck tenant, actor permissions and action state immediately before dispatch.
- For external writes use a transactional outbox, stable idempotency keys, and reconciliation;
  do not claim atomic transactions across PostgreSQL, Salesforce, and Jira.
- Salesforce Apex must enforce CRUD/FLS/sharing and business rules independently.
- Jira ScriptRunner must validate scopes, issue transition constraints, and authorization.
- Record external request IDs and outcomes in the audit store after redaction.

## Distributed tracing boundaries

Apex and ScriptRunner Cloud may not support the same automatic OTel SDK hooks as Python.
Forward a safe `traceparent` only through trusted integration channels if supported;
otherwise correlate using an opaque `run_id`/`external_request_id` in an audit record.
Do not assume an automatically continuous trace across managed SaaS scripts.

## Salesforce deployment (requires org and CLI)

```bash
cd integrations/salesforce
sf org login web --alias agent-lab
sf project deploy start --target-org agent-lab
sf apex run test --tests AgentRiskApiTest --target-org agent-lab --result-format human
```

Grant only necessary Apex class access and object permissions to a dedicated integration user.
Review Salesforce API version compatibility, field-level access, rate limits, and test results.

## Jira deployment (requires ScriptRunner Cloud)

Review `integrations/jira/scriptrunner/README.md`, adapt the script binding and endpoint
wrapper to your installed version, then validate JQL, Jira project permissions, and
API rate limits in a sandbox. This template is intentionally read-only.

## Security and audit gaps

Demo `X-Tenant-ID`, `X-Actor-ID`, `X-Role` headers are spoofable and MUST be replaced with
verified OAuth/OIDC identity. PostgreSQL audit records are not immutable. The LangGraph
read nodes are not yet intercepted by the governance layer; that remains a next milestone.
