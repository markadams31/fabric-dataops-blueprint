# Working in a branched workspace

A branched workspace is a Fabric workspace of your own, connected to your feature
branch. Use it when a change is easier to make in the portal than in a text editor —
a report, a semantic model, a notebook you want to run interactively.

The rule that makes it safe: **writes go to your workspace, reads come from the shared
one.** Nobody can write to `ws-<solution>-dev` — the team holds Viewer there — so your
workspace is where drafting happens, and a pull request is how it becomes real.

## Before you start

| You need | Why |
|---|---|
| Membership of `grp-fabric-workspace-creators` | It carries workspace-creation rights, and the *Users can sync workspace items with GitHub repositories* tenant setting is scoped to it. Without it, connecting fails with `FeatureNotAvailable` and names no setting |
| A [fine-grained GitHub token](https://github.com/settings/personal-access-tokens/new) with **Contents: read and write** on this repository | Fabric's GitHub connector authenticates with a token, not with your Microsoft sign-in. This is the one secret the design sanctions, it is yours alone, and a short expiry is fine |

## 1. Create the branch first

Fabric connects to a branch that already exists, so push it before you go near the portal.

```bash
git switch -c feature/add-revenue-measure
git push -u origin feature/add-revenue-measure
```

## 2. Create the workspace

In Fabric, **Workspaces → New workspace**. Name it `ws-<solution>-dev-<you>` so it is
obvious whose draft it is, and assign it to the same capacity as the solution.

## 3. Connect it to your branch

**Workspace settings → Git integration**. Choose GitHub, add your account with the token,
then point it at the repository, your branch, and the solution's folder.

![Git integration settings showing the repository, folder and branch](images/branched-workspace-git-settings.png)

Fabric then offers to fill the workspace from the branch — accept it. Every item that
synced shows **Synced** in the workspace list, with the branch and last-synced commit
along the bottom.

![The workspace list with a Git status column and the branch in the footer](images/branched-workspace-synced.png)

## 4. Work

Edit items in the portal as you normally would. Anything you touch flips to
**Uncommitted** in the Git status column.

## 5. Commit to your branch

Open **Source control**, review what changed, write a message, and commit. This pushes
straight to your feature branch.

![The source control panel listing changed items with a commit message box](images/branched-workspace-changes.png)

Expect noise alongside your real change. Fabric writes files without a trailing newline
and rewrites line endings, so items you never opened can appear as modified — the
screenshot above shows exactly that: `nb_ingest_orders` is a genuine edit, `lh_bronze` is
whitespace. Read the list before you commit and uncheck what you did not mean to touch.

## 6. Open a pull request

From here it is the ordinary path. The pull request runs the same gates as any other —
linting, tests, the repository guards, an offline dbt parse — and on merge the build
publishes to `ws-<solution>-dev` as the deploy identity. Your workspace played no part in
that: the repository did.

## 7. Dispose of it

**Delete the workspace when the pull request merges.** It is a draft space, not an
environment: nothing in it is a source of truth, and anything worth keeping is in the
branch. A deleted workspace is restorable for 30 days if you delete one too early, and
leaving them around costs capacity and invites someone to treat a draft as real.

Delete the branch too — GitHub does it for you on merge.

## What does not sync today

`solutions/<name>/fabric` contains `wh_analytics.Warehouse`, which holds only a
`.platform` file because a warehouse has no exportable definition. fabric-cicd deploys it
happily; Git integration rejects **the whole folder** with `MissingItemDefinitionFiles`.
Until the warehouse is created by Terraform rather than shipped in the bundle, connect
your workspace to a branch where that folder is absent.

The measured detail behind this, and what else a round trip does to item definitions, is
in [the path to production](path-to-production.md#what-a-branched-workspace-does-to-this-repository).
