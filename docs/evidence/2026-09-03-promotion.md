# Step 8 — promotion: one bundle, three environments, two approvals

**Date** 2026-09-03 · **Runs** build 33706260199 (bundle source), promote 33706468218 (test + prod)

## What was proven

- **Build once, deploy many, literally.** Bundle `sales-2ae0e6f4…` was built once on
  merge, deployed to dev, then promoted to `ws-sales-test` and `ws-sales-prod` —
  the digest verified identical at every hop, nothing rebuilt. 19/19 dbt tests
  (including the not-empty smokes) passed in each environment.
- **Approval gates work.** The `sales-test` and `sales-prod` GitHub environments
  each paused the run for the repository owner's review; approvals released them
  one environment at a time. Every deployment now lands in GitHub's Deployments
  ledger automatically — the "what is where" record, no tags needed.
- **Environment-scoped OIDC replaced the interim branch credentials.** Deploy jobs
  now run under `environment: <solution>-<env>` subjects; the temporary
  `refs/heads/main` federated credentials on deploy identities were destroyed in
  Terraform (1 resource) the same day the environments arrived.
- **Provenance is enforced**: `promote.yml` refuses run IDs whose build didn't
  conclude green, and derives the artifact name from the run's own commit SHA.

## Rollback

The mechanism *is* the promotion path: `promote.yml` pointed at an earlier green
run re-deploys that bundle (the cross-run artifact download it depends on is the
same one both of tonight's promotions used). Definitions roll back; data never
travels between workspaces.

## Design note

Every environment seeds the same committed sample bytes at deploy time — the
demo's stand-in for per-environment ingestion. Promotion moves definitions only.
