#!/usr/bin/env bash
# github-setup.sh — create and harden the GitHub repository.
#
# Run it yourself after the first `terraform apply` in platform/terraform — every
# value it publishes comes from `terraform output`, so Terraform stays the single
# source of truth. Needs: gh (logged in as the repo owner), terraform, jq.
#
# What it does, in order:
#   1  Repository — create private if missing, push main, squash-merge only,
#      wiki/projects off, delete branches on merge
#   2  Actions — workflow token read-only, cannot approve PRs; Dependabot alerts
#   3  Ruleset, secret scanning, "platform" environment — Pro/public-only
#      features: attempted, skipped with a warning while the repo is private on a
#      free plan. Re-run this script once the repo flips public.
#   4  Variables — identifiers only, never secrets. Environment-level when the
#      environment exists, repository-level otherwise.
#
# Idempotent: settings are asserted, not toggled — re-running converges.

set -euo pipefail

say()  { printf '%s\n' "$*"; }
warn() { printf '!  %s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
gh auth status >/dev/null 2>&1 || die "not logged in — run: gh auth login"

TF_OUT="$(terraform -chdir="$HERE/../terraform" output -json 2>/dev/null)" \
  && [[ "$TF_OUT" != "{}" ]] || die "no terraform outputs — run terraform apply in platform/terraform first"
val() { jq -er ".$1.value" <<<"$TF_OUT" || die "terraform output $1 missing"; }

GITHUB_REPO="$(val github_repository)"
AZURE_TENANT_ID="$(val tenant_id)"
AZURE_SUBSCRIPTION_ID="$(val subscription_id)"
AZURE_CLIENT_ID_PLATFORM="$(val platform_client_id)"
FABRIC_CAPACITY_NAME="$(val capacity_name)"
FABRIC_RESOURCE_GROUP="$(val resource_group)"
TFSTATE_SUBSCRIPTION_ID="$(val tfstate_subscription_id)"
TFSTATE_ACCOUNT="$(val tfstate_storage_account)"
TFSTATE_CONTAINER="$(val tfstate_container)"
TFSTATE_RESOURCE_GROUP="$(val tfstate_resource_group)"
LOCATION="$(val location)"
BUDGET_EMAIL="$(val budget_email)"
BUDGET_START_DATE="$(val budget_start_date)"
FABRIC_CAPACITY_ADMINS="$(jq -ec .capacity_admins.value <<<"$TF_OUT")"  # list — HCL syntax for TF_VAR parsing

# --- 1 · repository ----------------------------------------------------------
if gh repo view "$GITHUB_REPO" --json name >/dev/null 2>&1; then
  say "=  repository $GITHUB_REPO exists"
else
  say "+  creating PRIVATE repository $GITHUB_REPO"
  gh repo create "$GITHUB_REPO" --private \
    --description "A working, secretless CI/CD reference architecture for Microsoft Fabric"
fi
git -C "$REPO_ROOT" remote get-url origin >/dev/null 2>&1 \
  || git -C "$REPO_ROOT" remote add origin "https://github.com/$GITHUB_REPO.git"
say "+  pushing main"
git -C "$REPO_ROOT" push -u origin main

say "+  squash-merge only, auto-delete branches, wiki/projects off"
gh api --silent -X PATCH "repos/$GITHUB_REPO" \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true -F has_wiki=false -F has_projects=false \
  -F squash_merge_commit_title=PR_TITLE -F squash_merge_commit_message=PR_BODY

# --- 2 · actions -------------------------------------------------------------
say "+  workflow token read-only, cannot approve PRs"
gh api --silent -X PUT "repos/$GITHUB_REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false
say "+  Dependabot vulnerability alerts"
gh api --silent -X PUT "repos/$GITHUB_REPO/vulnerability-alerts"

# --- 3 · pro/public-only hardening (tolerated while private on a free plan) --
if gh api --silent -X PATCH "repos/$GITHUB_REPO" --input - <<'JSON' 2>/dev/null
{"security_and_analysis": {"secret_scanning": {"status": "enabled"},
                           "secret_scanning_push_protection": {"status": "enabled"}}}
JSON
then say "+  secret scanning + push protection"
else warn "secret scanning unavailable while private — re-run once public"
fi

if gh api "repos/$GITHUB_REPO/rulesets" --jq '.[].name' 2>/dev/null | grep -qx "protect-main"; then
  say "=  ruleset protect-main exists"
elif gh api --silent -X POST "repos/$GITHUB_REPO/rulesets" --input - <<'JSON' 2>/dev/null
{"name": "protect-main", "target": "branch", "enforcement": "active",
 "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
 "rules": [
   {"type": "deletion"},
   {"type": "non_fast_forward"},
   {"type": "pull_request",
    "parameters": {"required_approving_review_count": 0,
                   "dismiss_stale_reviews_on_push": true,
                   "require_code_owner_review": false,
                   "require_last_push_approval": false,
                   "required_review_thread_resolution": true}},
   {"type": "required_status_checks",
    "parameters": {"strict_required_status_checks_policy": false,
                   "required_status_checks": [{"context": "validate"}]}}]}
JSON
then say "+  ruleset protect-main (PRs only, no force push, no deletion)"
else warn "rulesets unavailable while private — re-run once public"
fi
# Approvals are 0 because this is a single-maintainer repository; the "platform"
# environment reviewer is the human gate. Organisations should raise this to 1+.

ENV_AVAILABLE=true
if jq -n --argjson id "$(gh api user --jq .id)" \
     '{reviewers: [{type: "User", id: $id}],
       deployment_branch_policy: {protected_branches: false, custom_branch_policies: true}}' |
     gh api --silent -X PUT "repos/$GITHUB_REPO/environments/platform" --input - 2>/dev/null; then
  say "+  environment 'platform' (required reviewer: you)"
  gh api "repos/$GITHUB_REPO/environments/platform/deployment-branch-policies" \
      --jq '.branch_policies[].name' 2>/dev/null | grep -qx main \
    || gh api --silent -X POST "repos/$GITHUB_REPO/environments/platform/deployment-branch-policies" \
         -f name=main -f type=branch
  say "+  environment deploys from main only"
else
  ENV_AVAILABLE=false
  warn "environments unavailable while private — variables go to repo level; re-run once public"
fi

# --- 4 · variables (identifiers only, never secrets) -------------------------
# Repo-level always: these are identifiers, not secrets, and workflows outside
# the platform environment (build, capacity, prod-schedule) read them too.
for v in AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID AZURE_CLIENT_ID_PLATFORM \
         FABRIC_CAPACITY_NAME FABRIC_RESOURCE_GROUP FABRIC_CAPACITY_ADMINS \
         LOCATION BUDGET_EMAIL BUDGET_START_DATE \
         TFSTATE_SUBSCRIPTION_ID TFSTATE_ACCOUNT TFSTATE_CONTAINER TFSTATE_RESOURCE_GROUP; do
  say "+  repo variable $v"
  gh variable set "$v" --repo "$GITHUB_REPO" --body "${!v}"
done

# Per-solution environments: dev deploys unattended; test and prod pause for the
# repository owner's approval. All three restrict deployments to main.
MY_ID="$(gh api user --jq .id)"
terraform -chdir="$HERE/../terraform" output -json solutions 2>/dev/null | jq -r 'keys[]' |
  while read -r name; do
    for env in dev test prod; do
      if [ "$env" = "dev" ]; then payload='{"deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}'
      else payload="{\"reviewers\": [{\"type\": \"User\", \"id\": $MY_ID}], \"deployment_branch_policy\": {\"protected_branches\": false, \"custom_branch_policies\": true}}"
      fi
      say "+  environment $name-$env"
      echo "$payload" | gh api --silent -X PUT "repos/$GITHUB_REPO/environments/$name-$env" --input - 2>/dev/null \
        || { warn "environment $name-$env unavailable while private — re-run once public"; continue; }
      gh api "repos/$GITHUB_REPO/environments/$name-$env/deployment-branch-policies"           --jq '.branch_policies[].name' 2>/dev/null | grep -qx main         || gh api --silent -X POST "repos/$GITHUB_REPO/environments/$name-$env/deployment-branch-policies"              -f name=main -f type=branch
    done
  done

# One variable per solution wires the deploy matrix to the right identity.
terraform -chdir="$HERE/../terraform" output -json solutions 2>/dev/null |
  jq -r 'to_entries[] | [.key, .value.deploy_client_id] | @tsv' |
  while IFS=$'\t' read -r name cid; do
    var="AZURE_CLIENT_ID_$(echo "$name" | tr '[:lower:]-' '[:upper:]_')"
    say "+  variable $var (deploy identity for $name)"
    gh variable set "$var" --repo "$GITHUB_REPO" --body "$cid"
  done

# --- 5 · retirement -----------------------------------------------------------
# Retiring a solution is deleting its folder, so its delivery wiring must go too:
# a leftover AZURE_CLIENT_ID_* points at an identity that no longer exists, and a
# leftover environment would silently re-adopt a future solution of the same name.
LIVE="$(terraform -chdir="$HERE/../terraform" output -json solutions 2>/dev/null | jq -r 'keys[]')"
gh api "repos/$GITHUB_REPO/environments" --jq '.environments[].name' 2>/dev/null |
  while read -r env; do
    [ "$env" = "platform" ] && continue
    printf '%s\n' "$LIVE" | grep -qx "${env%-*}" && continue
    say "-  environment $env (solution retired)"
    gh api --silent -X DELETE "repos/$GITHUB_REPO/environments/$env"
  done
gh variable list --repo "$GITHUB_REPO" --json name --jq '.[].name' 2>/dev/null |
  grep '^AZURE_CLIENT_ID_' | while read -r v; do
    [ "$v" = "AZURE_CLIENT_ID_PLATFORM" ] && continue
    printf '%s\n' "$LIVE" | grep -qx "$(echo "${v#AZURE_CLIENT_ID_}" | tr '[:upper:]' '[:lower:]')" && continue
    say "-  variable $v (solution retired)"
    gh variable delete "$v" --repo "$GITHUB_REPO"
  done

say ""
say "Done: https://github.com/$GITHUB_REPO"
