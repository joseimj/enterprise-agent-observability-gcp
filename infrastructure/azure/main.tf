terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
provider "azurerm" { features {} subscription_id = var.subscription_id }
resource "random_string" "suffix" { length = 6 special = false upper = false }
locals { suffix = random_string.suffix.result; name = "eao-${var.environment}-${local.suffix}" }
resource "azurerm_resource_group" "main" { name = "rg-${local.name}" location = var.location tags = var.tags }
resource "azurerm_log_analytics_workspace" "main" {
  name = "log-${local.name}" location = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name sku = "PerGB2018" retention_in_days = 30
}
resource "azurerm_container_app_environment" "main" {
  name = "cae-${local.name}" location = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id = azurerm_subnet.container_apps.id
  internal_load_balancer_enabled = true
}
resource "azurerm_user_assigned_identity" "agent" {
  name = "id-${local.name}" location = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}
resource "azurerm_key_vault" "main" {
  name = "kv-${local.name}" location = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name tenant_id = data.azurerm_client_config.current.tenant_id
  sku_name = "standard" enable_rbac_authorization = true
  purge_protection_enabled = true
}
data "azurerm_client_config" "current" {}
resource "azurerm_role_assignment" "secrets" {
  scope = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id = azurerm_user_assigned_identity.agent.principal_id
}
# Container image must be published separately to a reachable registry.
# This reference is an input and no image is built by Terraform.
resource "azurerm_container_app" "agent" {
  name = "ca-${local.name}" container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name = azurerm_resource_group.main.name revision_mode = "Single"
  identity { type = "UserAssigned" identity_ids = [azurerm_user_assigned_identity.agent.id] }
  template {
    min_replicas = 1
    max_replicas = 2
    container {
      name = "agent" image = var.container_image cpu = 0.5 memory = "1Gi"
      env { name = "INFERENCE_PROVIDER" value = "offline" }
      env { name = "ENABLE_SALESFORCE_READ_API" value = "false" }
      env { name = "OTEL_SERVICE_NAME" value = "enterprise-agent-api" }
    }
  }
  # Internal ingress until APIM, OIDC validation, and network controls are deployed.
  ingress { external_enabled = false target_port = 8000 transport = "http" traffic_weight { percentage = 100 latest_revision = true } }
}
output "resource_group" { value = azurerm_resource_group.main.name }
output "container_app" { value = azurerm_container_app.agent.name }
output "key_vault" { value = azurerm_key_vault.main.name }
