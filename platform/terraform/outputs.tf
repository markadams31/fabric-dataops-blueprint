# Everything github-setup.sh publishes as GitHub Actions variables. Identifiers only.

output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "subscription_id" {
  value = var.subscription_id
}

output "platform_client_id" {
  description = "Client ID the workflows pass to azure/login."
  value       = azurerm_user_assigned_identity.platform.client_id
}

output "capacity_name" {
  value = azurerm_fabric_capacity.platform.name
}

output "resource_group" {
  value = azurerm_resource_group.platform.name
}

output "tfstate_subscription_id" {
  value = var.tfstate_subscription_id
}

output "tfstate_storage_account" {
  value = var.tfstate_storage_account
}

output "tfstate_container" {
  value = var.tfstate_container
}

output "github_repository" {
  value = var.github_repository
}

# Pass-through of inputs github-setup.sh publishes as Actions variables, so a
# fork needs exactly one source of values: this configuration.
output "location" {
  value = var.location
}
output "capacity_admins" {
  value = var.capacity_admins
}
output "budget_email" {
  value = var.budget_email
}
output "budget_start_date" {
  value = var.budget_start_date
}
output "tfstate_resource_group" {
  value = var.tfstate_resource_group
}
