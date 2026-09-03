# Quickstart

From fork to a running platform. The shape of the journey: **steps 1–5 are a human
with a laptop, once; everything after is a pull request.** The first Terraform apply
runs as you because it creates the identity CI runs as — every later apply happens
in GitHub Actions.


## Before you start

You need:

- An **Azure subscription** you can create resources and role assignments in
  (role assignments need Owner or User Access Administrator on the subscription).
- Rights to **create Entra security groups and managed identities** — the apply
  creates both. In a demo tenant, Global Administrator covers it.
- The **Fabric administrator** role in the tenant (for step 4's portal settings).
- Locally: `az`, `terraform` (≥ 1.9), `gh`, `jq` — each logged in (`az login`, `gh auth login`).
- Optional, for local development: `uv` (runs the repo's Python tooling and dbt).

Cost: an F2 capacity bills ~US$0.36/hour while running and **nothing while paused**.
Step 3 ends by pausing it, and the apply includes a US$25/month budget alert as a backstop.

## 1. Fork and clone

Fork this repository, then clone your fork.

## 2. Bring a Terraform state backend

The one prerequisite: an Azure Storage container, reachable with Microsoft Entra
credentials, for Terraform state. Most organisations already have one. If not:

```bash
az group create -n rg-tfstate -l <region>
az storage account create -n <yourstateaccount> -g rg-tfstate --sku Standard_LRS \
  --min-tls-version TLS1_2 --allow-shared-key-access false
az storage container-rm create --storage-account <yourstateaccount> -g rg-tfstate \
  -n tfstate-fabric-dataops
az role assignment create --assignee <your-upn> --role "Storage Blob Data Contributor" \
  --scope "$(az storage account show -n <yourstateaccount> -g rg-tfstate --query id -o tsv)/blobServices/default/containers/tfstate-fabric-dataops"
```

Recommended on the account: blob **versioning**, 30-day blob and container
**soft delete**, and **shared-key access disabled** — the backend authenticates with
an Entra token (`use_azuread_auth = true`), so nothing here needs account keys. But
disabling keys affects every consumer of the account, so check what else uses it.

## 3. First apply — locally, as you

```bash
cd platform/terraform
cp terraform.tfvars.example terraform.tfvars          # your identifiers — no secrets
cp platform.backend.hcl.example platform.backend.hcl  # your state container
# edit both, then:
terraform init -backend-config=platform.backend.hcl
terraform apply
```

This creates the resource group, the F2 capacity, the budget alert, the platform
identity `mi-fabric-platform` with its GitHub OIDC federation (anchored to *your*
fork via `github_repository`), its role assignments, and the two security groups
the next step's settings are scoped to.

Then pause the capacity until a deployment needs it — Terraform manages what the
capacity *is*, not whether it is running:

```bash
az fabric capacity suspend -g <resource-group> --capacity-name <capacity-name>
```

## 4. Tenant and capacity settings — in the portal

These are portal clicks because no API exists for them; expect ~5 minutes in the
[admin portal](https://app.fabric.microsoft.com/admin-portal), signed in as a Fabric
admin. Scope every setting to a group, never the whole organisation — the apply
created the groups and put the platform identity in them, and Terraform adds each
solution's deploy identity as solutions are created.

### Tenant settings (admin portal → Tenant settings)

| Setting | Value | Why |
|---|---|---|
| Developer settings → **Service principals can call Fabric public APIs** | Enabled, scoped to `grp-fabric-automation` | Every deployment runs as a managed identity. Without this, nothing in the repository works. |
| Developer settings → **Service principals can create workspaces, connections, and deployment pipelines** | Enabled, scoped to `grp-fabric-automation` | A separate switch from the one above — it alone lets the platform identity create workspaces and connections. |
| Git integration → **Users can synchronize workspace items with their Git repositories** | Enabled | Personal-workspace Git sync (extension). Harmless for the core; required later. |
| Git integration → **Users can sync workspace items with GitHub repositories** | Enabled, scoped to `grp-fabric-automation` | Fabric's GitHub provider is off by default. Scoping to the group keeps ad-hoc portal Git connections out of the rest of the tenant. |
| Workspace settings → **Users can create workspaces** | Enabled, include `grp-fabric-workspace-creators` | The platform identity creates workspaces; developers do not. |
| Workspace settings → **Define workspace retention period** | 30 days | Deleted workspaces stay restorable long enough to notice a mistake. |
| Item settings → **Fabric item recovery** | Enabled, 30 days | Recycle-bin restore preserves item IDs, which keeps redeploys and references intact. Matched to the workspace retention period. |

### Capacity settings (admin portal → Capacity settings → your capacity)

| Setting | Value | Why |
|---|---|---|
| **Contributor permissions** | *Specific users or security groups* → `grp-fabric-workspace-creators` | Least privilege: a capacity **contributor** can place workspaces on the capacity but cannot change its settings or delete it. The platform identity never needs capacity admin. |

## 5. Harden your fork

```bash
platform/scripts/github-setup.sh
```

Reads `terraform output` — its only input — and asserts the repository settings:
squash-only merges, read-only workflow tokens, Dependabot alerts, secret scanning,
the `protect-main` ruleset, the `platform` environment with you as required
reviewer, and the Actions variables (identifiers only, never secrets). Idempotent;
re-run it any time. On a private fork without GitHub Pro, the Pro-only pieces are
skipped with a warning — re-run once your fork is public.

Then prove the plumbing end to end: run the **verify-oidc** workflow (Actions →
verify-oidc). It logs in as the platform identity and acquires a Fabric token —
if it is green, every later workflow can authenticate. Two fork notes: GitHub
leaves workflows disabled on a fresh fork until you enable them in the Actions
tab, and scheduled workflows (the nightly pause, the production heartbeat) stay
off until the fork has its own commit activity.

## 6. Create your first solution

Copy `solutions/_template` to `solutions/<name>` and open a pull request — the
solution's workspaces, deploy identity and viewer group are all derived from the
folder. The pull request must pass validation — linting, tests and the repository
guards — before it can merge.

Merging the folder does not create the workspaces — Terraform does, behind the
platform gate. After the merge:

1. Run **platform-terraform** (Actions → platform-terraform → apply) and approve
   it. This creates the three workspaces, the solution's deploy identity and its
   GitHub environments.
2. Re-run `platform/scripts/github-setup.sh` — it picks up the new solution's
   identity from `terraform output` and writes its `AZURE_CLIENT_ID_<NAME>`
   variable.
3. Re-run the failed **build** (or push again). The first build after the merge
   raced the provisioning and is expected to fail — this is the one place the
   pull-request flow and the infrastructure meet.

One deliberate consequence of least privilege: nobody can see the new workspaces
until you add people to `grp-<name>-viewers` — including yourself
(`az ad group member add --group grp-<name>-viewers --member-id <user-object-id>`).

The `finance` worked example is wired to *this* repository's sales workspaces by
ID (`solutions/finance/fabric/parameter.yml` — a data contract is explicit,
versioned wiring). On a fork, replace those IDs with your own — the platform
apply prints them — or delete the folder until you need a second solution.

## 7. Ship

Resume the capacity first if it is paused (Actions → capacity → run with
`resume`) — deploys need it running, and the nightly schedule pauses it.

Push to `main`. `build.yml` packs each solution into an immutable bundle and the
reusable `deploy-env.yml` deploys it into the dev workspace as that solution's own
identity — publish, seed, `dbt build`, verify. Re-deploying the same bundle is a
no-op.

## 8. Promote

Resume the capacity (Actions → capacity → resume), then run the **promote** workflow (Actions → promote) giving it
a green build run's ID. The same bundle that proved itself in dev goes to `test`,
then `prod`, pausing for your approval before each. Nothing is rebuilt between
environments; rollback is the same workflow pointed at an earlier run.
