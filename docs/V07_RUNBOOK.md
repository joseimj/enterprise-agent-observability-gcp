# v0.7 Operator Runbook

## Local
```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8000/health
```
The local risk scenario still uses mock enterprise services by default.

## Azure provisioning
See `infrastructure/azure/README.md`. Terraform requires a real subscription and an accessible image. The service is deployed with internal ingress and Salesforce API disabled by default.

## Salesforce configuration (future authenticated gateway required)
Create a Salesforce connected app with client-credentials support, use a dedicated integration user, and store its client ID/secret in Azure Key Vault. After adding a trusted API gateway, secret references and appropriate policies, configure `SALESFORCE_LOGIN_URL`, `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`, `SALESFORCE_API_VERSION`, `ENABLE_SALESFORCE_READ_API=true`, and `GATEWAY_AUTH_ENFORCED=true`. Setting these flags alone is **not** authentication; the gateway must genuinely enforce JWT verification and prevent bypass.

## Verification
- Confirm the application is not internet-accessible.
- Confirm Key Vault access is restricted to intended principals.
- Confirm Salesforce API user has read-only Account permissions.
- Check trace export and redact sensitive attributes.
- Test tenant isolation and approval controls before enabling any writes.
