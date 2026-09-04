# Authoring in the portal, on your own branch

Some changes are easier to make in Fabric than in a text editor — a report, a semantic
model, a notebook you want to run interactively. This is how to do that without anyone
editing a shared workspace. If you are still weighing whether you need a workspace at all,
[what you cannot run locally](path-to-production.md#what-you-cannot-run-locally) is the
list that decides it — for dbt work, usually not.

The rule that makes it safe: **writes go to your workspace, reads come from the shared
one.** Nobody can write to `ws-<solution>-dev` — the team holds Viewer there — so your
workspace is where drafting happens, and a pull request is how it becomes real.

## This is not a "branched workspace", and the difference matters

Microsoft's [branched workspace](https://learn.microsoft.com/fabric/cicd/git-integration/branched-workspace)
is a specific thing: a workspace **linked to a source workspace**. You create one with **Branch out to
another workspace** from a Git-connected workspace's Source control pane: Fabric cuts a
new branch from the source workspace's branch, creates the workspace, connects it, and
syncs it — one command. The link it establishes is what gives you the parent in the
workspace tree, breadcrumbs back to the source, and the **Related Branches** tab.

**No workspace here is connected to Git**, so none of that is available. `ws-<solution>-dev`
is a deployment target like test and prod, which is a
[deliberate choice with a cost](tooling.md#what-this-repository-chose), and this is the
cost: there is no source workspace to branch out *from*, so the command does not appear.

What follows is the manual equivalent, and this document calls it a **feature workspace**
to keep the two apart — a workspace you create yourself and connect to your own branch. It
gives the same isolation and the same round trip through Git. It is not a branched
workspace, and saying so matters: if you go looking for **Branch out** you will not find
it, and the Related Branches tab will never appear.

What you give up is the relationship, not the isolation: no parent in the workspace tree,
no breadcrumbs, no Related Branches tab. If you want it later, Microsoft has a preview
[Create Workspace Relation API](https://learn.microsoft.com/rest/api/fabric/core/git/create-workspace-relation)
intended for exactly this case — an automation that prepared the branch, the workspace and
the Git connection itself.

## Before you start

| You need | Why |
|---|---|
| Membership of `grp-fabric-workspace-creators` | It carries workspace-creation rights, and the *Users can sync workspace items with GitHub repositories* tenant setting is scoped to it. Without it, connecting fails with `FeatureNotAvailable` and names no setting |
| A [fine-grained GitHub token](https://github.com/settings/personal-access-tokens/new) with **Contents: read and write** on this repository | Fabric's GitHub connector authenticates with a token, not with your Microsoft sign-in. This is the one secret the design sanctions, it is yours alone, and a short expiry is fine |
| Capacity headroom | A workspace needs a capacity, and this demo's is paused most of the time — resume it first |

That first row is a real ask and worth naming as one. It is two grants, not one — the
tenant's *Users can create workspaces* setting, and capacity contributor so the workspace
can sit on the shared capacity — and neither can be narrowed to "may create a feature
workspace for a solution I work on". A developer who has them can create and delete
workspaces anywhere in the tenant. Plenty of organisations will not agree to that, and
they are not being unreasonable.

If yours is one of them, self-service does not have to mean standing rights. Both
alternatives keep the developer experience and move the privilege into the platform:

- **Provision on request.** A dispatchable workflow running as `mi-fabric-platform`,
  which already holds these rights, creates the workspace, places it on the capacity,
  names it by convention and grants the requester Admin. Nobody needs a tenant grant, and
  every creation is an audited run. You would still supply your own Git credentials
  afterwards, or commits carry the platform identity's name rather than yours.
- **Declare it.** Terraform creates one workspace per developer per solution from a list
  in this repository, so onboarding yourself is a pull request. Strongest governance,
  fully declarative, and the workspaces exist whether or not anyone is using them.

This repository takes the direct route because it is a demonstration with one maintainer.
An enterprise should expect to pick one of the two above — or wait: Microsoft has said it
plans a **delegated model for branch-out**, so that people without workspace-creation or
capacity-assignment rights can still branch out for themselves. That would remove this
prerequisite entirely.

One thing that would *not* help, despite appearances: connecting `ws-<solution>-dev` to Git
so people could branch out from it. Branch-out requires Contributor on the source
workspace — Viewers cannot even see Git information — so it would mean giving up the
Viewer-only rule that keeps dev from drifting, it still needs the same rights to create the
target workspace, and a workspace that fabric-cicd deploys into would sit permanently
dirty, since a deploy registers as uncommitted changes.

## The lifecycle, before the detail

```mermaid
flowchart LR
    B["1 · Branch<br/>pushed from your clone"] --> W["2 · Workspace<br/>you create it"]
    W --> C["3 · Connect it<br/>Git integration, your branch"]
    C --> K["4 · Work<br/>report layout · run a notebook"]
    K --> M["5 · Commit<br/>to your branch"]
    M --> PR["6 · Pull request"]
    PR --> MAIN["merged to main"]
    MAIN --> DEV["the build deploys<br/>ws-#60;solution#62;-dev"]
    MAIN --> D["7 · Delete the workspace"]
    M -.->|"or switch branch and keep it"| K
    style W fill:#f0fdf4,stroke:#16a34a
    style K fill:#f0fdf4,stroke:#16a34a
    style MAIN fill:#fff8e1,stroke:#f59e0b
    style DEV fill:#eff6ff,stroke:#2563eb
```

Green is yours and temporary, gold is the source of truth, blue belongs to the pipeline.
The dotted line is the choice covered further down: delete the workspace per feature, or
keep one and move it between branches.

## 1. Create the branch first

Fabric connects to a branch that already exists, so push it before you go near the portal.

```bash
git switch -c feature/add-revenue-measure
git push -u origin feature/add-revenue-measure
```

## 2. Create the workspace

In Fabric, **Workspaces → New workspace**. Name it `ws-<solution>-dev-<you>` so it is
obvious whose draft it is, and assign it to the same capacity as the solution.

Not *My workspace* — Fabric's
[Git integration limitations](https://learn.microsoft.com/fabric/cicd/git-integration/git-integration-process#considerations-and-limitations)
state plainly that it can't connect to a Git provider, so none of what follows works
there. It would be a poor fit regardless: you get one, so two branches at once is
impossible; nobody else can see your draft; and the lifecycle below ends by deleting the
workspace, which you cannot do to *My workspace*.

## 3. Connect it to your branch

**Workspace settings → Git integration**. Choose GitHub, add your account with the token,
then point it at the repository, your branch, and the solution's folder.

![Git integration settings showing the repository, folder and branch](images/feature-workspace-git-settings.png)

Fabric then offers to fill the workspace from the branch — accept it. Only
[Git-supported item types](https://learn.microsoft.com/fabric/cicd/git-integration/intro-to-git-integration#supported-items)
arrive; anything else the solution deploys simply will not be there. Every item that did
sync shows **Synced**, with the branch and last-synced commit along the bottom.

![The workspace list with a Git status column and the branch in the footer](images/feature-workspace-synced.png)

## 4. Work

**Know what will and will not work here first.** A synced workspace is not a deployed one:
Git sync copies definitions exactly as committed, so `parameter.yml` never runs and every
placeholder stays literal. The semantic model therefore arrives pointing at a server called
`SALES_WAREHOUSE_ENDPOINT`, its editor refuses to open, and the report reports *"Couldn't
load the model schema associated with this report."*

So a feature workspace is for **a report's layout and running a notebook**. Editing a
semantic model, or anything that has to resolve a connection, needs a deployed workspace —
which means merging and letting the build put it in `ws-<solution>-dev`.

Edit items in the portal as you normally would. Anything you touch flips to
**Uncommitted** in the Git status column.

## 5. Commit to your branch

Open **Source control**, review what changed, write a message, and commit. This pushes
straight to your feature branch.

![The source control panel listing changed items with a commit message box](images/feature-workspace-changes.png)

Expect noise alongside your real change. Fabric writes files without a trailing newline
and rewrites line endings, so items you never opened can appear as modified — the
screenshot above shows exactly that: `nb_ingest_orders` is a genuine edit, `lh_bronze` is
whitespace. Read the list before you commit and uncheck what you did not mean to touch.

To move to a different branch, use **Switch branch** in the same pane rather than
disconnecting. Commit first: you cannot switch with uncommitted changes, every item is
overridden by the new branch's version, and an item that exists only in the old branch is
deleted.

## 6. Open a pull request

From here it is the ordinary path. The pull request runs the same gates as any other —
linting, tests, the repository guards, an offline dbt parse — and on merge the build
publishes to `ws-<solution>-dev` as the deploy identity. Your workspace played no part in
that: the repository did.

## Reuse it, rather than one per feature

Creating a feature workspace per branch proliferates fast: three developers with two branches
each is six workspaces, and every one needs creating, connecting and syncing. Fabric
supports the alternative — keep the workspace and move it between branches with **Switch
branch** in the Source control pane.

One constraint decides the shape: a switch target *must contain the same directory* the
workspace is connected to. A workspace is therefore bound to one solution's folder, which
makes the natural unit **one workspace per developer per solution** — `ws-sales-dev-mark`
lives as long as you work on sales, and moves from branch to branch as you do.

| | One per feature | One per developer, per solution |
|---|---|---|
| How many exist | One per open branch, across the team | One per person per solution they touch |
| Starting work | Create, connect, sync each time | Switch branch |
| Isolation | Complete — nothing survives from the last feature | Switching overrides every item, and deletes items absent from the new branch. Abandoned drafts can linger |
| Before you move on | Delete the workspace | Commit first: you cannot switch with uncommitted changes |
| Suits | An occasional change, or a shared demo tenant | Anyone working on features regularly |

Switching is restricted to workspace admins unless someone enables **Allow users with at
least Contributor role to change Git branch** on that workspace. You are the admin of your
own, so this only matters if you share one.

Recycling is the better default for a real team; the per-feature flow above is what to do
the first time, and remains right when a draft is genuinely throwaway.

## 7. Dispose of it

**Delete the workspace when you no longer need it** — when the pull request merges if it
was per-feature, or when you stop working on that solution if you recycle it. It is a
draft space, not an environment: nothing in it is a source of truth, and anything worth
keeping is already in the branch. Commit before you delete — items never committed are
simply gone. A deleted workspace is restorable for 30 days if you go too early.

An idle workspace does not burn capacity units on its own, so this is about clutter and
governance rather than cost: every one is another place someone can mistake a draft for
something real, and another entry an admin has to reason about.

Delete the branch too; GitHub does that for you on merge.

## What a Git-connected workspace does to this repository

Tested, rather than assumed — a workspace was connected to a feature branch pointed at
`solutions/sales/fabric`, and the results are worth knowing before you try it.

**Two things stop the sync outright:**

| Symptom | Cause |
|---|---|
| `MissingItemDefinitionFiles` | `wh_analytics.Warehouse` contains only `.platform` — deliberately, so fabric-cicd creates an empty warehouse for dbt to fill. Git integration expects a warehouse to carry a DacFx database project there, and refuses the whole directory rather than just that item. Not a claim that warehouses cannot be serialised: the definition API refuses them, Git integration does not |
| `InvalidArtifactJobSchedulerException` | Hit when `.schedules` held `"enabled": "SCHEDULE_ENABLED"` for `parameter.yml` to rewrite at deploy time. Fabric reads the file directly and requires a boolean. The file now ships a literal `false` and `parameter.yml` rewrites that instead, so this no longer occurs here — the lesson generalises: placeholders survive in free-form files like TMDL and fail wherever Fabric validates a schema |

**The bigger constraint is that a synced workspace is not a deployed one.** Git sync copies
the definitions as committed; it does not run fabric-cicd, so `parameter.yml` never executes
and every placeholder stays a placeholder. `model.tmdl` commits the line
`database = Sql.Database("SALES_WAREHOUSE_ENDPOINT", "SALES_WAREHOUSE_ID")`, and that is
exactly what lands in the workspace — a connection to a server named `SALES_WAREHOUSE_ENDPOINT`.
Measured consequences: the semantic model's editor refuses to open, and opening the report
gives *"Couldn't load the model schema associated with this report."* The report editor still
works, so layout can be changed and committed; nothing data-bound can be.

This is not a defect to fix; it is what parameterisation means — the values are per
environment, and a feature workspace is not one of them. It does decide what the portal is
good for here: **drafting a report's layout, and running a notebook.** Anything that needs to
resolve a connection needs a deployed workspace, which means `ws-<solution>-dev` after a merge.

**And once it does sync, the workspace reports changes you did not make.** With no edit at
all, `lh_bronze` and `nb_ingest_orders` come back *Modified*, and committing produces a
diff of pure whitespace: Fabric writes files with no trailing newline, and rewrites
`.schedules` line endings. Nothing is lost, but every feature workspace starts dirty and
a careless commit fills the repository with noise.

One thing that did **not** happen, despite the API suggesting it would: Git integration
left the semantic model untouched. `getDefinition` splits its expression out into a
separate `expressions.tmdl` with the author's endpoint baked in, but the Git serialiser
does not — the two paths disagree, and only the API path breaks `parameter.yml`. A guard
catches that case either way.

The honest summary: authoring in a feature workspace works for items a workspace can
serialise cleanly, and this repository's solution folder is not one of them today. Treat
the portal as a place to draft, and the repository as where a change becomes real.

## What does not sync today

`solutions/<name>/fabric` contains `wh_analytics.Warehouse`, which holds only a
`.platform` file because a warehouse has no exportable definition. fabric-cicd deploys it
happily; Git integration rejects **the whole folder** with `MissingItemDefinitionFiles`.
Until the warehouse is created by Terraform rather than shipped in the bundle, connect
your workspace to a branch where that folder is absent.

The measured detail behind this, and what else a round trip does to item definitions, is
in [the path to production](path-to-production.md#what-a-git-connected-workspace-does-to-this-repository).
