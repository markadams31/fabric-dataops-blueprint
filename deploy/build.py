"""Pack one solution into an immutable bundle.

usage: build.py --solution NAME --sha GITSHA [--out DIR]

The bundle is the unit of deployment: the same bytes go to every environment.
A solution's directories say what it holds (the directory name is the
type); anything unrecognised fails the build rather than silently not deploying.
"""

import argparse
import hashlib
import json
import pathlib
import sys
import tarfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from importlib.metadata import version

from guards import KNOWN_FILES, LOCAL_ARTIFACTS, SOLUTION_DIRECTORIES  # single source of truth


def wanted(root: pathlib.Path, f: pathlib.Path) -> bool:
    """Bundle only source: local tool artifacts never travel."""
    return f.is_file() and not set(f.relative_to(root).parts) & LOCAL_ARTIFACTS


def content_digest(root: pathlib.Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in root.rglob("*") if wanted(root, p)):
        h.update(str(f.relative_to(root)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--out", default="dist")
    args = ap.parse_args()

    src = pathlib.Path("solutions") / args.solution
    if not src.is_dir():
        sys.exit(f"no such solution: {src}")

    directories = sorted(d.name for d in src.iterdir() if d.is_dir())
    unknown = [c for c in directories if c not in SOLUTION_DIRECTORIES]
    stray = [f.name for f in src.iterdir() if f.is_file() and f.name not in KNOWN_FILES]
    if unknown or stray:
        sys.exit(f"unclaimed content in {src}: dirs={unknown} files={stray} "
                 f"(a solution holds: {sorted(SOLUTION_DIRECTORIES)})")

    manifest = {
        "solution": args.solution,
        "source_sha": args.sha,
        "content_digest": content_digest(src),
        "directories": directories,
        "tools": {"python": sys.version.split()[0], "fabric-cicd": version("fabric-cicd")},
    }

    out = pathlib.Path(args.out)
    out.mkdir(exist_ok=True)
    bundle = out / f"{args.solution}-{args.sha}.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        tar.add(src, arcname=".",
                filter=lambda ti: None if set(pathlib.PurePath(ti.name).parts) & LOCAL_ARTIFACTS else ti)
    (out / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"built {bundle} digest={manifest['content_digest'][:16]}… holds={directories}")


if __name__ == "__main__":
    main()
