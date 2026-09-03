# Clean slate: teardown and a fresh run, the way an adopter would

**Date:** 2026-09-03 · **Context:** with v0.1.0 done, the entire platform was
destroyed and rebuilt from nothing by following the quickstart as a stranger
would — the ultimate test of whether the documentation is the product.

## Teardown

`terraform destroy` removed all 55 resources (the capacity resumed first — the
fabric provider refuses to plan against a paused one). The GitHub repository was
deleted, the state container emptied, and the git history reset to a single
commit. Only the tenant survived: its settings still pointed at the *destroyed*
security groups.

## The run, step by step

| Quickstart step | What happened |
|---|---|
| 1 — Fork and clone | The repo must exist **before** the first apply — the federated credentials embed its immutable ID. The `.example` tfvars documents how to fetch it; validated. |
| 2 — State backend | Pre-existing account, emptied container; nothing else needed. |
| 3 — First apply | Green **on the documented retry**: brand-new service principals 404 when added to groups moments after creation (propagation), and one workspace role assignment hit a transient conflict. Re-apply reconciled 5 resources. |
| 4 — Portal settings | The subtle one — see below. |
| 5 — Harden | `github-setup.sh` ran private → public → re-run. **Finding (fixed in this pull request):** on a free-plan private repo it hard-failed at the test/prod reviewer rule instead of warning like the other Pro-only pieces. verify-oidc then proved the plumbing: token acquisition green immediately, workspace creation refused until step 4 propagated (~10 minutes) — the step ordering is real. |
| 7 — Ship | First build: sales green end-to-end into dev; finance failed exactly at its documented seam (the shortcut contract still pointed at the old tenant's GUIDs). |
| 8 — Promote | Sales promoted `test` → `prod` behind both approvals — after a live fix (below). Finance followed once its contract was rewired by pull request, the documented adopter step. |

## The soft-deleted group trap (step 4)

Destroying Terraform-managed Entra groups leaves tenant settings pointing at
their corpses — and the portal **renders the stale reference as a
healthy-looking chip**, because Entra soft-deletes groups for 30 days and the
name still resolves. Every scoped setting (both service-principal switches, the
GitHub Git provider) and the capacity's contributor permissions had to have the
stale entry removed and the recreated group added. Nothing errors; identities
simply lose the permission until you notice. If your groups ever get recreated,
check the chips.

## Found and fixed live: per-solution provenance

`promote` refused sales' green, dev-proven bundle — because *finance* was red in
the same build run, and provenance judged the whole run. In a multi-solution
repository that means one broken solution freezes every other solution's
promotions. Fixed during the run: provenance now asserts **that solution's own
`deploy-dev` job** succeeded (path, branch and input checks unchanged), matching
the fact that bundles are per solution.

## Verdict

From `terraform destroy` to both solutions promoted through prod on a brand-new
platform: one working session, roughly half of it waiting (tenant-setting
propagation, deploys, dbt). Every failure en route was either documented in
advance — the apply retry, the finance contract seam, the first-build race — or
became a fix shipped mid-run: per-solution promote provenance, and the setup
script's private-repo hard-fail. The quickstart holds: a stranger with a
tenant, a subscription and a laptop gets from fork to a promoted, two-solution
estate with no undocumented step.
