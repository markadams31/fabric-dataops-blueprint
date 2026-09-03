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

## Platform sharp edges (live-verified — see docs/evidence/2026-09-03-torture.md)

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
