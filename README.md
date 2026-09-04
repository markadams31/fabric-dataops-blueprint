# Fabric DataOps Blueprint

In organisations that adopt modern software practices, the production environment is not a place users can directly edit.  
It is the result of running processes against source code. Change the source, run the processes, and you get a new production.
Most Fabric estates are not operated this way. Instead, changes are made to items in place.

This repository explores the adoption of Microsoft Fabric based on one key principle: **code is the source of truth**.
The beneficial implications that flow from this core foundation include:
- **History.** In the service, an overwritten report is gone. In Git, every version is kept, and restoring one is a redeploy.
- **Consistency.** Every environment is built from the same source.
- **Traceability.** The pull request records who changed what, the reasoning, and who approved it.
- **Reliability.** Changes are tested before reaching production.
- **Scalability.** Adding a team's **solution** — one team's product, with its own workspaces, identity and approvers — is configuration, not a project. The fiftieth runs with the same pipelines, checks, and tests as the first.

This design is intended for large enterprises that want to manage a data estate at scale with confidence.

One caveat: code rebuilds definitions, not data.  Where a table holds history the upstream no
longer has, its state is irreplaceable. Such tables are systems of record and must be protected as such —
[what rolls back and what does not](docs/path-to-production.md#what-rolls-back-and-what-does-not)
says which table in this solution is one and which platform mechanisms exist for it.

## Working against the grain

Fabric's native model is the opposite of this one: **the workspace is the source of truth.**
That is not a habit its users fell into, it is what the primitives do. Git integration
synchronises workspace *state* rather than publishing a build. Deployment pipelines copy
items from one workspace into another. Variables bind at runtime, inside a workspace. An item
definition is, literally, what the portal would have written.

This repository asserts the reverse — the repository is the truth, and a tested artefact moves
between environments — and that single disagreement is where nearly every difficulty in it
comes from. Naming it early is worth more than any individual workaround, because the friction
then stops looking like a series of defects and starts looking like the cost of the position:

- A workspace synced from Git gets **un-parameterised** definitions, because a sync is not a
  deploy. Git hands over the repository's bytes, and those bytes are placeholders.
- Two first-party serialisers disagree about the same item, because one serves the portal
  round trip and the other serves the definition API, and nothing had to reconcile them until
  someone tried to build artefacts from both.
- Warehouse Git integration wants to own the schema as a database project, because the
  platform assumes a workspace owns its warehouse — where here, dbt does.

One limit follows from all of this and is worth stating plainly, because it bounds what the
design can promise. Nothing runs inside Fabric to keep a workspace matching the repository.
Changes are pushed by GitHub Actions when something merges, and if a workspace is edited in
place, nothing notices and nothing converges it back. The repository is the source of truth
by construction and by permission — humans hold Viewer on the shared workspaces — rather than
by continuous enforcement.

The delivery model is worth naming as precisely. **Dev is continuous deployment** — every
merge that passes the gates reaches it unattended. **Test and production are continuous
delivery**: every bundle is releasable, and releasing one is a decision a person makes.

None of those is a defect, and none of them is avoidable while holding this position. They are
the toll, and it is only worth paying when the requirements are real: the repository must be
the source of truth, changes must be tested before production, something outside Fabric takes
part, and more than one team needs isolation. **Where those are negotiable, Fabric's own
tooling is simpler and the better answer** — which is what the next section is for.

## Choosing a release process

Microsoft's guidance names [three ways to release changes to Fabric workspaces](https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd),
and this repository deliberately takes the most involved one.

**Deployment pipelines** — Fabric's native promotion tool. A [deployment pipeline](https://learn.microsoft.com/fabric/cicd/deployment-pipelines/intro-to-deployment-pipelines)
chains workspaces into stages and, on request, copies the items in one stage over the paired items in the
next. It needs no setup beyond the portal, shows a comparison of stages before you deploy, keeps a deployment history,
and can be driven by API. Microsoft positions it as the lowest-effort option that's a good fit for
[small-to-medium projects focused on semantic models and reports](https://learn.microsoft.com/fabric/fundamentals/understand-best-practices-fabric-cicd#how-can-you-automate-fabric-ci-cd).
For a team whose estate is a handful of Power BI items it may be all you need. It falls short of the standard set
out above once an estate grows: the source of truth is the `dev` workspace rather than the repository, nothing is
tested in transit, whoever promotes to production can also edit it, and item coverage is partial — see Microsoft's own
[considerations and limitations](https://learn.microsoft.com/fabric/cicd/deployment-pipelines/understand-the-deployment-process#considerations-and-limitations).

**Git synchronization** — a branch per environment, each workspace updated from its own branch. Everything is
visible in Git, but environments *become* branches: a change travels between them as cherry-picks, drift between
environments returns, and no single tested artefact moves through the stages.

**API-driven** — build once from `main`, then deploy the same immutable **build artefact** to every environment. This repository calls that artefact a **bundle**, and deploys it with
[fabric-cicd](https://github.com/microsoft/fabric-cicd). The source of truth is the repository, changes are tested
in transit, and environments are byte-identical by construction. It is the highest-effort option; paying that cost
well is what the rest of this repository demonstrates.

## The unit of work: a solution

The repository's unit of work is what it calls a **solution** - one team's product with a [`dev` → `test` → `prod` set of
workspaces](docs/path-to-production.md#the-three-workspaces) and one folder under `solutions/`. The platform hosts as many solutions as you need on shared capacity, and
solutions exchange data only through OneLake shortcuts.

| Layer | Per solution | Shared | Owned by |
|---|---|---|---|
| Control plane | Three workspaces (`ws-<solution>-dev/test/prod`), roles, a workspace identity, connections | Capacities, the Terraform module that creates a solution, the platform identity | Terraform, as `mi-fabric-platform` |
| Data plane | A Lakehouse (Bronze), a Warehouse (Silver and Gold), notebooks, one dbt project, semantic models and reports — everything under `solutions/<name>/` | Nothing; a solution never writes into another's workspace | fabric-cicd and dbt, as `mi-deploy-<solution>` |
| Delivery | GitHub environments `<solution>-dev/test/prod` with the team's own reviewers; one build per merge; the same bundle promoted through every environment | The workflows, parameterised by solution; the artefact store | GitHub Actions with OIDC — no stored secrets |
| People | The team holds Viewer on its shared workspaces and authors locally or in a **feature workspace** — Microsoft's term for a developer's own workspace connected to their own branch — of their own; changes land only through a pull request | The break-glass group (PIM) and the platform approvers | Entra groups |

```mermaid
flowchart TB
    CP["Workspaces · roles · identities · connections<br/>Control plane — Terraform, as mi-fabric-platform"]
    subgraph DP ["Data plane — as mi-deploy-#60;solution#62;"]
        I["The items: lakehouse · warehouse · notebooks · semantic model · report<br/>published by fabric-cicd"]
        T["The tables inside the warehouse<br/>built and owned by dbt, and only dbt"]
    end
    CP -->|"creates the workspaces the items live in"| DP
    I -->|"one owner per store"| T
    style CP fill:#eff6ff,stroke:#2563eb
    style DP fill:#f0fdf4,stroke:#16a34a
```

**The warehouse is data plane, and Terraform is deliberately kept out of it.** The provider
*can* manage one — `fabric_warehouse` is generally available — and it is still the wrong
tool, because Terraform's model is convergence and its remedy for a changed immutable
attribute is to replace the resource. For a store holding the only copy of the marts, that
remedy is data loss. This repository already refuses that class of risk elsewhere: orphan
control never deletes data-bearing item types, and hard delete is never enabled. Putting the
warehouse under a tool that can decide to recreate it would contradict the same principle.

So fabric-cicd brings the warehouse into being from a folder holding nothing but a
`.platform` file, and from that moment dbt owns every table in it — **one owner per store**.
Terraform creates the workspace the warehouse lives in, and stops there.

The cost is visible and worth knowing before you meet it. Because the warehouse folder
carries no schema, Fabric's Git integration rejects it — and because Fabric would want to own
that schema itself (as a DacFx database project) if it did, adopting warehouse Git
integration would put a second owner on a store dbt already owns.

Adding a solution is one folder copied from `solutions/_template` — everything else is derived from it.

## How it fits together

```mermaid
flowchart LR
    DEV["Developers"] -->|"pull request"| REPO["GitHub repository<br/>the only source of truth"]
    REPO -->|"merge · promote"| ACT["GitHub Actions<br/>OIDC, no secrets"]
    ACT -->|"as mi-fabric-platform"| TF["Terraform<br/>workspaces · access"]
    ACT -->|"as mi-deploy-#60;solution#62;"| CD["fabric-cicd + dbt<br/>items · tables · tests"]
    TF --> WS["Solution workspaces<br/>dev → test → prod"]
    CD --> WS
    WS --> USERS["Consumers<br/>Viewer"]
    classDef gold fill:#fff8e1,stroke:#f59e0b,stroke-width:2px
    classDef blue fill:#eff6ff,stroke:#2563eb,stroke-width:2px
    class REPO gold
    class WS blue
```

Developers commit and merge changes to the repository, GitHub Actions applies those changes using two identities with two jobs:
- `mi-fabric-platform` creates workspaces and grants access,
- `mi-deploy-<solution>` changes what is inside them.

No human writes to a shared workspace, and a solution's identity can write only to that solution's
workspaces — so a compromised deployment reaches one team's data and no part of the platform. The one
crossing: scheduled operations run as the platform identity, because only it can resume a paused
capacity. It moves *data* on a published definition; it never publishes.

## The same four phases, whatever changed

A solution holds two kinds of thing, in directories named after them: `fabric/` for the items
fabric-cicd deploys — reports, semantic models, notebooks, the lakehouse and warehouse — and `dbt/`
for the transformation project, when the solution has one. A report and a SQL model disagree about
what "build" and "test" mean, so rather than flatten that, every change moves through the same four
phases and each kind does its own work inside them:

- **Validate** — checks that run in the pull request with no cloud access: linting, format locks, report and model rules.
- **Build** — produce the deployable artefact: a bundle of item definitions, a parsed dbt project.
- **Deploy** — apply that artefact to one environment: fabric-cicd publish, `dbt build`.
- **Verify** — prove it worked: item counts, dbt's own tests, smoke queries.

The repository's scope is deliberately the set of items fabric-cicd can deploy, plus dbt for transformation — which
is very nearly the set of things Fabric allows to be deployed as code at all.
The workflows run the phases knowing nothing about the tools inside them: they see directories,
not report editors or SQL compilers.

## Quickstart

From fork to a running platform in eight steps — the first five are a human with a laptop, once; everything after is a pull request.
The walkthrough lives in [docs/quickstart.md](docs/quickstart.md).

## Where things live

```
platform/     Terraform — capacities and the solution module: workspaces, roles, identities, connections
solutions/    one folder per solution: Fabric item definitions, dbt project, deploy config
  _template/  what a new solution starts from
  sales/      the worked example
  finance/    a second solution, reading sales' gold tables through a data contract (a OneLake shortcut)
.github/      CI — one workflow per concern: validate pull requests, build and deploy, platform Terraform
docs/         quickstart · the path to production · the tooling and the choices · authoring in the portal
samples/      synthetic retail data that the whole repository teaches from
```

## Try it without a tenant

Validate and build are cloud-free by construction — that is what makes a pull request cheap. With
`uv` installed you can run the whole offline half in a minute:

```bash
uv sync                                        # pinned toolchain
uv run pytest -q                               # the guards' failing fixtures
uv run python deploy/guards.py                 # the repository guards: pull-request checks
uv run python deploy/build.py --solution sales --sha demo
```

The last command writes `dist/sales-demo.tar.gz` and a `release-manifest.json` whose
`content_digest` is derived from the source alone — build it twice, get the same digest. That
reproducibility is what lets promotion move bytes instead of rebuilding them.

## What it costs

An F2 capacity bills about US$0.36/hour while running and nothing while paused. This repository
pauses nightly and resumes for the scheduled run, which lands it near US$20–25/month; the Terraform
apply includes a budget alert at US$25 as a backstop. Deploys and dbt need the capacity running —
the `capacity` workflow is the resume button.

Reading order: evaluating the design — this page, then [the path to production](docs/path-to-production.md)
for how a change travels and [the tooling and choices](docs/tooling.md) for what else was possible and
what each option costs; adopting it — [the quickstart](docs/quickstart.md); writing a change —
[authoring locally](docs/local-authoring.md) or [in the portal](docs/portal-authoring.md);
maintaining it — the
maintainer notes in [CLAUDE.md](CLAUDE.md).

MIT-licensed. One maintainer, best effort.
