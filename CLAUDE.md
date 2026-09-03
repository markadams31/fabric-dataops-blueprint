# Maintainer notes

Internal knowledge for working on this repository. Adopter-facing documentation
lives in README.md and docs/ — nothing here is needed to *use* the blueprint.

## Working on the repo

- Gates before any push: `uv run ruff check .` · `uv run pytest -q` ·
  `uv run python deploy/guards.py`. The `validate` check is required by the
  protect-main ruleset and there is no bypass — everything lands through a PR.
- Solutions, matrices and identities derive from `solutions/*/` folders (names
  must match `[a-z][a-z0-9-]+`). Never hand-maintain a list a derivation rule
  already produces.
- Docs trail code: nothing is documented before it exists and has been run
  live. The test behind every load-bearing claim goes in `docs/evidence/` as a
  dated, immutable file.
- Mermaid on GitHub strips `<...>` as HTML — write literal angle brackets as
  `#60;` / `#62;`. Diagram colour vocabulary: gold = source of truth / the
  bundle, green = writable by you, blue = pipeline-owned.
- ruff excludes `*.Notebook` (Fabric injects runtime globals); the guards skip
  local dbt artefacts (`target/`, `logs/`, `.user.yml`, `__pycache__`).

## Platform sharp edges (all live-verified)

- The capacity must be Active for deploys, dbt, and even Terraform *plans*
  (the fabric provider refuses to plan against a paused capacity). Use the
  capacity workflow; its pause defers while deploys are in flight.
- Deploy identities cannot see the capacity in `GET /capacities`, so deploy.py
  cannot preflight its state — a paused capacity surfaces as fabric-cicd's
  `CapacityNotActive` after a ~300-second retry ceiling.
- New-solution provisioning order: merge the folder → platform-terraform apply
  (gated) → re-run `platform/scripts/github-setup.sh` → re-run the build. The
  first build after the merge always fails; that is the seam, not a bug.
- Federated-credential and group-membership changes propagate in ~2 minutes —
  retry the apply before debugging.
- `executeQueries` is 401 for every service-principal type in this tenant with
  every documented switch satisfied; smoke tests are dbt singular tests instead.
- Workspace Viewer does not confer OneLake read: the cross-solution contract
  grant is Contributor — a documented over-grant with a watch-list row.

## Operating notes

- Nightly: production heartbeat 18:00 UTC (resume → ingest → dbt → issue on
  failure); capacity pause 20:00 UTC. ~US$0.36/hour while Active — pause
  whenever idle.
- Single-maintainer demonstration repo: approvals are self-approvals, and the
  repository is disposable by design.

## Evidence register (condensed)

The full dated lab notes were retired from the tree (they age badly); the
durable facts live here, and the originals remain in git history. What each
round of live testing settled:

- **Trial spikes (08-31):** service principals publish every item type
  identically to users; fabric-cicd matches items by displayName+type, so a
  rename is a new item; recycle-bin restore preserves item IDs; a full-scope
  publish of ~19 items runs ~14 min (Environment ≈400 s, UDF has a re-publish
  cooldown); OPENROWSET over OneLake works under a service principal.
- **OIDC workspace-create (09-02):** GitHub's federated subjects embed immutable
  IDs (`owner@id/repo@id`) — classic-format credentials fail AADSTS700213;
  capacity *contributor* rights (via group) suffice to create workspaces.
- **First deploy (09-02):** a reusable workflow's caller job needs
  `id-token: write` itself; deploy identities hold zero Azure RBAC — log in
  tenant-level with `allow-no-subscriptions`.
- **Data path (09-03):** OneLake DFS upload and T-SQL staging both work as a
  managed identity; dbt-fabric authenticates via CLI tenant-level.
- **Scope (09-03):** the repo covers fabric-cicd's ACCEPTED_ITEM_TYPES plus dbt;
  most excluded item types are undeployable by any tool.
- **Serve (09-03):** `deploy_with_config` needs `core.parameter` explicitly;
  dynamic attributes are `$`-prefixed (`$items.<Type>.<name>.$sqlendpoint`);
  skip explicit Direct Lake refresh right after warehouse writes — it reframes
  on query.
- **Promotion (09-03):** bundles verified byte-identical dev → test → prod;
  rollback is the same workflow pointed at an earlier run.
- **Operate (09-03):** the Job Scheduler runs notebooks as a managed identity;
  cross-solution reads need the Contributor contract grant.
- **Torture + clean-slate rebuild (09-03):** the whole platform was destroyed
  and rebuilt from nothing following the quickstart; both solutions promoted
  through prod. Traps that round found: tenant settings render **soft-deleted
  groups as healthy-looking chips** for 30 days (permissions silently dead);
  brand-new service principals 404 on group-add for ~2 min (re-apply); a
  sibling solution's red must not gate promotion (provenance is per-solution).
