# _template — what a new solution starts from

Copy this folder to `solutions/<your-solution-name>` and open a pull request.
That is the whole procedure: the platform derives everything else from the folder —
its three workspaces (`ws-<name>-dev/test/prod`), its deploy identity
(`mi-deploy-<name>`) and its viewer group (`grp-<name>-viewers`).

## Layout — the directory names are the component types

| Directory | Component type | Deployed by |
|---|---|---|
| `fabric/` | Fabric items — every type fabric-cicd supports, one component | fabric-cicd, full scope |
| `dbt/<project>/` | A dbt project (one per subdirectory) | `dbt build` |

A new component type is one driver in `deploy/` plus its directory name — the
contract is validate → build → deploy → verify.

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
