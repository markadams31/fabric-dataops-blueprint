"""Rebuild and test one solution's marts against one environment.

usage: run_dbt.py --solution NAME --environment ENV

The nightly heartbeat. Ingestion is deliberately not triggered from here: the
notebook carries its own `.schedules`, which Fabric applies and runs, so when a
run happens is the platform's business rather than this repository's. dbt reads
the Bronze files directly with OPENROWSET, so it does not wait on that run.
"""

import argparse
import pathlib
import sys

from azure.identity import AzureCliCredential

from deploy import API, get_all, run_dbt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True)
    ap.add_argument("--environment", required=True)
    args = ap.parse_args()

    solution = pathlib.Path("solutions") / args.solution
    if not (solution / "dbt").is_dir():
        print(f"{args.solution} has no dbt component — nothing to rebuild")
        return

    cred = AzureCliCredential()
    headers = {"Authorization": f"Bearer {cred.get_token('https://api.fabric.microsoft.com/.default').token}"}

    ws_name = f"ws-{args.solution}-{args.environment}"
    ws = next((w for w in get_all(f"{API}/workspaces", headers)
               if w["displayName"] == ws_name), None)
    if not ws:
        sys.exit(f"workspace {ws_name} not visible to this identity")

    run_dbt(solution, cred, headers, ws["id"], get_all(f"{API}/workspaces/{ws['id']}/items", headers))
    print("marts rebuilt and tested")


if __name__ == "__main__":
    main()
