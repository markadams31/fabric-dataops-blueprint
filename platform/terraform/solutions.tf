# Solutions are derived from the tree: every folder under solutions/ except
# _template is a solution; creating one is copying the template and merging a PR.
# (A solution.yml override file is planned but nothing reads one yet — conventions only.)

data "fabric_capacity" "platform" {
  display_name = azurerm_fabric_capacity.platform.name
}

locals {
  solutions = toset([
    for f in fileset("${path.module}/../../solutions", "**") :
    split("/", f)[0] if split("/", f)[0] != "_template"
  ])
}

module "solution" {
  source   = "./modules/solution"
  for_each = local.solutions

  name                = each.key
  capacity_id         = data.fabric_capacity.platform.id
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  github_oidc_repo    = local.github_oidc_repo
  automation_group_id = azuread_group.automation.object_id
  platform_principal_id = azurerm_user_assigned_identity.platform.principal_id
}

output "solutions" {
  description = "Per-solution wiring: workspaces and deploy identity."
  value = { for name, m in module.solution : name => {
    workspaces       = m.workspace_ids
    deploy_client_id = m.deploy_client_id
  } }
}

# --- data contracts -----------------------------------------------------------
# Cross-solution access is explicit, versioned configuration: finance reads
# sales' gold through a OneLake shortcut, and shortcuts pass the caller's
# identity through to the target. Empirically, workspace Viewer does NOT confer
# OneLake read (it is a SQL-surface role) — Contributor is today's least
# Terraform-manageable grant that satisfies a shortcut contract to a warehouse.
# That is an over-grant, accepted and documented (see the watch list): the
# consumer identity could write to the producer, and we rely on it not to.
resource "fabric_workspace_role_assignment" "contract_finance_reads_sales" {
  for_each     = module.solution["sales"].workspace_ids
  workspace_id = each.value
  principal = {
    id   = module.solution["finance"].deploy_principal_id
    type = "ServicePrincipal"
  }
  role = "Contributor"
}
