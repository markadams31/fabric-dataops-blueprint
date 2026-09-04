# Fabric CI/CD tooling, and the choices this repository made

Microsoft explains *why* CI/CD matters and what goes wrong without it better than a
repository README can, so start there: [What is CI/CD in Microsoft Fabric?](https://learn.microsoft.com/fabric/cicd/cicd-overview)
for the landscape, and [CI/CD concepts and best practices](https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd)
for the reasoning in depth.

This page covers what those pages leave to you: which tool to pick, what each one
carries, and which trade-offs this repository accepted.

## What's available

| Tool | What it does | Where it fits |
|---|---|---|
| [Git integration](https://learn.microsoft.com/fabric/cicd/git-integration/intro-to-git-integration) | Connects a workspace to a branch; commits items to Git and updates the workspace from it | Source control, and the basis of *branch out to workspace* |
| [Deployment pipelines](https://learn.microsoft.com/fabric/cicd/deployment-pipelines/intro-to-deployment-pipelines) | Chains workspaces into stages and copies items between them, in the portal or by API | Lowest-effort promotion |
| [fabric-cicd](https://microsoft.github.io/fabric-cicd/) | Python library that publishes item definitions from a folder into a workspace | API-driven release from a repository |
| [Fabric CLI](https://learn.microsoft.com/rest/api/fabric/articles/fabric-command-line-interface) (`fab`) | Filesystem-like CLI over the Fabric APIs; `fab deploy` wraps fabric-cicd | Scripted operations, no Python needed |
| [Terraform provider](https://registry.terraform.io/providers/microsoft/fabric/latest/docs) | Creates workspaces, capacities, roles, connections, workspace identities | Infrastructure as code |
| [Variable libraries](https://learn.microsoft.com/fabric/cicd/variable-library/variable-library-overview) | Environment-specific values in an item, one value set per environment | Parameterisation |
| [Job scheduler](https://learn.microsoft.com/fabric/fundamentals/job-scheduler) | Runs items on a schedule; also a REST API | Triggers |
| [Activator](https://learn.microsoft.com/fabric/real-time-hub/tutorial-orchestrate-jobs-with-job-events) | Reacts to Fabric job and OneLake events and starts other items | Event-driven orchestration |
| [Apache Airflow job](https://learn.microsoft.com/fabric/data-factory/cicd-apache-airflow-jobs) | Managed Airflow inside Fabric | Complex DAG orchestration |
| [Bulk Import Item Definitions](https://learn.microsoft.com/rest/api/fabric/core/items/bulk-import-item-definitions) (beta) | Imports many item definitions in one call, resolving dependency order itself | The other way to do an API-driven release |
| [Fabric REST APIs](https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/item-definition-overview) | Everything above, underneath | What you fall back to |

## What the platform carries, and what you carry

This is the single most useful thing to understand, and the source of most confusion.
**An item definition is the item's content, not everything about the item.** A data
pipeline's definition is `pipeline-content.json` plus `.platform` — that is all. Its
schedule, its permissions and its sensitivity label are separate platform state.

Git integration serialises *more* than the definition into the item folder (that is
where `.schedules` comes from), and deployment pipelines copy items at the workspace
level. The definition API — which fabric-cicd uses — carries content only. So the same
words mean different things depending on which tool you picked:

| | Deployment pipelines | Git integration | API-driven (this repo) |
|---|---|---|---|
| Item content | carried | carried | carried |
| Schedules | carried | carried (`.schedules`) | carried — see below |
| Same-workspace item references | [auto-bound](https://learn.microsoft.com/fabric/cicd/cross-workspace-dependency-binding) | auto-bound | auto-bound |
| Cross-workspace references | deployment rules | **you** | **you** (`parameter.yml`) |
| Workspaces, roles, capacity | not carried | not carried | **you** (Terraform) |
| Testing before production | none | none | **you** |

Nothing here is a defect. It is the trade every team makes: the more the platform
carries, the less you control.

**One row is measured rather than documented.** Microsoft's
[job scheduler page](https://learn.microsoft.com/fabric/fundamentals/job-scheduler)
says that on the public API you manage schedules by code, which reads as though
schedules do not travel with a definition. They do: a `.schedules` file in the item
folder is published by fabric-cicd as a definition part and Fabric applies it —
verified here against a notebook, including varying `enabled` per environment through
`parameter.yml`. This repository relies on that behaviour, so it is worth re-checking
after a library upgrade.

## Choosing

Microsoft's [Choose the best Fabric CI/CD workflow option for you](https://learn.microsoft.com/fabric/cicd/manage-deployment)
sets out four options. Condensed:

| Option | Source of truth | Branching | Deployment mechanism | Per-stage configuration |
|---|---|---|---|---|
| 1 — Git integration | Git | Gitflow, a primary branch per stage | Fabric Git APIs (`update-from-git`) | Separate per-stage branches |
| **2 — Fabric Items APIs** | Git, a single `main` | Trunk-based | Items APIs: fabric-cicd or Bulk Import | **Build-environment scripts** |
| 3 — Deployment pipelines | The `dev` workspace | Trunk-based | Deployment pipelines APIs | Deployment rules and auto-binding |
| 4 — ISV, many customer workspaces | Git, a single `main` | Trunk-based | Items APIs, per customer workspace | Per-customer release parameters |

**This repository is Option 2**, which is worth knowing before reading further: a single
`main`, stage workspaces that are not connected to Git, and a build environment that
transforms item definitions before they are uploaded. Microsoft's page is the map; this
one says which turns were taken and why.

Four questions decide which option is yours. They are about requirements, not tools.

1. **Where does truth live — a workspace or the repository?** If the answer is the `dev`
   workspace, Option 3 is a good fit and much less work. If it must be the repository,
   Options 1, 2 or 4.
2. **Must changes be tested before production?** Neither Git synchronisation nor a
   deployment pipeline runs tests in transit. If a gate matters, the release passes
   through a CI runner — which is what a *build environment* is.
3. **Does anything outside Fabric take part?** Transformation in dbt, infrastructure in
   Terraform, an artefact store — each pulls towards Option 2, because Fabric can only
   schedule and orchestrate what lives inside it.
4. **How many teams?** One team with a handful of reports has no scaling problem and
   should not build one. This machinery pays off when solutions and reviewers multiply.

A rough rule: 
- Portal-first, report-centric, one team → **Option 3**. 
- Repository-first, tested, multi-team → **Option 2**.
- **Option 1** sits between them, and its cost is that each stage gets its own long-lived branch, so changes move by cherry-pick and environments drift apart. 
Microsoft's own closing note is worth repeating: many organisations take a hybrid approach, and you are not obliged to pick exactly one.

## What this repository chose

| Decision | What else was possible | Why this | What it costs |
|---|---|---|---|
| **API-driven release** with fabric-cicd | Deployment pipelines; Git synchronisation | The repository is the source of truth, changes are tested in transit, and item coverage is whatever the library supports | Schedules, cross-workspace references and platform state become your job |
| **Terraform** for workspaces, identities and access | Portal setup; `fab` scripts | Access and existence are reviewable in a pull request, and a solution becomes a folder | The provider is young, and it refuses to plan against a paused capacity |
| **Build once, promote the bundle** | Rebuild in each stage's build environment, which is what Option 2 describes | The bytes proven in dev are the bytes that reach production | The build environment is Microsoft's idea; the *immutability* is ours, so nothing in their tooling models an artefact — and Actions artefacts expire after 90 days |
| **No workspace is connected to Git** | Option 2 connects `dev` to Git for authoring; only `test` and `prod` are disconnected | Every environment is built by identical machinery, so `dev` cannot drift from the repository | Fabric's *branch out to workspace* has no Git-connected workspace to branch from, so developers connect one themselves |
| **Managed identities with OIDC** | Service principal with a client secret | No secret exists to leak, rotate or forget | Federated subjects are fiddly, and some APIs still refuse service principals |
| **`parameter.yml` and a variable library** | A variable library alone | Semantic-model TMDL cannot read a library, and `notebookutils.variableLibrary` has no service-principal support | Two mechanisms to learn instead of one |
| **Schedules in the item's own `.schedules` file** | A custom declaration applied through the Job Scheduler API, which is what this repository did first | Fabric's own format, which it both writes and reads, published with the definition; per-environment `enabled` is a `parameter.yml` rewrite | Undocumented on this path, so it rests on a measured result; and Fabric auto-disables a scheduler after roughly ten consecutive failures |
| **dbt in GitHub Actions** | The dbt job item; notebooks; pipelines | Tests, lineage, and validation that needs no cloud | Fabric emits no job event when the marts are rebuilt, so event-driven orchestration is unavailable |
| **Repository guards at pull-request time** | Rely on deploy-time failure | Catches silent classes — a renamed mart that freezes a consumer's data fails no deploy | Code to maintain that Microsoft does not supply |
| **Shared capacity, one Terraform state** | A capacity and a configuration per environment, [as Microsoft recommends](https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd) | Cost, for a demonstration | No noisy-neighbour isolation, and a wider blast radius on a bad apply |

Terminology, mapped once: what this repository calls a **solution** is the guidance's
*Fabric CI/CD project*; **promote** is its *release process*; the **bundle** is this
repository's own addition, which the guidance's release options do not have.
