# Maintainer notes

Internal knowledge for working on this repository. Adopter-facing documentation
lives in README.md and docs/ — nothing here is needed to *use* the blueprint.

## Working on the repo

- Gates before any push: `uv run ruff check .` · `uv run pytest -q` ·
  `uv run python deploy/guards.py`. The `validate` check is required by the
  protect-main ruleset and there is no bypass — everything lands through a PR.
- Solutions, matrices and identities derive from `solutions/*/` folders (names
  must match `[a-z][a-z0-9]+` — no hyphens, because the name becomes a GitHub
  variable name). Never hand-maintain a list a derivation rule
  already produces.
- Docs trail code: nothing is documented before it exists and has been run
  live. What each round of live testing settled goes in the evidence register
  below, not into dated files in the tree.
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
  grant is Contributor — a documented over-grant with a watch-list entry below.

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
- **Team-scale run (09-04):** a third solution was added, promoted and retired
  while the other two kept running. Seven defects, all fixed and all only
  visible at three solutions or under a rollback:
  - Fabric refuses a second role for a workspace's *creator*, so granting the
    platform identity Admin directly failed for every solution CI provisions —
    the first two worked only because a human created their workspaces. The
    grant goes through `grp-fabric-platform` now.
  - A medallion solution has more than one lakehouse; `lh_bronze` is the name
    the tooling depends on, and other lakehouses are free-form.
  - A producer renaming a dbt mart leaves the old table behind, so the
    consumer's shortcut keeps resolving and its data freezes — green
    everywhere, wrong forever. A guard now resolves the producer from the
    contract's placeholder and checks the model still exists.
  - GitHub stamps a deployment with the ref the workflow ran from, so a
    rollback recorded today's main. Promote records the promoted bundle as a
    deployment status; the schedule reads that.
  - Local dbt artefacts (`target/`, `logs/`, `.user.yml`) kept a retired
    solution's folder alive, and a local plan proposed recreating everything
    that had just been destroyed.
  - Retirement left GitHub environments and an `AZURE_CLIENT_ID_*` behind,
    pointing at a deleted identity. `github-setup.sh` prunes them.
  - A transient Fabric API timeout crashed a deploy with a raw traceback; list
    calls retry.
  A data pipeline — an item type never deployed here before — published with no
  code change, which is the extensibility claim holding up. What was not
  retested: two builds dispatched at once (the schedule-versus-promote
  collision was, and serialised correctly).
- **The GitHub provider setting needs the developers too (09-04):** connecting a
  branched workspace to a branch fails with `FeatureNotAvailable` — "the tenant
  administrator has not enabled the specified Git provider type" — unless the
  person doing it is in a group the *Users can sync workspace items with GitHub
  repositories* setting is scoped to. Scoping it to `grp-fabric-automation` alone
  covers the pipeline but locks out every human who would author in a branched
  workspace. The error names no setting, so this is minutes of confusion for an
  adopter.
- **Branched workspace, tested end to end (09-04):** PAT → Fabric connection →
  `git/connect` → `initializeConnection` → `updateFromGit` → `commitToGit`, all by
  API. Blockers found, in order: the GitHub tenant setting scoped to automation
  only; a Warehouse folder holding just `.platform` (`MissingItemDefinitionFiles`,
  refuses the whole directory); and a parameterised `.schedules`
  (`InvalidArtifactJobSchedulerException` — Fabric validates the schema, so a
  placeholder where a boolean belongs is fatal). After that it syncs, but reports
  items Modified with no edit made: Fabric writes no trailing newline and rewrites
  `.schedules` line endings, so a commit is whitespace noise. Git integration did
  NOT split the semantic model's TMDL even though `getDefinition` does — the two
  serialisers differ, and the earlier round-trip note conflated them.
- **Portal round-trip fidelity via getDefinition (09-04):** `getDefinition` on our own deployed items
  shows what authoring in a workspace would commit back. Notebooks, reports and
  variable libraries are clean. A lakehouse gains `alm.settings.json`. A notebook
  with a schedule gains `.schedules` — so a schedule *is* part of what the
  definition API returns, even though fabric-cicd ignores it; whether publishing
  one back applies it is untested. The semantic model splits its expression out of
  `model.tmdl` into `expressions.tmdl` with the author's endpoint baked in, which
  silently breaks `parameter.yml`'s rewrite — now caught by a guard. Warehouses and
  SQL endpoints have no definition at all (`OperationNotSupportedForItemType`).
- **What the library already does (09-04):** `item_type_in_scope` defaults to
  every accepted type, so passing a list is redundant; `deploy_with_config`
  raises on failure and returns `DeploymentStatus.completed` otherwise;
  `FabricWorkspace` resolves a workspace by name. Two things that look like
  wins are not: the library's git-diff change detection cannot work on a
  bundle (a bundle has no git history, and promotion deploys an old one), and
  moving demo seeding into the ingestion notebook relocates code rather than
  removing it — deploys would then have to wait on a Spark session.
- **Schedules as code (09-04):** a `.schedules` file in the item folder is
  published by fabric-cicd as a definition part and Fabric applies it — verified by
  deleting a notebook's schedule, deploying, and seeing it return with the declared
  interval. Per-environment `enabled` works through a `parameter.yml` rewrite of
  `"SCHEDULE_ENABLED"`. This contradicts Microsoft's matrix, which says the public
  API means managing schedules by code; an earlier custom `schedules.yml` mechanism
  was built on that assumption and then deleted. Note Fabric auto-disables a
  scheduler after roughly ten consecutive failures, which is why the sales schedule
  ships disabled while the capacity pauses.
- **Torture + clean-slate rebuild (09-03):** the whole platform was destroyed
  and rebuilt from nothing following the quickstart; both solutions promoted
  through prod. Traps that round found: tenant settings render **soft-deleted
  groups as healthy-looking chips** for 30 days (permissions silently dead);
  brand-new service principals 404 on group-add for ~2 min (re-apply); a
  sibling solution's red must not gate promotion (provenance is per-solution).

## Watch list

Upstream changes that should trigger a design revisit — check when bumping tool
versions.

| What | Where | Trigger | Response |
|---|---|---|---|
| TMDL-aware `key_value_replace` for semantic models | [fabric-cicd #552](https://github.com/microsoft/fabric-cicd/issues/552) (PR open) | Ships in a release | Use it for the semantic model's `expressions.tmdl` rewrite instead of `find_replace` |
| Validate-only / dry-run mode | [fabric-cicd issues](https://github.com/microsoft/fabric-cicd/issues) | Ships | Add to `pr-validation` as a cloud-free publish check |
| Schedule pause/resume around deployments | fabric-cicd feature request | Ships | Consider adopting in the deploy phase before prod schedules exist |
| Full-Lakehouse / Warehouse-schema deployment | fabric-cicd feature requests | Ships | **Do not adopt blindly** — would overlap dbt's ownership of the warehouse (one owner per store) |
| `deploy_with_config` | [config-based deployment](https://microsoft.github.io/fabric-cicd/latest/how_to/config_deployment/) | When orphan control / per-environment publish differences land here | Candidate replacement for the publish block in `deploy.py` |
| `executeQueries` for service principals | Power BI REST API | Tenant behaviour changes (currently 401 for ALL SPN types here, every documented switch satisfied) | Reinstate a DAX smoke against the semantic model in `deploy.py` |
| Finer-grained OneLake read on warehouses | Fabric release notes (OneLake security / item ReadAll via API) | A Terraform-manageable read-only grant appears | Downgrade the cross-solution contract grant from Contributor to it — workspace Viewer does not confer OneLake read |
| PBIR becomes the enforced report format | Fabric release notes | GA (announced Q3 2026) | Format already used here; confirm nothing breaks |
| Fabric Git integration read-write requirement | [Git limitations](https://learn.microsoft.com/fabric/cicd/git-integration/git-integration-process#considerations-and-limitations) | 2026-12-01 | Verify branched-workspace flow for Viewer-only users |
| Delegated branch-out | [CI/CD best practices](https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd) — "Fabric plans to introduce a delegated model to enable self-service branch-out operations for users who don't have permissions to create workspaces or assign a workspace to a Fabric capacity" | Ships | Adopt it: it removes the two tenant grants the portal authoring path currently needs, which is the main reason that path is optional here |
| Workspace item Bulk Import/Export APIs | [Fabric CI/CD announcement](https://community.fabric.microsoft.com/blog/fbc_fabricupdatesblogs/new-cicd-resources-for-microsoft-fabric-from-concepts-to-end-to-end-automation/5358502) (Mar 2026) | GA | Evaluate as a definitions backup/restore mechanism for the README's system-of-record caveat — Microsoft still recommends fabric-cicd for deployment |
