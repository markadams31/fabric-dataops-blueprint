terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    fabric = {
      source  = "microsoft/fabric"
      version = "~> 1.13"
    }
  }

  # Remote state in Azure Storage — the repository's one precondition: bring a state
  # container (see docs/quickstart.md). Partial configuration; the
  # account, container and key come from platform.backend.hcl at init:
  #   terraform init -backend-config=platform.backend.hcl
  #
  # use_azuread_auth is invariant: the backend authenticates to the blob data plane
  # with an Entra token, so the caller needs only Storage Blob Data Contributor on
  # the container — which lets the state account live in a different subscription.
  backend "azurerm" {
    use_azuread_auth = true
  }
}
