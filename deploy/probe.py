"""Re-test the platform assumptions this repository rests on, as a deploy identity.

Documentation about Fabric changes, contradicts itself, and goes stale; several
claims here have flipped when only a doc page backed them. Every probe below
answers one question by calling the API and reporting what came back, so the
evidence register records a measurement rather than a citation. Read-only or
self-cleaning: nothing it creates outlives the run.

    uv run python deploy/probe.py --workspace ws-sales-dev
"""

import argparse
import subprocess
import sys

import requests

FABRIC = "https://api.fabric.microsoft.com/v1"
POWERBI = "https://api.powerbi.com/v1.0/myorg"


def token(resource: str) -> str:
    out = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


def headers(resource: str = "https://api.fabric.microsoft.com") -> dict:
    return {"Authorization": f"Bearer {token(resource)}", "Content-Type": "application/json"}


def workspace_id(name: str) -> str:
    rows = requests.get(f"{FABRIC}/workspaces", headers=headers(), timeout=60).json()["value"]
    match = [w for w in rows if w["displayName"] == name]
    if not match:
        sys.exit(f"workspace {name!r} not visible to this identity")
    return match[0]["id"]


def items(ws: str) -> list:
    return requests.get(f"{FABRIC}/workspaces/{ws}/items", headers=headers(), timeout=60).json()["value"]


def probe_activator(ws: str) -> tuple[str, str]:
    """Does an Activator (Reflex) item accept a service principal? Docs disagree."""
    r = requests.post(f"{FABRIC}/workspaces/{ws}/items", headers=headers(), timeout=120,
                      json={"displayName": "zz_probe_reflex", "type": "Reflex"})
    if r.status_code in (200, 201, 202):
        created = [i for i in items(ws) if i["displayName"] == "zz_probe_reflex"]
        for i in created:
            requests.delete(f"{FABRIC}/workspaces/{ws}/items/{i['id']}", headers=headers(), timeout=60)
        return "SUPPORTED", f"HTTP {r.status_code}, item created and removed"
    return "REFUSED", f"HTTP {r.status_code} {r.text[:160]}"


def probe_execute_queries(ws: str) -> tuple[str, str]:
    """The long-open E14: does executeQueries work with the Power BI audience?"""
    model = [i for i in items(ws) if i["type"] == "SemanticModel"]
    if not model:
        return "SKIPPED", "no semantic model in this workspace"
    h = headers("https://analysis.windows.net/powerbi/api")
    r = requests.post(f"{POWERBI}/groups/{ws}/datasets/{model[0]['id']}/executeQueries",
                      headers=h, timeout=120,
                      json={"queries": [{"query": "EVALUATE ROW(\"probe\", 1)"}],
                            "serializerSettings": {"includeNulls": True}})
    if r.status_code == 200:
        return "WORKS", "HTTP 200 — the documented fallback is no longer needed"
    return "REFUSED", f"HTTP {r.status_code} {r.text[:160]}"


def probe_git_read(ws: str) -> tuple[str, str]:
    """The Git APIs are marked service-principal supported. Nothing here had tested it."""
    r = requests.get(f"{FABRIC}/workspaces/{ws}/git/connection", headers=headers(), timeout=60)
    if r.status_code == 200:
        state = r.json().get("gitConnectionState", "unknown")
        return "REACHABLE", f"HTTP 200, gitConnectionState={state}"
    return "REFUSED", f"HTTP {r.status_code} {r.text[:160]}"


def probe_warehouse_roles(ws: str) -> tuple[str, str]:
    """OneLake data access roles on a warehouse — measured as a user, not as an MI."""
    wh = [i for i in items(ws) if i["type"] == "Warehouse"]
    if not wh:
        return "SKIPPED", "no warehouse in this workspace"
    r = requests.get(f"{FABRIC}/workspaces/{ws}/items/{wh[0]['id']}/dataAccessRoles",
                     headers=headers(), timeout=60)
    if r.status_code == 200:
        return "SUPPORTED", "HTTP 200 — the over-grant could now be narrowed"
    return "UNSUPPORTED", f"HTTP {r.status_code} {r.text[:160]}"


PROBES = {
    "Activator accepts a service principal": probe_activator,
    "executeQueries with the Power BI audience": probe_execute_queries,
    "Git APIs reachable as a service principal": probe_git_read,
    "OneLake roles on a Warehouse": probe_warehouse_roles,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    args = ap.parse_args()
    ws = workspace_id(args.workspace)
    print(f"probing {args.workspace} ({ws})\n")
    width = max(len(k) for k in PROBES)
    for claim, fn in PROBES.items():
        try:
            verdict, detail = fn(ws)
        except (requests.RequestException, subprocess.CalledProcessError, KeyError) as exc:
            verdict, detail = "ERROR", str(exc)[:160]
        print(f"  {claim:<{width}}  {verdict:<12} {detail}")
    print("\nProbes report what the API returned. They assert nothing on their own.")


if __name__ == "__main__":
    main()
