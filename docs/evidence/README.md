# Evidence

Every consequential claim in this repository was tested against a live Fabric
tenant before being built on, and each test left a dated, immutable record here.
Files reference register IDs (E-numbers for evidence rows, S-numbers for spikes)
from the project's working notes; the files themselves carry the full context.

| File | What it settles |
|---|---|
| `2026-08-31-trial-spikes.md` | The foundation: service-principal parity across item types, Git round-trips, orphan control, rename/restore semantics, dbt adapters, deploy timings |
| `2026-09-02-s27-oidc-workspace-create.md` | Workspace creation via OIDC with capacity *contributor* rights only; GitHub's immutable-ID subject format |
| `2026-09-02-solution-module.md` | Tree-derived solutions live; CI plans as the platform identity; the paused-capacity planning quirk |
| `2026-09-02-first-deploy.md` | Bundle → fabric-cicd publish as a managed identity; reusable-workflow and tenant-level-login gotchas |
| `2026-09-03-dbt-marts.md` | The full data path as the deploy identity: OneLake seed, OPENROWSET staging, tested marts |
| `2026-09-03-item-type-coverage.md` | Fabric's item catalog vs fabric-cicd — the basis for the project's scope |
| `2026-09-03-serve.md` | Hand-authored Direct Lake + PBIR served; the executeQueries-for-service-principals wall, confirmed exhaustively |
| `2026-09-03-promotion.md` | One bundle byte-identical through dev → test → prod behind approvals; the GitHub Deployments ledger |
| `2026-09-03-operate.md` | A second solution and its cross-solution shortcut contract live; the Viewer-lacks-OneLake-read over-grant; the production heartbeat with a live Spark run |
| `2026-09-03-torture.md` | The solution attacked on purpose: live failure probes, an adversarial review, a cold read of the docs, and the Microsoft-guidance alignment audit — with what was fixed and what stays sharp |
| `2026-09-03-clean-slate-adopter-run.md` | The whole platform destroyed and rebuilt from nothing by following the quickstart as a stranger — the soft-deleted-group trap, and per-solution provenance found and fixed live |
