# One solution: a team's dev/test/prod workspaces on the shared capacity, the
# identity that deploys into them, and the group its consumers read through.
# Instantiated once per folder under solutions/ — the folder name is the input.

terraform {
  required_providers {
    fabric  = { source = "microsoft/fabric" }
    azurerm = { source = "hashicorp/azurerm" }
    azuread = { source = "hashicorp/azuread" }
  }
}

locals {
  environments = ["dev", "test", "prod"]
}

resource "fabric_workspace" "this" {
  for_each     = toset(local.environments)
  display_name = "ws-${var.name}-${each.key}"
  description  = "Solution ${var.name} · ${each.key} — managed by platform/terraform; deployed by mi-deploy-${var.name}"
  capacity_id  = var.capacity_id

  identity = {
    type = "SystemAssigned"
  }
}

# --- the identity that deploys item content into these workspaces -------------

resource "azurerm_user_assigned_identity" "deploy" {
  name                = "mi-deploy-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
}

resource "azurerm_federated_identity_credential" "env" {
  for_each            = toset(local.environments)
  name                = "gh-environment-${var.name}-${each.key}"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.deploy.id
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_oidc_repo}:environment:${var.name}-${each.key}"
  audience            = ["api://AzureADTokenExchange"]
}

# Deploying needs the SPN tenant settings, which are scoped to this group.
resource "azuread_group_member" "deploy_automation" {
  group_object_id  = var.automation_group_id
  member_object_id = azurerm_user_assigned_identity.deploy.principal_id
}

resource "fabric_workspace_role_assignment" "platform_admin" {
  for_each     = fabric_workspace.this
  workspace_id = each.value.id
  principal = {
    id   = var.platform_principal_id
    type = "ServicePrincipal"
  }
  role = "Admin"
}

# Member: publish items and write data, but not manage access — that stays here.
resource "fabric_workspace_role_assignment" "deploy" {
  for_each     = fabric_workspace.this
  workspace_id = each.value.id
  principal = {
    id   = azurerm_user_assigned_identity.deploy.principal_id
    type = "ServicePrincipal"
  }
  role = "Member"
}

# --- the humans: consumers read, nobody writes --------------------------------

resource "azuread_group" "viewers" {
  display_name     = "grp-${var.name}-viewers"
  mail_nickname    = replace("grp-${var.name}-viewers", "-", "")
  security_enabled = true
}

resource "fabric_workspace_role_assignment" "viewers" {
  for_each     = fabric_workspace.this
  workspace_id = each.value.id
  principal = {
    id   = azuread_group.viewers.object_id
    type = "Group"
  }
  role = "Viewer"
}
