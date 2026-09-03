output "workspace_ids" {
  value = { for env, ws in fabric_workspace.this : env => ws.id }
}

output "deploy_client_id" {
  description = "Client ID the solution's deploy jobs pass to azure/login."
  value       = azurerm_user_assigned_identity.deploy.client_id
}

output "viewers_group_id" {
  value = azuread_group.viewers.object_id
}

output "deploy_principal_id" {
  description = "Object ID of the deploy identity — used for cross-solution contracts."
  value       = azurerm_user_assigned_identity.deploy.principal_id
}
