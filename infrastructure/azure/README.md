# Azure infrastructure (v0.7)

This Terraform module provisions an Azure resource group, Log Analytics workspace, Container Apps environment, internal-only Container App, user-assigned managed identity, and Key Vault with RBAC. **It does not provision API Management, private endpoints, PostgreSQL, OTLP Collector, Grafana, or Dynatrace**, and does not deploy Salesforce/Apex itself. The Container App is intentionally inaccessible from the public internet.

## Prerequisites
- Azure CLI login and permission to create resources and assign roles.
- Terraform >=1.6 and AzureRM 4.x.
- A prebuilt application image available from a registry the Container App can pull; configure registry credentials/identity as appropriate before deployment.
- Salesforce org with an OAuth client-credentials-capable connected app and least-privilege integration user (separate Salesforce configuration).

```bash
cd infrastructure/azure
cp terraform.tfvars.example terraform.tfvars
# edit subscription_id and container_image
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

**Do not deploy with production credentials yet.** This module deliberately disables the Salesforce endpoint and lacks a configured authenticated API gateway. The existing governance endpoints in the inherited app also require an authenticated boundary before any external exposure. The container may require additional environment configuration and a reachable PostgreSQL service for governance features.

## Security and production gaps
1. Add API Management with JWT validation and backend network integration, Entra ID authorization, rate limits, and request filtering.
2. Configure managed-identity Key Vault secret references for Salesforce client credentials. Azure managed identity does **not** authenticate directly to Salesforce.
3. Configure ACR pull identity, private networking and outbound egress restrictions.
4. Deploy PostgreSQL Flexible Server, private DNS, migrations and backup policies.
5. Deploy an OTLP Collector and configure Grafana/Dynatrace exporters without exposing secrets.
6. Configure environment promotion, drift detection, policy-as-code and CI security scans.
7. Review Salesforce data residency and CRM API permissions; Apex executes in Salesforce, not in Azure.
