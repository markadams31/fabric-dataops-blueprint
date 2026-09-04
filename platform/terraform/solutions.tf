# Solutions are derived from the tree: every folder under solutions/ except
# _template is a solution; creating one is copying the template and merging a PR.
# (A solution.yml override file is planned but nothing reads one yet — conventions only.)

data "fabric_capacity" "platform" {
  display_name = azurerm_fabric_capacity.platform.name
}

locals {
  # Local build artefacts must not conjure a solution: dbt leaves target/, logs/
  # and .user.yml behind, so a retired folder would still look inhabited to a
  # local plan and be recreated moments after it was destroyed.
  artefact_dirs = ["target", "logs", "dbt_packages", "__pycache__"]

  solutions = toset([
    for f in fileset("${path.module}/../../solutions", "**") : split("/", f)[0]
    if split("/", f)[0] != "_template"
    && length(setintersection(toset(split("/", f)), toset(local.artefact_dirs))) == 0
    && basename(f) != ".user.yml"
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
  platform_group_id   = azuread_group.platform.object_id
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
#
# Measured 2026-09-04, and it closes the obvious escape route. OneLake security
# roles look like the answer and are not: the item type is unsupported. Calling
# GET .../items/<warehouse>/dataAccessRoles returns HTTP 400
# UniversalSecurityFeatureDisabledForArtifactType, "Universal security feature is
# disabled for the artifact type 'Warehouse'", while the identical call against
# this solution's lakehouse returns 200 and its DefaultReader role. Item-level
# sharing is closed too: Microsoft documents warehouse sharing as UI-only and
# states that sharing a warehouse directly with a service principal is not
# supported. So Contributor is not laziness — it is the only grant that both
# reaches OneLake and can be declared.
# Both ends must exist: a contract disappears with either side of it, so
# retiring a solution stays a folder deletion.
resource "fabric_workspace_role_assignment" "contract_finance_reads_sales" {
  for_each = (contains(tolist(local.solutions), "sales")
    && contains(tolist(local.solutions), "finance")
  ) ? module.solution["sales"].workspace_ids : {}
  workspace_id = each.value
  principal = {
    id   = module.solution["finance"].deploy_principal_id
    type = "ServicePrincipal"
  }
  role = "Contributor"
}
