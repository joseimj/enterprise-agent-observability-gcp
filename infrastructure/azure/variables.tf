variable "subscription_id" { type = string description = "Azure subscription ID" }
variable "environment" { type = string default = "dev" }
variable "location" { type = string default = "eastus2" }
variable "container_image" { type = string description = "Existing accessible container image reference" }
variable "tags" { type = map(string) default = { project = "enterprise-agent-observability" } }

variable "postgres_sku" { type = string default = "B_Standard_B1ms" }
variable "postgres_backup_days" { type = number default = 7 validation { condition = var.postgres_backup_days >= 7 && var.postgres_backup_days <= 35 error_message = "Backup retention must be 7..35 days." } }
