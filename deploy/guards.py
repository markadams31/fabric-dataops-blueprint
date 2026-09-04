"""Repository guards: invariants a pull request must satisfy, no cloud access.

usage: guards.py [solutions-root]

Each guard returns a list of violation strings; any violation fails the run.
Guards protect against the mistakes that deploy cleanly and hurt later:
duplicated logicalIds, workspace GUIDs baked into definitions, legacy report
formats, files no component owns.
"""

import json
import pathlib
import re
import sys

import yaml

# The project's scope: what fabric-cicd deploys, plus dbt as the
# transformation engine. A new component type is one driver plus its name here.
KNOWN_COMPONENTS = {"fabric", "dbt"}
KNOWN_FILES = {"solution.yml", "parameter.yml", "README.md"}

GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
BANNED_FILES = {".pbix", ".abf"}
BANNED_NAMES = {"localSettings.json", "cache.abf", "notebook-settings.json"}
# Local tool artifacts: git-ignored, but present on developer machines — skipped.
LOCAL_ARTIFACTS = {"target", "logs", "dbt_packages", "__pycache__", ".user.yml"}

# Item types fabric-cicd will happily deploy but whose APIs refuse a service
# principal, so a deploy running as a managed identity fails at publish time with
# nothing catching it first. Derived from the identity tables that every operation
# in microsoft/fabric-rest-api-specs carries, filtered to the types fabric-cicd
# accepts. Reflex is deliberately absent: the stale item-type matrix says it is
# unsupported, and a live probe creating one as a deploy identity says otherwise.
# Re-check with the verify-claims workflow before trusting this list against a
# newer Fabric release.
SERVICE_PRINCIPAL_REFUSED = {
    "MLExperiment": "the whole MLExperiment CRUD surface answers No to service principals",
    "UserDataFunction": "the whole User Data Functions CRUD surface answers No to service principals",
}


def solutions(root: pathlib.Path):
    return sorted(d for d in root.iterdir() if d.is_dir() and d.name != "_template")


def guard_unclaimed(root: pathlib.Path) -> list[str]:
    """Every path in a solution belongs to a component or a known file."""
    out = []
    for sol in solutions(root):
        for entry in sorted(sol.iterdir()):
            if entry.is_dir() and entry.name not in KNOWN_COMPONENTS:
                out.append(f"{sol.name}: directory '{entry.name}/' matches no component type "
                           f"(known: {sorted(KNOWN_COMPONENTS)})")
            if entry.is_file() and entry.name not in KNOWN_FILES:
                out.append(f"{sol.name}: file '{entry.name}' is not a recognised solution file")
    return out


def guard_logical_ids(root: pathlib.Path) -> list[str]:
    """logicalIds are globally unique — never copy an item folder without a new one."""
    seen: dict[str, str] = {}
    out = []
    for p in sorted(root.rglob("*/.platform")):
        d = read_platform(p, out)
        if d is None:
            continue
        lid = d["config"]["logicalId"]
        where = str(p.parent.relative_to(root))
        if lid in seen:
            out.append(f"duplicate logicalId {lid}: '{seen[lid]}' and '{where}'")
        seen[lid] = where
    return out


def guard_platform_names(root: pathlib.Path) -> list[str]:
    """An item folder '<name>.<Type>' must match its .platform metadata."""
    out = []
    for p in sorted(root.rglob("*/.platform")):
        d = read_platform(p, out)
        if d is None:
            continue
        meta = d["metadata"]
        folder = p.parent.name
        expected = f"{meta['displayName']}.{meta['type']}"
        if folder != expected:
            out.append(f"'{folder}': .platform says displayName='{meta['displayName']}' "
                       f"type='{meta['type']}' (folder should be '{expected}')")
    return out


def guard_foreign_guids(root: pathlib.Path) -> list[str]:
    """No workspace/item GUIDs baked into definitions.

    Allowed: each file's own logicalId, the all-zeros placeholder, JSON schema
    URLs (contain no GUIDs), and Variable Library value sets — the sanctioned
    home for environment-specific identifiers.
    """
    out = []
    logical_ids = set()
    for p in root.rglob("*/.platform"):
        d = read_platform(p, [])
        if d:
            logical_ids.add(d["config"]["logicalId"])
    for sol in solutions(root):
        for comp in ("fabric", "dbt"):
            base = sol / comp
            if not base.is_dir():
                continue
            for f in sorted(p for p in base.rglob("*") if p.is_file()):
                rel_parts = set(f.relative_to(base).parts)
                if (".VariableLibrary" in str(f.relative_to(base)) or rel_parts & LOCAL_ARTIFACTS
                        or f.name == "parameter.yml"):  # the sanctioned rebinding home
                    continue
                for line in f.read_text(errors="ignore").splitlines():
                    if "lineageTag" in line:  # TMDL structural ids, not environment leakage
                        continue
                    for guid in set(GUID.findall(line)):
                        if guid.lower() == ZERO_GUID or guid in logical_ids:
                            continue
                        out.append(f"{f.relative_to(root)}: hardcoded GUID {guid} — "
                                   f"parameterize it (parameter.yml or the Variable Library)")
    return out


def guard_format_lock(root: pathlib.Path) -> list[str]:
    """PBIR reports only; no binaries or Fabric-generated local files."""
    out = []
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = f.relative_to(root)
        if f.suffix in BANNED_FILES or f.name in BANNED_NAMES:
            out.append(f"{rel}: '{f.name}' must not be committed")
    for report in sorted(root.rglob("*.Report")):
        if (report / "report.json").is_file() and not (report / "definition").is_dir():
            out.append(f"{report.relative_to(root)}: legacy report format — "
                       f"use PBIR (a definition/ folder), not top-level report.json")
    return out


def guard_contract_targets(root: pathlib.Path) -> list[str]:
    """A shortcut into another solution's warehouse must name a table that
    solution still builds.

    Renaming a mart is invisible to the team that owns it: dbt leaves the old
    table behind, so the consumer's shortcut keeps resolving and its data
    quietly stops changing — no error, anywhere, ever. The producer is read
    from the contract's own placeholder (`SALES_WORKSPACE_ID` names `sales`),
    which is why contracts are written with placeholders rather than GUIDs.
    Only schema-qualified warehouse paths are checked; lakehouse shortcuts are
    free-form.
    """
    def models_of(solution: pathlib.Path) -> set[str]:
        return {p.stem for p in solution.rglob("*.sql")
                if "dbt" in p.parts and "models" in p.parts}

    out = []
    for f in sorted(root.rglob("shortcuts.metadata.json")):
        try:
            shortcuts = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            out.append(f"{f.relative_to(root)}: invalid JSON ({e})")
            continue
        for sc in shortcuts if isinstance(shortcuts, list) else []:
            target = ((sc.get("target") or {}).get("oneLake") or {})
            parts = str(target.get("path", "")).strip("/").split("/")
            if len(parts) != 3 or parts[0] != "Tables":
                continue
            m = re.fullmatch(r"([A-Z][A-Z0-9]*)_WORKSPACE_ID", str(target.get("workspaceId", "")))
            if not m:
                out.append(f"{f.relative_to(root)}: shortcut '{sc.get('name')}' does not name "
                           f"its producer — use a <PRODUCER>_WORKSPACE_ID placeholder so the "
                           f"contract can be checked")
                continue
            producer = root / m.group(1).lower()
            if not producer.is_dir():
                out.append(f"{f.relative_to(root)}: shortcut '{sc.get('name')}' names producer "
                           f"'{m.group(1).lower()}', which is not a solution in this repository")
            elif parts[2] not in models_of(producer):
                out.append(f"{f.relative_to(root)}: shortcut '{sc.get('name')}' targets "
                           f"{'/'.join(parts)}, but {m.group(1).lower()} builds no model named "
                           f"'{parts[2]}' — a renamed model leaves this consumer reading a table "
                           f"that never updates again")
    return out


def guard_parameter_targets(root: pathlib.Path) -> list[str]:
    """Every rewrite in parameter.yml must still have something to rewrite.

    Fabric normalises a definition when a workspace commits it — a semantic
    model's expression moves out of model.tmdl into its own expressions.tmdl,
    for one — so authoring in the portal can leave a rewrite pointing at a file
    that no longer holds its placeholder. fabric-cicd then replaces nothing, and
    the item deploys still bound to whatever workspace the author was using.
    """
    out = []
    for f in sorted(root.rglob("fabric/parameter.yml")):
        rel = f.relative_to(root)
        try:
            doc = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as e:
            out.append(f"{rel}: invalid YAML ({e})")
            continue
        for entry in doc.get("find_replace", []) or []:
            find = entry.get("find_value")
            path = str(entry.get("file_path") or "").lstrip("/")
            if not find or not path:
                continue  # no file_path means "anywhere in the tree"
            target = f.parent / path
            if not target.is_file():
                out.append(f"{rel}: rewrites '{path}', which this solution does not ship")
            elif find not in target.read_text(errors="ignore"):
                out.append(f"{rel}: '{find}' no longer appears in {path} — the rewrite would "
                           f"replace nothing and the item would deploy bound to its author's "
                           f"workspace")
    return out


def read_platform(p: pathlib.Path, out: list[str]) -> dict | None:
    """Parse a .platform file; malformed JSON is a violation, not a crash."""
    try:
        d = json.loads(p.read_text())
        d["metadata"]["displayName"], d["metadata"]["type"], d["config"]["logicalId"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        out.append(f"{p}: invalid .platform ({e})")
        return None
    return d


def guard_service_principal_types(root: pathlib.Path) -> list[str]:
    """No item whose API refuses the identity that deploys it."""
    out = []
    for sol in solutions(root):
        for platform in sorted((sol / "fabric").rglob(".platform")):
            try:
                meta = json.loads(platform.read_text()).get("metadata", {})
            except json.JSONDecodeError:
                continue  # guard_platform_names reports malformed files
            why = SERVICE_PRINCIPAL_REFUSED.get(meta.get("type", ""))
            if why:
                out.append(
                    f"{sol.name}: {platform.parent.name} is a {meta['type']}, which cannot be "
                    f"deployed by this repository's identity model — {why}. Deploys run as "
                    f"mi-deploy-{sol.name}, so this would fail at publish time"
                )
    return out


GUARDS = [guard_unclaimed, guard_logical_ids, guard_platform_names,
          guard_foreign_guids, guard_format_lock, guard_contract_targets,
          guard_parameter_targets, guard_service_principal_types]


def run(root: pathlib.Path) -> list[str]:
    violations = []
    for g in GUARDS:
        violations += g(root)
    return violations


def main() -> None:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "solutions")
    violations = run(root)
    for v in violations:
        print(f"GUARD: {v}")
    if violations:
        sys.exit(f"{len(violations)} guard violation(s)")
    print(f"guards ok: {len(GUARDS)} guards, {len(list(solutions(root)))} solution(s)")


if __name__ == "__main__":
    main()
