# v0.5 Architecture and Integration Contracts

## Scope

The read-only customer risk graph now follows **Salesforce → Jira → ServiceNow → risk scoring → knowledge → inference**. All three reads pass through the Python allowlisted `enterprise_tools.read_tool()` gateway. ServiceNow is represented by a deterministic FastAPI mock in local Docker; Jira and Salesforce remain mocked locally. Python spans are emitted for tool calls and ServiceNow requests.

## Trust boundaries

- The Python gateway validates tool names and account references but is **not a production authorization service**. The governance approval API remains an independent lab flow for writes.
- Salesforce Apex code runs inside Salesforce and must enforce CRUD/FLS, sharing, OAuth scopes and permission sets.
- Jira Groovy policy/listener examples target **ScriptRunner Data Center**; the inherited read-only script targets **ScriptRunner Cloud**. They cannot be deployed interchangeably.
- ServiceNow Scripted REST and Script Include must be deployed with instance ACLs and an OAuth integration user. `GlideRecordSecure` enforces ACL checks for the querying principal.
- Never propagate bearer tokens, prompts containing PII or full business records into spans or logs. Use `traceparent` propagation only on trusted service-to-service links.

## Data contract

ServiceNow mock: `GET /itsm/{account_id}` returns `{account_id, incidents:[{number,severity,status,sla_breached,configuration_item,source}]}`. The agent normalizes `number` to the risk scoring `key` field. Production adapters must map native ServiceNow state, priority, SLA and CMDB reference values to this contract; the supplied ServiceNow Script Include deliberately returns native fields and therefore needs an adapter before live substitution.

## Observability and reliability

OTLP traces go to the existing Grafana/Tempo stack; the optional Dynatrace Compose overlay remains available. Simulate `servicenow_failure` and `slow_servicenow` with `/risk/analyze`. Inspect the spans `tool.servicenow.itsm.read` and `servicenow.itsm.lookup`. Failure injection returns HTTP 502 at the API. This is not a claim of Davis AI auto-detection: Dynatrace alerting must be configured in a real tenant.

## Remaining production gaps

Identity verification, centralized write interception, durable outbox, production OAuth, human-in-the-loop LangGraph checkpoints, end-to-end tests with real SaaS tenants, and dashboard execution explorer are **not implemented**. The example Apex/Groovy/ServiceNow code has not been compiled or run in its vendor platform.
