# 2026-08-31 — Live spikes on the trial capacity (FT1, Australia East)

All resources are disposable and named `zz-spike-*`. Identity under test: service principal `dp-ref-airflow-spn`
(appId d17839d8-…, objectId 2bf898ea-…) with a client secret — a stand-in for the OIDC managed identity
(same principal type in Fabric). Comparison identity: user `fabric@…` via `az login`.

Tooling: fabric-cicd 1.3.0, terraform 1.16 + microsoft/fabric 1.13.0, Python 3.12 (uv), sample item
definitions from microsoft/fabric-cicd `sample/workspace` (MIT).

## Changes made to the tenant (log)

| When (UTC+10) | Change | Why | Revert |
|---|---|---|---|
| 13:35 | Workspaces `zz-spike-01-spn-coverage` (aba28230…), `zz-spike-02-upn-coverage` (d5f6f76f…), `zz-spike-03-git` (57741b5e…) on the trial | spike targets | delete workspaces |
| 13:38 | SPN `dp-ref-airflow-spn` → Member on 01, Admin on 03 | deploy identity; Git connect needs Admin | remove role |
| 13:44 | Tenant setting `GitHubTenantSettings` → **enabled** (whole org) | required for any GitHub Git integration | admin portal → Git integration → off |
| 13:44 | GitHub repo `markadams31/zz-fabric-spike` (private) | Git-integration target | `gh repo delete` |
| 13:5x | Workspaces `zz-spike-04-*`, `zz-spike-05-delete`, `zz-spike-loop-00..09` created and deleted (sit in the admin `Deleted` list for the retention window) | control-plane / loop spikes | expire automatically |
| 14:0x | SPN granted `User` on the existing `AzureBlobs` sample connection (via Terraform `fabric_connection_role_assignment`, state in `spike/tf-conn/`) | connection-sharing spike | `terraform destroy` in `spike/tf-conn/` |
| 14:1x | Workspace identity provisioned on `zz-spike-03-git` | control-plane spike | deleted with the workspace |
| 14:2x | Workspaces `zz-spike-06-bulk`, `zz-spike-07-standard` (c0a6f040…, 2f5f7db2…) | scope/bulk timing | `teardown.py` |
| — | Items inside spike workspaces: sample items, `PBIRSample` report, `DirectLakeProbe` model, dbt schema `dbt_spike`, OneLake file `Files/probe/rows.csv`, Delta table `probe_rows`, a Daily schedule on `Hello World` | spikes | deleted with the workspaces |
| — | **Left ON deliberately:** tenant setting `GitHubTenantSettings` (needed by the reference architecture anyway) | — | admin portal if unwanted |

## Spike 1.1 — item-type coverage, SPN vs user (fabric-cicd `publish_all_items`, one type per call)

| Item type | SPN | User | Note |
|---|---|---|---|
| Lakehouse (×2, one schema-enabled) | ✅ 20 s | ✅ 38 s | |
| Warehouse | ✅ 6 s | ✅ 11 s | **No `PrincipalTypeNotSupported`** — the proposal's §6.6/§15.5 fear does not reproduce at fabric-cicd 1.3.0 |
| SQLDatabase | ✅ 36 s | ✅ 36 s | |
| VariableLibrary | ✅ 8 s | ✅ 8 s | |
| SemanticModel (TMDL) | ✅ 18 s | ✅ 18 s | |
| Report (PBIR, `byPath`) | ✅ 3 s | ✅ 3 s | rebinding to same-workspace model worked |
| Notebook | ✗ ordering | ✗ ordering | `Cannot replace logical ID … referenced item (Environment) is not yet deployed` — harness ordered Environment last; re-run pending |
| DataPipeline | ✗ ordering | ✗ ordering | depends on the notebook above; re-run pending |
| SparkJobDefinition | ✗ ordering | ✗ ordering | re-run pending |
| CopyJob | ✗ | ✗ | generic API error (`An error occurred while processing the operation`) — sample references a connection that doesn't exist here |
| UserDataFunction | ✅ 116 s | ✅ 116 s | |
| DataBuildToolJob | ✅ 6 s | ✅ 5 s | fabric-cicd supports the native dbt-job item |
| ApacheAirflowJob | ✅ 16 s | ✅ 17 s | sample has `dags/` inside the item definition |
| Environment (with libraries) | ✅ **401 s** | ✅ 411 s | the slow one — publish waits for the library build |
| DataPipeline (re-run after Environment/Notebook existed) | ✅ 8 s | ✅ 7 s | |
| SparkJobDefinition (re-run) | ✅ 9 s | ✅ 9 s | |

| CopyJob (re-run after repointing its destination `artifactId` from `Diabetes_LH`'s logicalId to `WithoutSchema`'s) | ✅ 8 s | ✅ 9 s | the earlier failure was an unresolvable logicalId in the sample, not a connection or identity problem |

**Verdict for Spike 1.1: no identity-specific gap found — 13 of 13 sampled types publish under the SPN exactly as
under the user.** `PrincipalTypeNotSupported` never appeared. Every failure seen was an ordering or sample-reference
artefact and reproduced identically for the user.

Corroboration: fabric-cicd logs (client side) + `GET /v1/admin/items?workspaceId=…` (service side) — the admin
listing shows every SPN-deployed item with `creatorPrincipal = dp-ref-airflow-spn`, i.e. **the deploy identity is the
item owner** (feeds §18.5 / keep-alive runbook).

Also observed: fabric-cicd 1.3.0 has a **single** `ACCEPTED_ITEM_TYPES` list — there are no separate UPN/SPN
lists in the source; the proposal's claim (§6.6, §9) is outdated.

## Spike 1.3 — `fabric_workspace_git` with a service principal (Terraform)

- Provider 1.13.0 docs: *"This resource supports Service Principal authentication only when `git_credentials.source` is
  `ConfiguredConnection`"* — GitHub requires `ConfiguredConnection`; the proposal's "not supported for SPN" is outdated.
- Provider also has `fabric_connection_role_assignment`, `fabric_gateway`, `fabric_gateway_role_assignment`,
  `fabric_apache_airflow_job` (all "supports Service Principal authentication").
- Config written and validated (`tf-git/main.tf`). **Blocked**: creating the GitHub source-control connection with the
  `gh` CLI OAuth token returned `400 … Unexpected PAT detected. Please provide a valid GitHub PAT (classic or
  fine-grained)`. Fabric↔GitHub needs a real PAT — a long-lived secret, held per developer for personal workspaces.
  Needs a PAT from Mark to continue (fine-grained, scoped to `zz-fabric-spike`, Contents read/write).

## Semantic model refresh + definition export as the SPN (zz-spike-01)

- `POST …/datasets/{id}/refreshes` as the SPN → 202; status `Completed / ViaApi`. Dataset `configuredBy` = the SPN's
  object ID → **the deploying SPN owns the model and can refresh it** (§16 #13: owner = deploy identity).
- `getDefinition` as the SPN works for Report and SemanticModel. Report came back with `definition.pbir` rewritten to
  **`byConnection`** (fabric-cicd converts `byPath` on deploy — the REST asymmetry the proposal describes is real) and
  with **`report.json`** — i.e. the fabric-cicd sample reports are **PBIR-Legacy**; the export format follows the
  imported format (sticky). The repo's own sample report must be authored as PBIR or the format-lock gate rejects it.
- SemanticModel export = `definition.pbism` + TMDL `definition/` (7 files) — TMDL survives REST round-trip.
- `.platform` `logicalId` in REST exports of REST-created items is all zeros — logical IDs are a Git-integration
  concept; fabric-cicd resolves references by the repo's `.platform` IDs at deploy time.

## Spike 1.7 / 2.7 — T-SQL, OneLake and OPENROWSET as SPN vs user (tsql.py)

| Step | SPN (Member, ws 01) | User (Admin, ws 02) |
|---|---|---|
| OneLake DFS upload of a CSV to `Files/` | ✅ 201/202/200 | ✅ |
| Load-table API → Delta `probe_rows` (non-schema lakehouse) | ✅ Succeeded | ✅ |
| pyodbc + Entra token to the Warehouse, `SELECT 1`, `SUSER_SNAME()` | ✅ returns `d17839d8-…@tenant` | ✅ |
| **`OPENROWSET(BULK 'abfss://…/Files/probe/rows.csv')`** | **✅ 3 rows** | ✅ 3 rows |
| `refreshMetadata` on the lakehouse SQL endpoint | ✅ 200, **1.6 s**, synchronous, per-table status | ✅ 2.0 s |
| 3-part read `[WithoutSchema].[dbo].[probe_rows]` | first attempt: snapshot-isolation DDL error (transient), OK on retry 15 s later | same |

**Contradicts the 2026-08-25 evidence** ("OPENROWSET over OneLake fails under SPN"). Conditions differ: here the SPN is
Member and created the lakehouse; there it was Contributor on `dp-ref-dev` reading dlt JSONL from a schema-enabled
lakehouse. **Reproduction against `dp-ref-dev` (SPN = Contributor, schema-enabled `lh_bronze`, dlt JSONL files):
OPENROWSET also succeeds today** — `airflow_markers/preflight.json` and two `_dlt_loads/*.jsonl` files returned rows
under `SUSER_SNAME() = d17839d8-…`. **Corrected belief (2026-08-31):** OPENROWSET over OneLake works for a service
principal with a workspace role; the 2026-08-25 failure had another cause (candidates: `.gz` output, token audience
inside the Airflow worker, a since-fixed platform issue). The all-T-SQL Bronze→Silver path from Actions is viable.
Design consequence: put a retry around the first cross-database read after `refreshMetadata`.

Coverage update: **UserDataFunction ✅ (116 s), DataBuildToolJob ✅, ApacheAirflowJob ✅** for both SPN and user.

## Control-plane facts as the SPN

- `POST /workspaces` with the **trial** capacity as the SPN → **403 `InsufficientPermissionsOverCapacity`** — confirms
  a trial cannot grant a service principal capacity rights; the Terraform control plane under a managed identity needs
  the F2. (Without a capacity the SPN *can* create a workspace — 201 — deleted immediately.)
- `GET /workspaces/{id}/recoverableItems` → 200 (empty) — **item recovery is enabled** in this tenant
  (`ConfigureArtifactRetentionPeriod` = on), so the retire/restore spike is possible.
- Variable Library after fabric-cicd deploy with `environment="PPE"`: `activeValueSetName = "PPE"` — **value-set
  activation by environment works** as the proposal assumes (§8).

## Spike 1.2 — orphan control vs an out-of-repo lakehouse (SPN, ws 01)

`TfLakehouse` (stand-in for Terraform) and `StrayNotebook` created via REST, then `unpublish_all_orphan_items` with
scope `[Lakehouse, Notebook]`:

| Flags | Result |
|---|---|
| defaults | `Skipping unpublish for Lakehouse items because the 'enable_lakehouse_unpublish' feature flag is not enabled` — **lakehouse kept**; `StrayNotebook` **deleted** |
| `enable_lakehouse_unpublish` | `TfLakehouse` deleted |

→ §6.4's Terraform-vs-orphan loop exists only when the per-type flag is on. The guard becomes "these flags stay off in
test/prod" plus the type exclusion; non-data items (notebooks, pipelines, variable libraries…) ARE deleted by default.

## Spike 2b.1 / 2b.2 — rename, retire, restore (user on ws 02; SPN on ws 01)

- Renaming the **folder** `Vars.VariableLibrary` → `Vars2.VariableLibrary` changed nothing: fabric-cicd published
  `Vars` (display name comes from `.platform`), same item ID.
- Changing `metadata.displayName` in `.platform` to `Vars2` (same `logicalId`) → fabric-cicd published a **new item
  `Vars2` (new ID d97aaf2f…)** and orphan-deleted `Vars`. **fabric-cicd matches by display name + type, not by
  logicalId.** A rename is delete + create; every reference, schedule and share on the old item is lost.
- `GET /recoverableItems` listed the deleted `Vars`; `POST …/recover` → 202; it returned **with its original ID**
  (9381e0f3…) alongside `Vars2` → the duplicate-identity situation the docs warn about, reproduced.
- As the **SPN (Member)** on ws 01: recycle bin listed `StrayNotebook`, `TfLakehouse` (+ its SQLEndpoint child);
  recover → 202 for both parents, IDs preserved; the child endpoint answers 409 `InvalidTargetItemStateForRecovery`
  (restored with its parent). Member can restore, as documented.

## Notebook rebinding, schedules, hard delete (SPN, ws 01)

- With a trimmed `parameter.yml` (regex on the `# META "default_lakehouse"` / `default_lakehouse_workspace_id` lines
  → `$items.Lakehouse.WithoutSchema.id` / `$workspace.id`, plus `$items.Lakehouse.WithoutSchema.sqlendpoint`), the
  deployed `Example Notebook` META shows **the target lakehouse ID (cf4d0da5…) and workspace ID** and the SQL endpoint
  host — **fabric-cicd parameterisation rebinding works** (§8 fallback path, independent of Fabric's preview
  auto-binding). The deployed definition has only `notebook-content.py` + `.platform` (no `notebook-settings.json`).
- **Schedule persistence (§16 #13):** a Daily `RunNotebook` schedule created as the SPN (`owner = ServicePrincipal
  2bf898ea…`) **survived a fabric-cicd redeploy** of the notebook; the item ID stayed the same (update-in-place).
  So schedules are stable across deploys and owned by whoever created them — the deploy identity if `post_deploy.py`
  creates them.
- **`enable_hard_delete` as Member:** two stray notebooks were unpublished with the flag; neither appeared in
  `recoverableItems` → hard delete **worked for a Member**, although fabric-cicd's docs say it requires Admin.
  Treat the flag as dangerous at Member level too; keep it off outside spike workspaces.

## Spike 2.1 / 2.2 — dbt adapters as the SPN

| Target | Adapter | Auth | Result |
|---|---|---|---|
| Warehouse `Default` (SPN-created, ws 01) | dbt-fabric 1.11.1 / dbt-core 1.12.3 | `authentication: environment` (AZURE_CLIENT_ID/TENANT_ID/CLIENT_SECRET) | `dbt debug` **OK** (5 s); `dbt run` created view `dbt_spike.probe_model` **OK** (5 s total) |
| Warehouse `Default` (ws 02) | dbt-fabric 1.11.1 | `authentication: CLI` (user after `az login`) | `dbt debug` **OK** (3.6 s) |
| Lakehouse `WithoutSchema` via Livy | dbt-fabricspark 1.13.2 | `authentication: spn` (+ `spark_config.name` is a required key; `schema` must equal the lakehouse name on a non-schema lakehouse) | `dbt debug` **OK in 54 s**; `dbt run` of one trivial view: **79 s**, second run **82 s** — a new Livy session per invocation, ~60–70 s of pure session overhead on the trial. **Reproduces the "Livy tax"**; supports one adapter in the core. |

## Spike 2b.4 — connection sharing to the deploy identity (Terraform)

- Before: the SPN's `GET /connections` returned **0** connections (the tenant has 7 as the user).
- `fabric_connection_role_assignment` (provider 1.13, user CLI auth) granted `User` to the SPN on the existing
  `AzureBlobs` sample connection: **Creation complete after 1 s**; user view shows Owner + User.
- After: the SPN `GET /connections/{id}` → 200 and its list shows exactly that connection.
→ Connection permissions are a real, separate grant; Terraform can do it (the `connections` module gets a
  `for_each` role assignment for `mi-fabric-deploy` and the workspace identity). Creating a `Web`/`Anonymous`
  connection via provider or REST needs a different creation-method shape than I guessed — parked.

## Workspace identity and the native dbt-job item (SPN)

- `POST /workspaces/{id}/provisionIdentity` as the SPN (Admin on ws 03) → 202 → **Succeeded**; the workspace now
  has `workspaceIdentity {applicationId, servicePrincipalId}`. Terraform can own workspace identities under the MI.
- The fabric-cicd-deployed `DataBuildToolJob` definition is only `dbt-content.json` + `.platform`; **the dbt project
  itself is stored in OneLake, outside the item definition**. `POST …/jobs/instances?jobType=Execute` as the SPN →
  202 → **Failed: "Failed to download dbt project from OneLake"**. Deploying the item via fabric-cicd therefore does
  not deploy the dbt code — a separate OneLake upload step would be needed. Strong evidence for "dbt runs from the
  repo in Actions", against the Fabric-native dbt-job alternative for a Git-sourced pipeline.

## Hand-authored PBIR report (no Desktop) — SPN deploy + export

A minimal PBIR definition written by hand (`definition.pbir` v4 `byPath` → `../ABC.SemanticModel`; `definition/`
with `version.json`, `report.json`, `pages/pages.json`, `pages/page1/page.json`; `.platform` with a fresh
`logicalId`) published via fabric-cicd as the SPN in **2 s** and `getDefinition` returned exactly the PBIR tree
(`definition/version.json`, `definition/report.json`, `definition/pages/…`, no `report.json`). → The repo can ship a
true-PBIR sample authored in the repo; Power BI Desktop is only needed to test *round-trip fidelity* of Desktop saves.

## Spike 11 — dbt full-refresh vs a Direct Lake model (SPN deploys; queries as user)

- Hand-authored **Direct Lake on SQL** model (`compatibilityLevel 1604`, `expression DatabaseQuery = Sql.Database(<server>,
  <warehouse id>)`, partition `mode: directLake`, `schemaName: dbt_spike`, `entityName: probe_model`) over the dbt table
  in the SPN-created warehouse: fabric-cicd publish as SPN **18 s**; frame (refresh) as SPN → **Completed**.
- `EVALUATE probe_model` via `executeQueries`: as the **user** → rows; as the **SPN → 401 `PowerBINotAuthorizedException`**
  although tenant setting `DatasetExecuteQueries` is enabled for everyone. Open item for the DAX smoke test under the
  MI (XMLA/semantic-link or an app-permission fix); re-test on the F2.
- `dbt run --full-refresh` (table dropped and recreated with v2 rows) → DAX immediately after: **stale v1**; **~20 s
  later: v2 (2 rows) with no reframe call** (automatic updates on by default); explicit refresh → Completed, v2.
  → Full-refresh does not break Direct Lake; it leaves a stale window of seconds. The pipeline should still call
  refresh after dbt (§8 step 5) to make the cut-over deterministic and observable.

## Spike 16 — ten personal-workspace create/destroy loop (user, trial)

10 × `POST /workspaces` (trial capacity): all 201, **8–10.5 s each, 94.5 s total, no throttling, no `Retry-After`**;
10 × `DELETE`: all 200, 0.2–0.3 s each; re-creating the same display name immediately after deletion → 201. The
deleted workspaces sit in the admin `Deleted` list for the retention window. → Ephemeral personal workspaces are
viable; the reaper must tolerate the Deleted-state backlog (they're not visible to `GET /workspaces`).

## Scope completeness and bulk publish (SPN, fresh workspaces 06/07)

- `enable_bulk_publish` **requires `enable_experimental_features`** in fabric-cicd 1.3.0 — bulk mode is experimental,
  not a default.
- A single invocation with 13 types **but Environment excluded** failed in both bulk and standard mode at the same
  point: `Cannot replace logical ID 'a277ea4a…' (the Environment) as referenced item is not yet deployed` — after
  ~175 s, with 9 items already created. **fabric-cicd resolves `logicalId` references only among items in the same
  invocation's scope.** A narrowed scope therefore breaks references, not just orphan control — the stronger argument
  for §8's "one pass, full scope".
- Re-running the full scope 3 minutes later failed in **17.7 s** with `DeployCooldownBlock: Please wait 55 second(s)
  before publishing again` on the **UserDataFunction** — Fabric enforces a per-item publish cooldown for UDFs (and
  possibly other types). fabric-cicd does not wait it out; the deploy job needs a retry-after-cooldown, and two
  deploys to the same environment within a minute will collide (another reason for per-environment `concurrency`).
- **Full-scope single invocation, 14 types / 19 items (mostly updates), as the SPN: OK in 857 s (≈14 min)** — the
  Environment (library build, ≈400 s) and the UserDataFunction (≈116 s) dominate; everything else is seconds.
  Budget ≈15 min per environment for a small workspace with an Environment item; without one, ≈3–4 min.

## Spike 2b.5 — workspace delete and restore (user, API only)

`zz-spike-05-delete` created with a notebook → `DELETE /workspaces/{id}` → `GET /admin/workspaces?state=Deleted`
lists it → **`POST https://api.powerbi.com/v1.0/myorg/admin/groups/{id}/restore`** (`name`, `emailAddress`) → 200 →
workspace back with the **same ID**, the notebook intact and the capacity assignment retained. **Restore is
API-driven (Power BI admin API), not portal-only** — corrects the fact-check.

→ For CI the runner needs only `pip install dbt-fabric` and either `azure/login` + `CLI`, or the AZURE_* variables +
`environment` (with OIDC, `environment` would need a federated token file — `CLI` after `azure/login` is simpler).

## Git integration spikes (PAT obtained by driving GitHub's UI; connection `zz-spike-github`)

- **GitHub connection**: `POST /connections` type `GitHubSourceControl`, credential `Key` = fine-grained PAT (repo
  `zz-fabric-spike` only, Contents R/W, 7 days) → 201 with test-connection on. The `gh` OAuth token had been rejected
  (`Unexpected PAT detected`). SPN granted `User` on the connection.
- **Directory must pre-exist**: `git/connect` (user) with `directoryName: "/ws03"` (absent) → `GitProviderResourceNotFound`;
  with `"/"` → 200. After committing `ws03/.gitkeep` and `ws02/.gitkeep`, both `/ws03` and `/ws02` connected. Terraform
  hits the same error with a missing folder.
- **Spike 1.3 — `fabric_workspace_git` as the SPN (Terraform 1.13, `ConfiguredConnection`)**: `Creation complete after
  11s`; `git/connection` as the SPN = `ConnectedAndInitialized`, GitHub / `main` / `/ws03`. **PASS** — the proposal's
  §6.5 "user-context only" is outdated.
- **Export (user, ws 02 → branch `spike/ws02`, `/ws02`)**: connect 200 → `initializeConnection` = `CommitToGit` required →
  `commitToGit` Succeeded in 65 s for 17 items. Fabric assigned fresh `logicalId`s. Formats: Report = **PBIR-Legacy
  (`report.json`) with `byPath`** (REST had shown `byConnection` — the asymmetry is real); SemanticModel = TMDL;
  **Warehouse and SQLDatabase export as `.sqlproj`**; DataPipeline includes a **`.schedules`** file; Lakehouse =
  `alm.settings.json` + `lakehouse.metadata.json` + `shortcuts.metadata.json`; Environment = wheel + `environment.yml` +
  `Sparkcompute.yml`; ApacheAirflowJob = `apacheairflowjob-content.json` + `dags/`; Notebook = `.platform` +
  `notebook-content.py` only (no `notebook-settings.json` — auto-binding off by default).
- **Round-trip Git → workspace**: a comment added inside a cell of `Example Notebook` in Git → `updateFromGit`
  (`PreferRemote`) **Succeeded in 12 s**; `getDefinition` shows the edit in the workspace.
- **All-or-nothing**: my first edit appended text after the JSON-bodied sample notebook → `GitSyncFailed /
  PyToIPynbFailure` and **the whole update was rejected** (the other item's valid change did not apply either) until
  the file was restored. Commit is also refused while the remote is ahead ("one direction at a time" confirmed).
- **PBIR via Git**: the hand-authored PBIR report deployed to ws 02, `commitToGit` Succeeded in 12 s, export =
  `definition.pbir` v4 + `definition/{version,report,pages/…}.json` → **PBIR round-trips through Git integration**.

## Notebook auto-binding (docs, verified 2026-08-31)

- "Lakehouse auto-binding in Git" is **preview**, **off by default**, enabled per notebook in *notebook settings*; Fabric
  then writes `notebook-settings.json` and the docs say **do not edit it by hand** — the proposal's "add it to the
  scaffolding template" must change to "enable in settings / via definition on creation, then commit what Fabric writes".
- Official per-item-type binding matrix (learn.microsoft.com/fabric/cicd/cross-workspace-dependency-binding): semantic
  model → SQL endpoint / Warehouse / SQL DB **never auto-binds** (connection strings carry workspace-specific URLs);
  Report → model `byPath` = partial; Pipeline → SJD / semantic-model refresh / warehouse endpoint = no; Variable Library
  `ItemReference` = no; connections never bind. fabric-cicd's `$items.<Type>.<name>.sqlendpoint` / `.id` tokens are the
  parameterisation for exactly those rows.
