output "resource_group_name" {
  description = "Name of the automation resource group."
  value       = azurerm_resource_group.automation.name
}

output "resource_group_id" {
  description = "ID of the automation resource group."
  value       = azurerm_resource_group.automation.id
}

output "storage_account_name" {
  description = "Name of the automation storage account."
  value       = azurerm_storage_account.automation.name
}

output "storage_account_id" {
  description = "ID of the automation storage account."
  value       = azurerm_storage_account.automation.id
}