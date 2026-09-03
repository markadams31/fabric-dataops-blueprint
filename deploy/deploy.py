"""Deploy a bundle to one environment.

usage: deploy.py --bundle FILE --manifest FILE --solution NAME --environment ENV

Verifies the bundle digest, resolves the target workspace by name, publishes every
Fabric item type in one pass (fabric-cicd), then verifies item counts. Runs as
whatever identity `az login` established — locally you, in CI the solution's
deploy identity.
"""

import argparse
import collections
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import time

import requests
from azure.identity import AzureCliCredential
from fabric_cicd import constants, deploy_with_config

API = "https://api.fabric.microsoft.com/v1"

def get_all(url: str, headers: dict) -> list:
    """Fabric list APIs paginate and throttle: follow continuationUri, honor Retry-After."""
    rows: list = []
    while url:
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", "10")))
            continue
        r.raise_for_status()
        body = r.json()
        rows += body.get("value", [])
        url = body.get("continuationUri")
    return rows


# Full scope, always: fabric-cicd resolves cross-item references only within one
# invocation, so partial scopes create broken deploys (see
# docs/evidence/2026-08-31-trial-spikes.md). The library
# owns the list — hardcoding a copy here would silently go stale as Fabric adds
# item types (the enum grew to 30 while this repo was being built).
ITEM_TYPES = list(constants.ACCEPTED_ITEM_TYPES)


def content_digest(root: pathlib.Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(str(f.relative_to(root)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--solution", required=True)
    ap.add_argument("--environment", required=True)
    args = ap.parse_args()

    manifest = json.loads(pathlib.Path(args.manifest).read_text())
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="bundle-"))
    with tarfile.open(args.bundle) as tar:
        tar.extractall(workdir, filter="data")

    digest = content_digest(workdir)
    if digest != manifest["content_digest"]:
        sys.exit(f"digest mismatch: bundle={digest} manifest={manifest['content_digest']}")
    print(f"bundle verified: {manifest['solution']}@{manifest['source_sha'][:12]} digest ok")

    cred = AzureCliCredential()
    token = cred.get_token("https://api.fabric.microsoft.com/.default").token
    headers = {"Authorization": f"Bearer {token}"}

    ws_name = f"ws-{args.solution}-{args.environment}"
    workspaces = get_all(f"{API}/workspaces", headers)
    ws = next((w for w in workspaces if w["displayName"] == ws_name), None)
    if not ws:
        sys.exit(f"workspace {ws_name} not visible to this identity "
                 f"(visible: {[w['displayName'] for w in workspaces]})")

    caps = get_all(f"{API}/capacities", headers)
    cap = next((c for c in caps if c["id"] == ws.get("capacityId")), None)
    if cap and cap.get("state") != "Active":
        sys.exit(f"capacity '{cap['displayName']}' is {cap.get('state')} — resume it before deploying")
    if not cap:
        # Deploy identities hold no capacity permission, so this is the common case:
        # the state cannot be preflighted, and a paused capacity surfaces later as
        # fabric-cicd's CapacityNotActive error (see the maintainer notes).
        print("note: workspace capacity not visible to this identity — state not preflighted")

    core = {"workspace_id": ws["id"],
            "repository_directory": str(workdir / "fabric"),
            "item_types_in_scope": ITEM_TYPES}
    if (workdir / "fabric" / "parameter.yml").is_file():
        # deploy_with_config does not auto-discover parameter.yml — point at it.
        core["parameter"] = str(workdir / "fabric" / "parameter.yml")
    result = deploy_with_config(
        config_file_path=str(pathlib.Path(__file__).parent / "fabric.config.yml"),
        token_credential=cred,
        environment=args.environment,
        config_override={"core": core},
    )
    print(f"fabric-cicd: {result.status.value} — {result.message}")

    # Verify: every item in the bundle exists in the workspace.
    wanted = collections.Counter()
    for p in (workdir / "fabric").glob("*/.platform"):
        meta = json.loads(p.read_text())["metadata"]
        wanted[(meta["type"], meta["displayName"])] += 1
    live = get_all(f"{API}/workspaces/{ws['id']}/items", headers)
    have = {(i["type"], i["displayName"]) for i in live}
    missing = [k for k in wanted if k not in have]
    if missing:
        sys.exit(f"verify FAILED — deployed but not found: {missing}")
    print(f"verify ok: {len(wanted)} bundle items present in {ws_name} "
          f"({len(live)} items total)")

    if (workdir / "dbt").is_dir():
        # Demo ingestion: every environment seeds the same committed sample bytes,
        # standing in for a real solution's per-environment ingestion. Promotion
        # itself moves definitions only — data never travels between workspaces.
        seed_bronze(cred, headers, ws["id"], live)
        run_dbt(workdir, cred, headers, ws["id"], live, args.environment)



def seed_bronze(cred, headers, ws_id, items) -> None:
    """Upload the committed sample files into the Bronze lakehouse (demo
    ingestion — a real solution replaces this with its own sources)."""
    lh = next(i for i in items if i["type"] == "Lakehouse")
    sto = {"Authorization": "Bearer "
           + cred.get_token("https://storage.azure.com/.default").token}
    for f in sorted(pathlib.Path("samples/data").glob("*.csv")):
        base = (f"https://onelake.dfs.fabric.microsoft.com/{ws_id}/{lh['id']}"
                f"/Files/retail/{f.name}")
        body = f.read_bytes()
        requests.put(base, params={"resource": "file"},
                     headers={**sto, "Content-Length": "0"}, timeout=60).raise_for_status()
        requests.patch(base, params={"action": "append", "position": "0"},
                       headers=sto, data=body, timeout=60).raise_for_status()
        requests.patch(base, params={"action": "flush", "position": str(len(body))},
                       headers={**sto, "Content-Length": "0"}, timeout=60).raise_for_status()
        print(f"seeded {f.name} -> {lh['displayName']}/Files/retail/ ({len(body)} bytes)")


def run_dbt(workdir, cred, headers, ws_id, items, environment) -> None:
    """Run every dbt project in the bundle against the solution's warehouse."""
    lh = next(i for i in items if i["type"] == "Lakehouse")
    wh = next(i for i in items if i["type"] == "Warehouse")
    props = requests.get(f"{API}/workspaces/{ws_id}/warehouses/{wh['id']}",
                         headers=headers, timeout=60).json()
    env = {**os.environ,
           "DBT_FABRIC_SERVER": props["properties"]["connectionString"],
           "DBT_FABRIC_DATABASE": wh["displayName"],
           "DBT_LAKEHOUSE_FILES": (f"abfss://{ws_id}@onelake.dfs.fabric.microsoft.com"
                                   f"/{lh['id']}/Files"),
           "DBT_TARGET_ENV": environment}
    for project in sorted((workdir / "dbt").iterdir()):
        if not project.is_dir():
            continue
        print(f"dbt build: {project.name} -> {wh['displayName']}")
        r = subprocess.run(["dbt", "build", "--no-use-colors",
                            "--profiles-dir", str(project), "--project-dir", str(project)],
                           env=env, check=False)
        if r.returncode != 0:
            sys.exit(f"dbt build failed for {project.name}")


if __name__ == "__main__":
    main()
