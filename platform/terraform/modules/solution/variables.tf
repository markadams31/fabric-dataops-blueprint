variable "name" {
  description = "Solution name — the folder name under solutions/."
  type        = string
  validation {
    # No hyphens: a solution name becomes a GitHub variable name
    # (AZURE_CLIENT_ID_<NAME>), and those cannot contain them.
    condition     = can(regex("^[a-z][a-z0-9]{1,30}$", var.name))
    error_message = "Solution names are lowercase letters, digits and hyphens, starting with a letter."
  }
}

variable "capacity_id" {
  description = "Fabric capacity GUID the workspaces run on."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the solution's deploy identity."
  type        = string
}

variable "location" {
  description = "Region for the deploy identity."
  type        = string
}

variable "github_oidc_repo" {
  description = "owner@owner_id/name@repo_id — GitHub's immutable-ID OIDC form."
  type        = string
}

variable "automation_group_id" {
  description = "Object ID of grp-fabric-automation (scopes the SPN tenant settings)."
  type        = string
}

variable "platform_group_id" {
  description = "Object ID of grp-fabric-platform — Admin on every managed workspace."
  type        = string
}
