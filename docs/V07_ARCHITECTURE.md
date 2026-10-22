# v0.7 Architecture Decision: Azure-hosted integration and agent runtime

## Decision
Salesforce CRM and Apex remain on Salesforce-managed infrastructure. Azure hosts FastAPI, LangGraph and a Salesforce integration adapter. Jira/Groovy and ServiceNow retain their existing external boundaries. Amazon Bedrock is optional; using it from Azure requires separate AWS authentication and network egress.

## Trust boundaries
- Client to Azure API Management (target only, **not provisioned**): Entra ID JWT verification, audience, issuer, scopes, rate limiting.
- API gateway to agent runtime: private network and workload authentication (future).
- Azure agent to Salesforce: Salesforce OAuth 2.0 client credentials, dedicated integration user, least-privilege API access, allowlisted Salesforce instance domain. Azure managed identity accesses Azure Key Vault only.
- Agent to Jira and ServiceNow: platform-specific authentication and scoped permissions.
- Agent to PostgreSQL: audit writes are durable, transactional, tenant-scoped; current lab identity is not production-grade.
- Agent/Collector to observability: redact customer PII, OAuth tokens, prompts, secrets; propagate trace context when possible.

## Salesforce request path
1. Authorized user submits a risk request to an authenticated API gateway (future).
2. Gateway validates identity and forwards trusted claims to FastAPI.
3. LangGraph requests a Salesforce read through the governed adapter (planned end-to-end wiring).
4. Adapter obtains OAuth token from Salesforce and fetches an account by Salesforce record ID.
5. Trace spans capture timing/status without storing bearer tokens or full CRM payloads.
6. Writes are not enabled; a future write path must pass Tool Gateway, durable audit, approval and idempotency controls.

## Current implementation
- Read-only Salesforce OAuth client module, optional endpoint guarded behind environment flags.
- Terraform scaffold for Azure Container Apps, Key Vault, managed identity and Log Analytics.
- Existing local Docker Compose/Grafana/Dynatrace configurations retained from v0.6.

## Explicit non-goals of this release
- No automatic migration of Salesforce CRM/Apex to Azure.
- No live Salesforce integration tests, no production authentication gateway, no deployment of observability backends in Azure.
- No complete LangGraph-to-Tool-Gateway enforcement or checkpoint persistence.
