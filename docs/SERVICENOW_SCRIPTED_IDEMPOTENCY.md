# ServiceNow Scripted REST — Provider-Side Idempotency

**Status: implementation sample and offline contract tests; NOT installed or certified in ServiceNow.**

## Contract

- `POST /api/x_oai_agent/v1/incidents`: `{tenant_id, action_key, short_description, description}`.
- `GET /api/x_oai_agent/v1/incidents/{tenant_id}/{action_key}`: authoritative retrieval by key.
- Response: `{result:{sys_id, number, action_key, tenant_id}}`.
- Duplicate identical payload: same `sys_id`; a different payload for the same key: `409`.
- Request tenant is a claim only; authorization uses the authenticated ServiceNow identity and `x_oai_agent_tenant_access` membership records.

## Required ServiceNow configuration (manual)

1. Create a scoped application with role `x_oai_agent.api_executor`, assign only to OAuth integration principals.
2. Create table `x_oai_agent_tenant_access` with `u_user` (reference `sys_user`), `u_tenant` (string) and `u_active` (boolean). Configure ACLs to prevent non-administrative edits; provision explicit memberships.
3. Add custom fields on `incident`: `u_agent_dedupe_key` (string >= 194 characters), `u_agent_payload_hash` (string >= 64 characters), `u_agent_tenant` (string >= 64 characters). **Create a unique database index on `u_agent_dedupe_key`**. Do not rely on a lookup-before-insert check. Verify field length and index behavior on the target release.
4. Install server-side `AgentIncidentService` Script Include, then POST and GET resource scripts. Set the Script Include to non-client-callable and configure cross-scope privileges explicitly.
5. Configure the Scripted REST API's OAuth requirements and restrictive roles / ACLs; do not expose public endpoints. Test the service account's incident ACLs and any domain separation.
6. Review instance-mandatory fields, Business Rules, Data Policies and insert transaction behavior. Validate race conditions and unique-constraint collisions in the **real instance** before enabling writes.
7. Pin the API namespace/path to the deployed ServiceNow application scope; update Python `api_path` if different.

## Ambiguous-outcome behavior

The Python client converts write transport errors and 5xx to `ServiceNowUncertainWrite`. The worker must read the key **before considering any retry**, and an unconfirmed or unavailable lookup must park the outbox row for manual reconciliation. GET 404 does not alone prove that a prior POST never committed; eventual consistency, ACLs and failures can hide results. A unique provider-side key prevents concurrent duplicates only if it is actually installed and enforced. No exactly-once claims are made without real-instance verification.

## Offline tests

`python -m pytest -q tests/test_servicenow_scripted.py`

## Official docs

- https://www.servicenow.com/docs/r/api-reference/server-api-reference/c_ScriptableServiceRequest.html
- https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/r_ScriptedRESTServiceScriptExamples.html
- https://www.servicenow.com/docs/r/api-reference/rest-api-explorer/t_CreateAScriptedRESTAPIResource.html
- https://www.servicenow.com/docs/r/xanadu/api-reference/server-api-reference/c_GlideRecordAPI.html
