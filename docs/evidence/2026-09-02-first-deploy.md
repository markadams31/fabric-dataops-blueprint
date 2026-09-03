# Step 4 — first deploy: bundle build → fabric-cicd publish as the deploy identity

**Date** 2026-09-02 · **Runs** build 33611483855 (startup_failure), 33611622773 (deploy auth fail), 33611740044 (pass), 33611917717 (re-deploy pass)

## What was proven

- **Push to `main` fills an empty workspace.** `build.yml` packed `solutions/sales`
  into `sales-<sha>.tar.gz` (content digest + pinned tool versions in
  `release-manifest.json`), and the reusable `deploy-env.yml` published it into
  `ws-sales-dev` — Lakehouse, Warehouse, VariableLibrary, Notebook — in ~40 s of
  fabric-cicd time. Verify confirmed all four bundle items live (5 items total in
  the workspace; the fifth is the warehouse's SQL analytics endpoint).
- **fabric-cicd works as a managed identity** (`AzureCliCredential` after a
  tenant-level OIDC login) — the remaining doubt from the trial spikes, closed.
- **Re-deploying the same bundle is a no-op**: identical digest
  (`24ddbca92cab2e54…`, content-derived so it is stable across builds of the same
  tree), publish over the top, verify green, no duplicates.

## Findings

1. **A caller job must grant what a reusable workflow requests.** `build.yml`'s
   restrictive workflow-level `permissions: contents: read` made the
   `deploy-env.yml` call fail as a `startup_failure` with no jobs and no logs —
   the job calling a reusable workflow needs `id-token: write` itself.
2. **Deploy identities log in tenant-level.** `mi-deploy-<solution>` holds no Azure
   RBAC at all (by design), so `azure/login` fails with "No subscriptions found"
   unless `allow-no-subscriptions: true` — after which `AzureCliCredential` issues
   Fabric tokens normally.
3. **`vars[format('AZURE_CLIENT_ID_{0}', inputs.solution)]` works** — GitHub
   variable lookup is case-insensitive, so lowercase solution names resolve the
   upper-case variable. One variable per solution wires the matrix to the right
   identity.
4. Deferred deliberately: `artefact_store.py` (upload/download-artifact suffices
   until promotion), `parameter.yml` (nothing needs rebinding yet — arrives with
   the semantic model), changed-solution detection (one solution, static matrix).
