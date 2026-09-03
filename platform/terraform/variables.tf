variable "subscription_id" {
  description = "Subscription that holds the capacity, identity and resource group."
  type        = string
}

variable "location" {
  description = "Azure region for everything the platform creates."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group holding the capacity and platform identity."
  type        = string
}

variable "capacity_name" {
  description = "Fabric capacity name: 3-63 lowercase letters/digits, starts with a letter."
  type        = string
}

variable "capacity_sku" {
  description = "Fabric capacity size, F2 upwards. Resizing is just changing this value."
  type        = string
  default     = "F2"
}

variable "capacity_admins" {
  description = "UPNs (or service principal object IDs) administering the capacity."
  type        = list(string)
}

variable "budget_amount" {
  description = "Monthly USD budget for the resource group."
  type        = number
  default     = 25
}

variable "budget_email" {
  description = "Where budget alerts go."
  type        = string
}

variable "budget_start_date" {
  description = "First day of the month the budget starts, e.g. 2026-09-01T00:00:00Z."
  type        = string
}

variable "github_repository" {
  description = "owner/name of this repository — the OIDC trust anchors to it."
  type        = string
}

variable "github_owner_id" {
  description = "Numeric ID of the repository owner (gh api users/<owner> --jq .id)."
  type        = string
}

variable "github_repository_id" {
  description = "Numeric ID of the repository (gh api repos/<owner>/<name> --jq .id)."
  type        = string
}

variable "platform_identity_name" {
  description = "Name of the managed identity CI runs the control plane as."
  type        = string
  default     = "mi-fabric-platform"
}

variable "tfstate_subscription_id" {
  description = "Subscription of the Terraform state storage account."
  type        = string
}

variable "tfstate_resource_group" {
  description = "Resource group of the state storage account."
  type        = string
}

variable "tfstate_storage_account" {
  description = "State storage account name."
  type        = string
}

variable "tfstate_container" {
  description = "State container name."
  type        = string
}

locals {
  # GitHub's OIDC subject embeds immutable IDs: owner@owner_id/name@repo_id.
  # The IDs protect the trust against account/repo rename-and-recreate attacks.
  github_oidc_repo = format("%s@%s/%s@%s",
    split("/", var.github_repository)[0], var.github_owner_id,
    split("/", var.github_repository)[1], var.github_repository_id)

  # Naming standard, not configuration (docs/quickstart.md step 4 relies on these).
  automation_group = "grp-fabric-automation"           # scopes the SPN-API and GitHub tenant settings
  creators_group   = "grp-fabric-workspace-creators"   # gets Contributor permissions on the capacity

  tfstate_container_scope = "/subscriptions/${var.tfstate_subscription_id}/resourceGroups/${var.tfstate_resource_group}/providers/Microsoft.Storage/storageAccounts/${var.tfstate_storage_account}/blobServices/default/containers/${var.tfstate_container}"
}

variable "fabric_use_cli" {
  description = "Authenticate the Fabric provider with the local Azure CLI (true locally; CI sets false and uses OIDC)."
  type        = bool
  default     = true
}
