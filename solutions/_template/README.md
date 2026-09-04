# _template — what a new solution starts from

Copy this folder to `solutions/<your-solution-name>` and open a pull request.
That is the whole procedure: the platform derives everything else from the folder —
its three workspaces (`ws-<name>-dev/test/prod`), its deploy identity
(`mi-deploy-<name>`) and its viewer group (`grp-<name>-viewers`).

## Layout — a solution holds two directories

| Directory | What it is | Deployed by |
|---|---|---|
| `fabric/` | Fabric items — every type fabric-cicd supports | fabric-cicd, full scope |
| `dbt/<project>/` | A dbt project (one per subdirectory) | `dbt build` |

Both are optional: a solution that only reads another's marts needs no `dbt/`.

Inside `fabric/`, items follow Fabric's own Git format: one folder per item, named
`<display-name>.<ItemType>`. When copying an item folder to start a new item, give it
a fresh `logicalId` (any new UUID) — two items must never share one.

This template deliberately contains no example item: an item folder carries a
`logicalId`, and copies of a template item would all collide on it. Copy an item
from `solutions/sales/` and give it a fresh UUID instead.

## Overrides

Conventions cover the normal case — and today they are all there is: nothing reads
a `solution.yml` yet. When the first real deviation arrives (per-solution approvers,
at promotion), it becomes an override file containing only that deviation.

## Naming conventions the tooling relies on

Most names are yours. Two are not, because the pipeline finds items by them:

| Name | Why |
|---|---|
| `lh_bronze` | Where sample data is seeded and dbt reads its raw files. Other lakehouses (`lh_curated`, …) are free-form. |
| `wh_*` | The warehouse dbt builds into — exactly one per solution. |

## Triggers

`fabric/<item>.<Type>/.schedules` declares when an item runs. It is Fabric's own
format — the same file a workspace writes when you commit from the portal — and
fabric-cicd publishes it with the rest of the definition, so a trigger travels in
the bundle with the thing it triggers. Which environments actually run it is a
`parameter.yml` rewrite of the `enabled` flag, like any other per-environment value.
