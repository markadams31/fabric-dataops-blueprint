# S27 — platform identity creates a workspace via OIDC (no secrets)

**Date** 2026-09-02 · **Runs** verify-oidc 33607526208 (fail), 33607700176 (fail), 33607940613 (pass)

## Question

Can `mi-fabric-platform`, authenticated purely by GitHub OIDC federation, create a
workspace on the F2 through **capacity Contributor permissions** granted to
`grp-fabric-workspace-creators` — i.e. does least privilege work, or is ARM
`administration.members` (capacity admin) required?

## Verdict

**Contributor-via-group works.** The identity listed the capacity, created
`zz-spike-s27` on it (`POST /v1/workspaces` with `capacityId`), and deleted it
(HTTP 200). No capacity-admin rights, no client secret, no PAT anywhere in the chain:
GitHub OIDC → federated credential → Azure CLI → Fabric REST. This also proves the
scoped tenant settings end to end (SPN APIs + SPN-create-workspaces scoped to
`grp-fabric-automation`, both satisfied via group membership).

## Findings along the way

1. **GitHub now presents immutable-ID OIDC subjects**:
   `repo:markadams31@38002523/fabric-dataops-blueprint@1354315716:ref:refs/heads/main`
   — owner and repo carry their numeric IDs (rename/recreate protection). Federated
   credentials written in the classic `repo:owner/name:...` form fail with
   `AADSTS700213`. Any repository using classic subjects breaks on its next run.
   Fix: embed the IDs in the subject (`gh api repos/<o>/<r> --jq .id`,
   `--jq .owner.id`); the Terraform local `github_oidc_repo` composes it.
2. **Federated-credential changes propagate slowly.** An immediate retry after the
   subject fix failed with the same error; the retry after ~120 s succeeded. Wait
   two minutes before concluding a fed-cred change didn't work.
3. The capacity list visible to the identity also included `Premium Per User -
   Reserved` — contributor visibility behaves as documented.

## Still open from the trial→MI delta

fabric-cicd publish as the MI (`AzureCliCredential`), OneLake/OPENROWSET under an MI
token, and connection roles for an MI principal — these are exercised naturally by
Steps 4–5 and recorded then.
