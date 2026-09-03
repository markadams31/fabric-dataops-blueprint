provider "azurerm" {
  subscription_id = var.subscription_id
  features {}
}

provider "azuread" {}

# Fabric control plane. Locally this uses your Azure CLI login; in CI the workflow
# sets FABRIC_USE_OIDC and the provider authenticates as the platform identity.
provider "fabric" {
  use_cli = var.fabric_use_cli
}
