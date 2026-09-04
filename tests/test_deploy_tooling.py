"""The release machinery, tested offline.

The repository's claim is that changes are tested in transit; until these existed,
the code doing the transiting was the part with no tests. Nothing here reaches a
cloud: every test runs against a temporary tree.
"""

import json
import pathlib
import subprocess
import sys
import tarfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "deploy"))
import build

import deploy
import solutions as solutions_mod

REPO = pathlib.Path(__file__).parent.parent


def a_solution(root: pathlib.Path, name: str = "demo") -> pathlib.Path:
    """A minimal but valid solution: one notebook and one dbt model."""
    sol = root / name
    nb = sol / "fabric" / "nb_ingest_orders.Notebook"
    nb.mkdir(parents=True)
    (nb / ".platform").write_text(json.dumps({
        "metadata": {"type": "Notebook", "displayName": "nb_ingest_orders"},
        "config": {"version": "2.0", "logicalId": "11111111-2222-3333-4444-555555555555"}}))
    (nb / "notebook-content.py").write_text("# demo\nprint('hello')\n")
    models = sol / "dbt" / "warehouse" / "models"
    models.mkdir(parents=True)
    (models / "fct_demo.sql").write_text("select 1 as id\n")
    return sol


# --- the reproducibility the README promises ------------------------------------

def test_content_digest_is_stable_across_runs(tmp_path):
    a_solution(tmp_path)
    assert build.content_digest(tmp_path / "demo") == build.content_digest(tmp_path / "demo")


def test_content_digest_is_independent_of_file_order(tmp_path):
    sol = a_solution(tmp_path)
    first = build.content_digest(sol)
    # Rewriting a file with identical bytes changes mtime and directory order.
    p = sol / "fabric" / "nb_ingest_orders.Notebook" / "notebook-content.py"
    body = p.read_text()
    p.unlink()
    (sol / "fabric" / "nb_ingest_orders.Notebook" / "zz_other.txt").write_text("x")
    (sol / "fabric" / "nb_ingest_orders.Notebook" / "zz_other.txt").unlink()
    p.write_text(body)
    assert build.content_digest(sol) == first


def test_content_digest_changes_when_content_changes(tmp_path):
    sol = a_solution(tmp_path)
    before = build.content_digest(sol)
    (sol / "dbt" / "warehouse" / "models" / "fct_demo.sql").write_text("select 2 as id\n")
    assert build.content_digest(sol) != before


# --- the bundle a deploy consumes ------------------------------------------------

def test_build_produces_a_bundle_and_a_manifest(tmp_path):
    # build.py resolves `solutions/<name>` relative to the working directory.
    a_solution(tmp_path / "solutions")
    out = tmp_path / "dist"
    r = subprocess.run([sys.executable, str(REPO / "deploy" / "build.py"),
                        "--solution", "demo", "--sha", "abc123", "--out", str(out)],
                       cwd=tmp_path, capture_output=True, text=True, check=False,
                       env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO / "deploy")})
    assert r.returncode == 0, r.stderr
    bundle = out / "demo-abc123.tar.gz"
    assert bundle.is_file()
    manifest = json.loads((out / "release-manifest.json").read_text())
    assert manifest["solution"] == "demo"
    assert manifest["source_sha"] == "abc123"
    assert len(manifest["content_digest"]) == 64
    with tarfile.open(bundle) as tar:
        names = tar.getnames()
    assert any(n.endswith("notebook-content.py") for n in names)
    assert any(n.endswith("fct_demo.sql") for n in names)


# --- resolution that must fail loudly rather than guess --------------------------

def test_one_returns_the_single_match():
    items = [{"type": "Warehouse", "displayName": "wh_analytics", "id": "w1"},
             {"type": "Lakehouse", "displayName": "lh_bronze", "id": "l1"}]
    assert deploy.one(items, "Warehouse", "wh_")["id"] == "w1"


def test_one_refuses_when_absent():
    with pytest.raises(SystemExit):
        deploy.one([{"type": "Lakehouse", "displayName": "lh_bronze", "id": "l1"}], "Warehouse", "wh_")


def test_one_refuses_when_ambiguous():
    """Two warehouses must stop a deploy, not silently pick the first."""
    items = [{"type": "Warehouse", "displayName": "wh_a", "id": "1"},
             {"type": "Warehouse", "displayName": "wh_b", "id": "2"}]
    with pytest.raises(SystemExit):
        deploy.one(items, "Warehouse", "wh_")


# --- what counts as a solution ---------------------------------------------------

def test_template_and_invalid_names_are_not_solutions(tmp_path):
    for name in ["sales", "_template", "Bad-Name", "x", "finance"]:
        (tmp_path / name).mkdir()
    assert [d.name for d in solutions_mod.solutions(tmp_path)] == ["finance", "sales"]


def test_the_matrix_command_emits_json():
    r = subprocess.run([sys.executable, str(REPO / "deploy" / "solutions.py"), "--json",
                        str(REPO / "solutions")], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["finance", "sales"]
