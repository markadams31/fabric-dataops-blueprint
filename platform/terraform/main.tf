# Platform foundation: the capacity, the identity CI runs as, and the groups that
# scope tenant settings. One deliberate exception to "Terraform owns everything":
# pause/resume of the capacity is an operational action (capacity.yml), not state.

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "platform" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_fabric_capacity" "platform" {
  name                = var.capacity_name
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location

  sku {
    name = var.capacity_sku
    tier = "Fabric"
  }

  administration_members = var.capacity_admins
}

resource "azurerm_consumption_budget_resource_group" "platform" {
  name              = "budget-${azurerm_resource_group.platform.name}"
  resource_group_id = azurerm_resource_group.platform.id
  amount            = var.budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
    end_date   = "2031-12-31T00:00:00Z"
  }

  notification {
    enabled        = true
    operator       = "GreaterThan"
    threshold      = 80
    threshold_type = "Actual"
    contact_emails = [var.budget_email]
  }

  notification {
    enabled        = true
    operator       = "GreaterThan"
    threshold      = 100
    threshold_type = "Forecasted"
    contact_emails = [var.budget_email]
  }
}

# --- the identity CI runs the control plane as --------------------------------

resource "azurerm_user_assigned_identity" "platform" {
  name                = var.platform_identity_name
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
}

# GitHub OIDC trust: tokens for the "platform" environment and for main.
resource "azurerm_federated_identity_credential" "environment_platform" {
  name                = "gh-environment-platform"
  resource_group_name = azurerm_resource_group.platform.name
  parent_id           = azurerm_user_assigned_identity.platform.id
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${local.github_oidc_repo}:environment:platform"
  audience            = ["api://AzureADTokenExchange"]
}

resource "azurerm_federated_identity_credential" "branch_main" {
  name                = "gh-branch-main"
  resource_group_name = azurerm_resource_group.platform.name
  parent_id           = azurerm_user_assigned_identity.platform.id
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${local.github_oidc_repo}:ref:refs/heads/main"
  audience            = ["api://AzureADTokenExchange"]
}

# Manage the capacity (suspend/resume/scale) — nothing outside its resource group.
resource "azurerm_role_assignment" "platform_rg_contributor" {
  scope                = azurerm_resource_group.platform.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.platform.principal_id
  principal_type       = "ServicePrincipal"
}

# CI runs Terraform as this identity, so it must manage what Terraform manages:
# role assignments at the two scopes in this configuration, and security groups.
resource "azurerm_role_assignment" "platform_rg_rbac" {
  scope                = azurerm_resource_group.platform.id
  role_definition_name = "User Access Administrator"
  principal_id         = azurerm_user_assigned_identity.platform.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "platform_state_rbac" {
  scope                = local.tfstate_container_scope
  role_definition_name = "User Access Administrator"
  principal_id         = azurerm_user_assigned_identity.platform.principal_id
  principal_type       = "ServicePrincipal"
}

data "azuread_application_published_app_ids" "well_known" {}

data "azuread_service_principal" "msgraph" {
  client_id = data.azuread_application_published_app_ids.well_known.result["MicrosoftGraph"]
}

# Application.Read.All: refresh its own Graph state (service principals,
# app-role assignments) when CI plans as this identity.
resource "azuread_app_role_assignment" "platform_appread" {
  app_role_id         = data.azuread_service_principal.msgraph.app_role_ids["Application.Read.All"]
  principal_object_id = azurerm_user_assigned_identity.platform.principal_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

# Group.ReadWrite.All: create solution viewer groups and manage memberships.
# Tenant-wide by nature — an enterprise would scope this with administrative units.
resource "azuread_app_role_assignment" "platform_groups" {
  app_role_id         = data.azuread_service_principal.msgraph.app_role_ids["Group.ReadWrite.All"]
  principal_object_id = azurerm_user_assigned_identity.platform.principal_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

# Read/write Terraform state — container-scoped, nothing else in the account.
resource "azurerm_role_assignment" "platform_state" {
  scope                = local.tfstate_container_scope
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.platform.principal_id
  principal_type       = "ServicePrincipal"
}

# --- groups that scope tenant settings and capacity rights --------------------
# Membership is additive (azuread_group_member), so members added outside this
# configuration — a person, another team's automation — are left alone.

resource "azuread_group" "automation" {
  display_name     = local.automation_group
  mail_nickname    = replace(local.automation_group, "-", "")
  security_enabled = true
}

resource "azuread_group" "creators" {
  display_name     = local.creators_group
  mail_nickname    = replace(local.creators_group, "-", "")
  security_enabled = true
}

resource "azuread_group_member" "platform_automation" {
  group_object_id  = azuread_group.automation.object_id
  member_object_id = azurerm_user_assigned_identity.platform.principal_id
}

resource "azuread_group_member" "platform_creators" {
  group_object_id  = azuread_group.creators.object_id
  member_object_id = azurerm_user_assigned_identity.platform.principal_id
}
