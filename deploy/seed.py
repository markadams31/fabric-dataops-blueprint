"""Load this demo's sample source data into one environment's Bronze lakehouse.

usage: seed.py --solution NAME --environment ENV

**This stands in for ingestion, and it is deliberately not part of deploying.**
A deploy rebuilds derived data — running the dbt project is what deploying a dbt
project means — but it must never write source data, or redeploying to fix a
report silently overwrites Bronze. A real solution deletes this step and lets its
own ingestion fill the lakehouse.
"""

import argparse
import sys

from azure.identity import AzureCliCredential

from deploy import API, get_all, seed_bronze


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True)
    ap.add_argument("--environment", required=True)
    args = ap.parse_args()

    cred = AzureCliCredential()
    headers = {"Authorization": f"Bearer {cred.get_token('https://api.fabric.microsoft.com/.default').token}"}
    ws_name = f"ws-{args.solution}-{args.environment}"
    ws = next((w for w in get_all(f"{API}/workspaces", headers)
               if w["displayName"] == ws_name), None)
    if not ws:
        sys.exit(f"workspace {ws_name} not visible to this identity")
    seed_bronze(cred, headers, ws["id"], get_all(f"{API}/workspaces/{ws['id']}/items", headers))


if __name__ == "__main__":
    main()
