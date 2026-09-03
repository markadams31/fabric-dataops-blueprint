# Step 3 — tree-derived solution module, applied locally and from CI

**Date** 2026-09-02 · **Runs** platform-terraform 33609254010 (fail), 33609889288 (fail), 33610305301 (pass, `No changes`)

## What was proven

- **Tree derivation works end to end**: `solutions/sales/` (a folder, nothing more)
  produced `ws-sales-{dev,test,prod}` with system-assigned identities,
  `mi-deploy-sales` + three environment-scoped federated credentials, Member role on
  its workspaces, `grp-sales-viewers` with Viewer, membership of
  `grp-fabric-automation`. A throwaway `solutions/zz-probe/` folder created 15
  resources and deleting the folder destroyed exactly those 15; final plan clean.
- **CI parity**: `platform-terraform.yml` plans as `mi-fabric-platform` via OIDC
  (no azure/login step needed — azurerm, azuread and fabric providers all consume
  the GitHub OIDC token directly via `ARM_USE_OIDC`/`FABRIC_USE_OIDC`).

## Findings

1. **The Fabric provider refuses to plan while the capacity is paused** —
   `Error: Fabric Capacity State … Inactive Capacity may cause unrecoverable
   damage`. Refreshing any `fabric_workspace` requires an Active capacity.
   Consequence: scheduled Terraform plans (drift checks) must resume the capacity
   first or run inside the window when it is Active; the nightly pause and the
   nightly drift check must be sequenced, not independent.
2. **An identity that runs Terraform must be able to manage what Terraform
   manages.** Runtime rights weren't enough; CI planning needed: User Access
   Administrator at the two scopes whose role assignments Terraform owns (resource
   group + state container), Graph `Group.ReadWrite.All` (create/manage solution
   viewer groups), and Graph `Application.Read.All` (refresh its own app-role
   assignments). All granted *in Terraform itself*, so forks reproduce them.
3. **Workspace Admin must be explicit, not creator-implied.** Workspaces created by
   a local apply (as the human) were invisible to the MI in CI until the module
   assigned the platform identity Admin on every workspace — making local and CI
   applies symmetric.
4. **Transients seen once each, both cured by re-running**: `WorkspaceNameAlreadyExists`
   on a create the service had actually completed, and a fresh identity failing a
   group-membership write before propagation. Consistent with the repo's stance:
   idempotent re-run is the retry mechanism.
