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


def read_platform(p: pathlib.Path, out: list[str]) -> dict | None:
    """Parse a .platform file; malformed JSON is a violation, not a crash."""
    try:
        d = json.loads(p.read_text())
        d["metadata"]["displayName"], d["metadata"]["type"], d["config"]["logicalId"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        out.append(f"{p}: invalid .platform ({e})")
        return None
    return d


GUARDS = [guard_unclaimed, guard_logical_ids, guard_platform_names,
          guard_foreign_guids, guard_format_lock]


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
