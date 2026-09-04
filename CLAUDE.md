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
  grant is Contributor — a documented over-grant. Both narrower alternatives were
  tried and are closed (see the evidence register); it is the minimum grant that
  both reaches OneLake and can be declared in Terraform.

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
- **Portal round trip, measured end to end (09-04):** a report was edited in the
  portal of a feature workspace synced from a branch, then committed. The diff is
  exactly the edit — a new page directory plus an updated `pages.json` — and the
  semantic model was **not touched at all**, which confirms by commit what was
  previously inferred from `getDefinition` and the Git serialiser disagreeing.
  Fabric's additions are uniform: every file it writes loses its trailing newline,
  compact JSON returns pretty-printed (`version.json`), and `.schedules` line endings
  are rewritten — byte-different, identical parsed. With no edit at all only
  `lh_bronze` and `nb_ingest_orders` report Modified; report, semantic model and
  variable library stay clean. **The finding that matters more than any of that: a
  synced workspace is not a deployed one.** Git sync does not run fabric-cicd, so
  `parameter.yml` never executes and `model.tmdl` lands with the literal
  `Sql.Database("SALES_WAREHOUSE_ENDPOINT", "SALES_WAREHOUSE_ID")`. The semantic
  model's editor will not open and the report cannot bind its model. A feature
  workspace is good for a report's layout and for running a notebook; nothing that
  must resolve a connection can be authored there.
- **The Contributor over-grant cannot currently be narrowed (09-04):** the
  cross-solution contract shortcuts finance's lakehouse at sales' *warehouse*, and
  both obvious replacements are closed. `GET .../items/<warehouse>/dataAccessRoles`
  returns HTTP 400 `UniversalSecurityFeatureDisabledForArtifactType`; the same call
  against the lakehouse returns 200 with its `DefaultReader` role, which is the
  control that makes the negative meaningful. OneLake security roles list Lakehouse,
  Azure Databricks mirrored catalog, mirrored databases and mirrored catalogs — no
  Warehouse. Item-level `ReadAll` would be exactly the right permission ("read
  warehouse data through OneLake APIs and Spark") but warehouse sharing is UI-only
  and Microsoft states plainly that sharing a warehouse with a service principal is
  not supported. The watch-list row that said *adopt* was wrong for this shape and
  now says so; delegated shortcuts are the replacement to wait for.
- **The GitHub provider setting needs the developers too (09-04):** connecting a
  feature workspace to a branch fails with `FeatureNotAvailable` — "the tenant
  administrator has not enabled the specified Git provider type" — unless the
  person doing it is in a group the *Users can sync workspace items with GitHub
  repositories* setting is scoped to. Scoping it to `grp-fabric-automation` alone
  covers the pipeline but locks out every human who would author in a feature
  workspace. The error names no setting, so this is minutes of confusion for an
  adopter.
- **Feature workspace, tested end to end (09-04):** PAT → Fabric connection →
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

One terminology decision is worth recording so it does not get re-litigated. Microsoft uses
**feature workspace** for the general pattern — a developer's own isolated workspace on a
feature branch — and **branched workspace** for the specific capability that creates one via
*Branch out*, with the parent link, breadcrumbs and Related Branches tab. The
[best-practices page](https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd)
carries both under separate headings. Since no workspace here is Git-connected, branch-out is
unavailable and what this repository documents is a feature workspace. Using their word for
their feature, and their other word for ours, is the whole of the convention.

## Untested claims

The evidence register says what was measured. This says what the repository asserts or
relies on that has *not* been, so a reader can tell the difference. Audited 2026-09-04.

| Claim | Where it appears | Status |
|---|---|---|
| ~~A report or semantic model edited **in the portal** commits back cleanly~~ | — | **Closed 2026-09-04.** Measured: a portal report edit commits back as exactly that edit, and the semantic model is untouched by the commit. The semantic model turned out not to be authorable in a feature workspace at all, for a different reason — see the evidence register |
| Power BI Desktop is a usable authoring path | `path-to-production.md` lists it, now with the caveat inline | Never exercised. No Windows here, and the Windows-in-Docker spike was dropped. Desktop save fidelity for a hand-authored PBIR is unknown |
| The Fabric Data Engineering VS Code extension edits locally and runs on remote Spark | `path-to-production.md` offers it as the notebook alternative | Taken from Microsoft's documentation, not run here |
| `executeQueries` works for a service principal with the Power BI audience and the Power BI SP switch | Watch list | The 401 was measured against the *Fabric* switch. The retest was never run; dbt singular tests are the smoke path meanwhile |
| Publishing a `.schedules` returned by `getDefinition` applies it | Evidence register notes it | Publishing a *hand-written* `.schedules` was verified. Round-tripping one was not |
| The Git APIs accept a service principal | Nothing depends on it; recorded as resolved doc contradiction | The specs mark the operations conditionally supported. Every Git call this repository has made ran as a user |
| Two builds dispatched simultaneously serialise correctly | Implied by the per-solution concurrency groups | The schedule-versus-promote collision was tested and serialised. Two concurrent builds were not |
| The feature-workspace alternatives work — provision-on-request, or Terraform-declared per-developer workspaces | `portal-authoring.md` offers both | Designs, not implementations. Neither has been built |
| Delegated shortcuts remove the need for the Contributor contract grant | Watch list, as the replacement to wait for | Preview, and untested here. The claim rests on Microsoft's description |

Two things worth saying about this table. It is deliberately not a defect list — several rows
are fine to leave open on a demonstration repository, and closing them all would cost more
than it returns. And the first row is the one that matters, because the documentation sends
people down that path.

## Watch list

Upstream changes that should trigger a design revisit — check when bumping tool
versions.

| What | Where | Trigger | Response |
|---|---|---|---|
| TMDL-aware `key_value_replace` for semantic models | [fabric-cicd #552](https://github.com/microsoft/fabric-cicd/issues/552) (PR open) | Ships in a release | Use it for the semantic model's `expressions.tmdl` rewrite instead of `find_replace` |
| Validate-only / dry-run mode | [fabric-cicd issues](https://github.com/microsoft/fabric-cicd/issues) | Ships | Add to `pr-validation` as a cloud-free publish check |
| Schedule pause/resume around deployments | fabric-cicd feature request | Ships | Consider adopting in the deploy phase before prod schedules exist |
| Full-Lakehouse / Warehouse-schema deployment | fabric-cicd feature requests | Ships | **Do not adopt blindly** — would overlap dbt's ownership of the warehouse (one owner per store) |
| Warehouse Git integration | **Already shipped, in preview** — [commits the warehouse as a DacFx database project](https://learn.microsoft.com/fabric/data-warehouse/git-integration) of `.sql` files. Its own limitations page lists no selective commits, no SQL-analytics-endpoint version control, and SQL permissions needing separate export | Leaves preview | **Still do not adopt** — this is the same one-owner-per-store collision, now real rather than hypothetical: DacFx would own the schema dbt owns. The forum reports no way to exclude warehouse files from Git tracking once a workspace is connected, so the two cannot easily coexist. Relevant only if dbt ever leaves |
| `deploy_with_config` | [config-based deployment](https://microsoft.github.io/fabric-cicd/latest/how_to/config_deployment/) | When orphan control / per-environment publish differences land here | Candidate replacement for the publish block in `deploy.py` |
| `executeQueries` for service principals | Power BI REST API | **Re-test before assuming a wall**: this is a *Power BI* API needing the `analysis.windows.net/powerbi/api` audience and the *Power BI* SP switch — a different setting from the Fabric one we enumerated. Documented fallback if it still fails: query the SQL analytics endpoint with Entra auth, where SP support is explicit | Reinstate a DAX smoke against the semantic model |
| Finer-grained OneLake read | **Tried and blocked, measured 2026-09-04.** OneLake security roles are GA but [support only Lakehouse, mirrored databases and mirrored catalogs](https://learn.microsoft.com/fabric/onelake/security/data-access-control-model#permissions-and-supported-items) — not Warehouse, which is what our contract shortcut targets. Item-level sharing is closed as well: warehouse sharing is [UI-only and not supported for service principals](https://learn.microsoft.com/fabric/data-warehouse/share-warehouse-manage-permissions#limitations) | Warehouse becomes a supported item type, **or** [delegated shortcuts](https://learn.microsoft.com/fabric/onelake/shortcuts/create-onelake-shortcut) leave preview | Delegated shortcuts are the real replacement — a fixed identity on the shortcut means the consumer needs no grant on the producer at all. Until then Contributor stays, and the reason is now recorded in `solutions.tf` rather than implied |
| PBIR becomes the enforced report format | Fabric release notes | GA (announced Q3 2026) | Format already used here; confirm nothing breaks |
| Fabric Git integration read-write requirement | [Git limitations](https://learn.microsoft.com/fabric/cicd/git-integration/git-integration-process#considerations-and-limitations) | 2026-12-01 | Verify feature-workspace flow for Viewer-only users |
| Warehouse definition REST API | Fabric roadmap — "Create, Get, Update warehouse definition REST API", target Q3 2026, GA: *provision a warehouse initialised from a definition payload supporting Dacpac and SQL project* | Ships | **Do not adopt blindly** — it would make fabric-cicd a second owner of warehouse schema, which dbt owns. Relevant only if dbt ever leaves |
| Transaction support for Git integration and deployment pipelines | Fabric roadmap — target Q4 2026, GA: atomic deploys with automatic rollback, "no partial state" | Ships | Revisit the documented "deployment is not atomic" limit in path-to-production |
| File-level commit | Fabric roadmap — target Q3 2026, public preview | Ships | Would let a feature-workspace commit exclude Fabric's whitespace-only churn |
| Bulk Import/Export item definitions | Fabric roadmap — target Q3 2026, GA (beta today, `?beta=true`) | GA | Closest native shape to our bundle. Wait for GA: adopting at beta means changing call sites twice |
| Associate an identity with items and schedules | Fabric roadmap — target Q4 2026, public preview; [beta API today](https://learn.microsoft.com/rest/api/fabric/articles/item-management/associate-item-identity) | Ships | Removes the deploy-identity-owns-the-item problem and the 30-day owner keep-alive concern |
| Tenant settings by API | [Update Tenant Setting](https://learn.microsoft.com/rest/api/fabric/admin/tenants/update-tenant-setting) — preview, "not recommended for production", SP and MI supported | Leaves preview | Would make the quickstart's portal step scriptable, removing the only manual step in setup |
| Delegated branch-out — named **"Branch workspace admin profile"** on the roadmap | Learn states the commitment with **no date**; the only dated source is the roadmap feed (**Q3 2026**, public preview), whose quarters are explicitly at-risk — *lets developers use branch-out without needing create-workspace or assign-capacity permissions; admins pre-configure guardrails — developer role, capacity assignment, admin list* | Ships | Adopt it: it removes the two tenant grants the portal authoring path currently needs, which is the main reason that path is optional here |
| Item types whose APIs refuse service principals | Machine-readable: every operation in [`microsoft/fabric-rest-api-specs`](https://github.com/microsoft/fabric-rest-api-specs) carries an identity table in its `description`. Of 729 operations, 55 answer **No** — the whole CRUD surface of MLModel, MLExperiment, User Data Functions, Anomaly Detector, Digital Twin Builder, Event Schema Set and Operations Agent, plus admin bulk sensitivity-label set/remove | Adding one of those item types to a solution | **This is a live edge for us.** `item_type_in_scope` is omitted, so fabric-cicd deploys all 29 types — a solution that adds one of these fails as the deploy MI with no gate catching it first. Verify against the specs before adding an item type, not after |
| Spark runtime default changes under us | [Runtime 2.0](https://learn.microsoft.com/fabric/data-engineering/runtime-2-0) — Spark 4.1, Python 3.13, Delta 4.2 — becomes the default for the UX and for new workspaces in **late September 2026**; Runtime 1.3 leaves support 2026-09-30 | That date | No Environment item and no runtime pin exist here, so `nb_ingest_orders` moves when the default moves. The exposure is not the notebook but what reads its output: Delta 4.2 features are documented as experimental and Spark-only, and *"if you need to use the same Delta Lake tables across multiple Fabric workloads, don't enable those features"* — which is exactly what this repo does, writing Bronze from Spark and reading it from the warehouse. Run the heartbeat after the switch; leave the new features off |
| Branch out to an *existing* workspace as Contributor | Roadmap: shipped, public preview, Q3 2026 — Contributors can switch branches and branch out to existing workspaces with the setting enabled. Learn carries the switch-branch half as [Change Git branch with Contributor role](https://learn.microsoft.com/fabric/cicd/git-integration/git-integration-process) (July 2026) | Already shipped | Weaker than it sounds for us: branch-out still needs a Git-connected *source* workspace, which no workspace here is. Relevant only alongside the delegated model above |
| Workspace item Bulk Import/Export APIs | [Fabric CI/CD announcement](https://community.fabric.microsoft.com/blog/fbc_fabricupdatesblogs/new-cicd-resources-for-microsoft-fabric-from-concepts-to-end-to-end-automation/5358502) (Mar 2026) | GA | Evaluate as a definitions backup/restore mechanism for the README's system-of-record caveat — Microsoft still recommends fabric-cicd for deployment |

One fact worth keeping alongside that table, because it closes a question rather
than opening one. The **Fabric dbt job** keeps its project in OneLake rather than in
the item definition, its warehouse adapter accepts only Entra OAuth rather than
service principals, and it has no build caching — three independent reasons dbt stays
in GitHub Actions. That is not a matter of taste; all three are documented limits.

**A correction to an earlier note here: Activator's service-principal support is not
settled, and the claim that it has none came from the weaker source.** The swagger spec
and Activator's own REST reference page both answer Yes; only the
[item-type matrix](https://learn.microsoft.com/rest/api/fabric/articles/item-management/item-management-overview),
last dated 2025-03-25, says otherwise — and it disagrees with the reference pages on
Mirrored Database and Mirrored Azure Databricks Catalog too. Event-driven orchestration
on Activator is therefore an open option, not a closed one, and worth a live test before
either claim goes in a public document. One caveat survives the correction, and it is the
one that would bite here: Activator items using certain sources and actions
[error outright](https://learn.microsoft.com/fabric/real-time-intelligence/data-activator/activator-limitations)
in a Git-integrated workspace or a deployment pipeline, with support "planned for a future
release". Deployability by a service principal and deployability through CI/CD are separate
questions, and Activator currently answers them differently.

**The Git-API contradiction is resolved, against the page that stated it most plainly.**
The warehouse page claiming *"service principals are not supported for Git APIs"* is the
outlier: the swagger specs that generate Learn's identity tables mark Git Connect, Commit
To Git and Update From Git as *conditionally* supported — the condition being that every
item in the operation supports service principals — and Initialize Connection, Get Status
and Disconnect as supported outright. Two dedicated Learn how-to pages walk through
connecting a workspace as a service principal. The same stale page is wrong in the other
direction as well, since Deploy Stage Content is conditional rather than unrestricted.
Nothing here has been run against those APIs as a service principal, so this repository
still has no first-hand measurement — but the design should not be shaped around a
prohibition that the machine-readable source denies.

One contradiction stays open. CI/CD support for the SQL analytics endpoint was announced
as preview in June 2026, while later-dated warehouse docs say version control for it
"isn't currently available", deployment pipelines "don't support" the item, the roadmap
carries the work as planned for Q4 2026, and it appears in neither supported-items list.
Four first-party sources, three of them against. Verify in-tenant before designing
around it.

**Where roadmap dates come from.** Microsoft retired `learn.microsoft.com/fabric/release-plan/*`
— every URL now redirects to [roadmap.fabric.microsoft.com](https://roadmap.fabric.microsoft.com),
which renders client-side and has no per-feature links, so a roadmap claim can only be
cited to a product page. It carries two orthogonal fields, `ReleaseType` (public preview
or GA) and `ReleaseStatus` (planned or shipped), which is why "Q3 2026 preview" in the
rows above does not mean shipped. Several Q3 2026 items still read *planned* with the
quarter almost over.

A precision worth keeping about variable libraries: an item-reference variable *value*
holds a workspace ID and an item ID, so it can point across workspaces — but the library
itself must live in the same workspace as the items consuming it. The two statements read
as contradictory and are not.
