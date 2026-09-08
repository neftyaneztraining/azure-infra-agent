resource "azurerm_resource_group" "automation" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    Environment = var.environment
    Application = "Azure Infrastructure Automation"
    ManagedBy   = "Terraform"
  }
}

resource "azurerm_storage_account" "automation" {
  name                     = "stinfraauto${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.automation.name
  location                 = azurerm_resource_group.automation.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  tags = {
    Environment = var.environment
    Application = "Azure Infrastructure Automation"
    ManagedBy   = "Terraform"
  }
}

resource "azurerm_storage_container" "logs" {
  name                  = "logs"
  storage_account_id    = azurerm_storage_account.automation.id
  container_access_type = "private"
}

resource "azurerm_storage_queue" "requests" {
  name               = "infrastructure-requests"
  storage_account_id = azurerm_storage_account.automation.id
}

resource "azurerm_storage_table" "requests" {
  name               = "InfrastructureRequests"
  storage_account_id = azurerm_storage_account.automation.id
}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}