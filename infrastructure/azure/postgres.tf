# Azure PostgreSQL Flexible Server: private network, delegated subnet, private DNS.
# Requires provider azurerm ~> 4.0; verify resource SKUs/region quotas before apply.
resource "azurerm_virtual_network" "data" {
  name = "vnet-${local.name}"
  location = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space = ["10.72.0.0/16"]
}
resource "azurerm_subnet" "postgres" {
  name = "snet-postgres"
  resource_group_name = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.data.name
  address_prefixes = ["10.72.1.0/24"]
  delegation {
    name = "postgres-delegation"
    service_delegation { name = "Microsoft.DBforPostgreSQL/flexibleServers" actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"] }
  }
}
resource "azurerm_private_dns_zone" "postgres" {
  name = "${local.name}.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name
}
resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name = "postgres-link"
  resource_group_name = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id = azurerm_virtual_network.data.id
}
resource "random_password" "postgres" {
  length = 32
  special = true
  override_special = "-_"
}
resource "azurerm_postgresql_flexible_server" "audit" {
  name = "pg-${local.name}"
  resource_group_name = azurerm_resource_group.main.name
  location = azurerm_resource_group.main.location
  version = "16"
  delegated_subnet_id = azurerm_subnet.postgres.id
  private_dns_zone_id = azurerm_private_dns_zone.postgres.id
  administrator_login = "agentadmin"
  administrator_password = random_password.postgres.result
  storage_mb = 32768
  sku_name = var.postgres_sku
  backup_retention_days = var.postgres_backup_days
  public_network_access_enabled = false
  depends_on = [azurerm_private_dns_zone_virtual_network_link.postgres]
  lifecycle { prevent_destroy = true }
}
resource "azurerm_postgresql_flexible_server_database" "audit" {
  name = "agent_audit"
  server_id = azurerm_postgresql_flexible_server.audit.id
  charset = "UTF8"
  collation = "en_US.utf8"
}
resource "azurerm_key_vault_secret" "postgres_password" {
  name = "postgres-admin-password"
  value = random_password.postgres.result
  key_vault_id = azurerm_key_vault.main.id
  depends_on = [azurerm_role_assignment.secrets]
}
output "postgres_host" { value = azurerm_postgresql_flexible_server.audit.fqdn }
output "postgres_database" { value = azurerm_postgresql_flexible_server_database.audit.name }
# Container Apps environment VNet integration is defined in network_v09.tf.
# Verify private DNS resolution and routing from the deployed revision.
