"""Scheduled operations for one solution's environment.

usage: operate.py --solution NAME --environment ENV

Runs the ingestion notebook through the Job Scheduler API, then rebuilds and
tests the marts with dbt — the production heartbeat. Runs as whatever identity
`az login` established; the schedule uses the platform identity, which holds
Admin on every managed workspace.
"""

import argparse
import pathlib
import sys
import time

import requests
from azure.identity import AzureCliCredential

from deploy import API, get_all, run_dbt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True)
    ap.add_argument("--environment", required=True)
    args = ap.parse_args()

    cred = AzureCliCredential()
    token = cred.get_token("https://api.fabric.microsoft.com/.default").token
    headers = {"Authorization": f"Bearer {token}"}

    ws_name = f"ws-{args.solution}-{args.environment}"
    workspaces = get_all(f"{API}/workspaces", headers)
    ws = next((w for w in workspaces if w["displayName"] == ws_name), None)
    if not ws:
        sys.exit(f"workspace {ws_name} not visible to this identity")

    items = get_all(f"{API}/workspaces/{ws['id']}/items", headers)
    nb = next((i for i in items if i["type"] == "Notebook" and i["displayName"].startswith("nb_ingest")), None)
    if not nb and any(i["type"] == "Notebook" for i in items):
        # A rename outside the convention would otherwise turn the heartbeat into
        # a green no-op while ingestion silently stopped running.
        sys.exit("workspace has notebooks but none named nb_ingest* — ingestion would silently not run")
    # An item that triggers itself on Fabric's own scheduler must not be pushed
    # from here as well. The schedule ships in the item's definition, so the
    # workspace is the authority on whether it is live.
    if nb:
        live_schedules = requests.get(
            f"{API}/workspaces/{ws['id']}/items/{nb['id']}/jobs/Execute/schedules",
            headers=headers, timeout=60).json().get("value") or []
        if any(s.get("enabled") for s in live_schedules):
            print(f"{nb['displayName']} runs on Fabric's own scheduler — not triggering it here")
            nb = None

    if nb:
        print(f"running {nb['displayName']} via the Job Scheduler")
        r = requests.post(f"{API}/workspaces/{ws['id']}/items/{nb['id']}/jobs/instances?jobType=RunNotebook",
                          headers=headers, json={}, timeout=60)
        if r.status_code != 202:
            sys.exit(f"job submit failed: HTTP {r.status_code} {r.text[:200]}")
        loc = r.headers["Location"]
        for _ in range(90):
            time.sleep(10)
            job = requests.get(loc, headers=headers, timeout=60).json()
            if job.get("status") in ("Completed", "Failed", "Cancelled", "Deduped"):
                print(f"notebook job: {job['status']}")
                if job["status"] != "Completed":
                    sys.exit(f"notebook job ended {job['status']}: {str(job.get('failureReason'))[:300]}")
                break
        else:
            sys.exit("notebook job timed out")

    if (pathlib.Path("solutions") / args.solution / "dbt").is_dir():
        run_dbt(pathlib.Path("solutions") / args.solution, cred, headers, ws["id"], items)
    print("operate: complete")


if __name__ == "__main__":
    main()
