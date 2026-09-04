"""The one place that decides what counts as a solution.

usage: solutions.py [--json] [root]

A solution is a directory under `solutions/` whose name matches the naming rule.
The rule is not cosmetic: the name becomes a GitHub variable name and a workspace
name, so hyphens and capitals are excluded. Both the guards and the build matrix
read this, so the tree stays the single source of truth for which solutions exist.
"""

import argparse
import json
import pathlib
import re
import sys

# Lowercase alphanumeric, at least two characters: the name becomes part of
# `AZURE_CLIENT_ID_<name>` and `ws-<name>-dev`, neither of which tolerates a hyphen.
NAME = re.compile(r"[a-z][a-z0-9]+")


def solutions(root: pathlib.Path) -> list[pathlib.Path]:
    """Every solution directory under root, in a stable order."""
    return sorted(d for d in root.iterdir()
                  if d.is_dir() and d.name != "_template" and NAME.fullmatch(d.name))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="solutions")
    ap.add_argument("--json", action="store_true", help="emit a JSON array for a workflow matrix")
    args = ap.parse_args()
    root = pathlib.Path(args.root)
    if not root.is_dir():
        sys.exit(f"{root} is not a directory")
    names = [d.name for d in solutions(root)]
    print(json.dumps(names) if args.json else "\n".join(names))


if __name__ == "__main__":
    main()
