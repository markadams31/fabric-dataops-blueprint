"""Every guard has a failing fixture: a planted defect each guard must catch."""

import json
import pathlib
import subprocess
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "deploy"))
import guards


def item(root, sol, name, itype, logical_id=None):
    d = root / sol / "fabric" / f"{name}.{itype}"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".platform").write_text(json.dumps({
        "metadata": {"type": itype, "displayName": name},
        "config": {"version": "2.0", "logicalId": logical_id or str(uuid.uuid4())},
    }))
    return d


def test_clean_tree_passes(tmp_path):
    item(tmp_path, "s1", "nb_a", "Notebook")
    assert guards.run(tmp_path) == []


def test_unclaimed_directory_fails(tmp_path):
    item(tmp_path, "s1", "nb_a", "Notebook")
    (tmp_path / "s1" / "mystery").mkdir()
    assert any("mystery" in v for v in guards.run(tmp_path))


def test_unclaimed_file_fails(tmp_path):
    item(tmp_path, "s1", "nb_a", "Notebook")
    (tmp_path / "s1" / "notes.txt").write_text("x")
    assert any("notes.txt" in v for v in guards.run(tmp_path))


def test_duplicate_logical_id_fails(tmp_path):
    lid = str(uuid.uuid4())
    item(tmp_path, "s1", "nb_a", "Notebook", lid)
    item(tmp_path, "s1", "nb_b", "Notebook", lid)
    assert any("duplicate logicalId" in v for v in guards.run(tmp_path))


def test_folder_platform_mismatch_fails(tmp_path):
    d = item(tmp_path, "s1", "nb_a", "Notebook")
    d.rename(d.parent / "nb_renamed.Notebook")
    assert any("nb_renamed" in v for v in guards.run(tmp_path))


def test_foreign_guid_fails(tmp_path):
    d = item(tmp_path, "s1", "nb_a", "Notebook")
    (d / "notebook-content.py").write_text('ws = "12345678-1234-1234-1234-123456789abc"')
    assert any("hardcoded GUID" in v for v in guards.run(tmp_path))


def test_zero_guid_and_variable_library_allowed(tmp_path):
    d = item(tmp_path, "s1", "nb_a", "Notebook")
    (d / "notebook-content.py").write_text(f'ws = "{guards.ZERO_GUID}"')
    vl = item(tmp_path, "s1", "vl", "VariableLibrary")
    (vl / "variables.json").write_text('{"v": "12345678-1234-1234-1234-123456789abc"}')
    assert guards.run(tmp_path) == []


def test_legacy_report_format_fails(tmp_path):
    d = item(tmp_path, "s1", "rpt", "Report")
    (d / "report.json").write_text("{}")
    assert any("legacy report format" in v for v in guards.run(tmp_path))


def test_banned_file_fails(tmp_path):
    d = item(tmp_path, "s1", "nb_a", "Notebook")
    (d / "notebook-settings.json").write_text("{}")
    assert any("notebook-settings.json" in v for v in guards.run(tmp_path))


def test_real_solutions_tree_is_clean():
    root = pathlib.Path(__file__).parent.parent / "solutions"
    assert guards.run(root) == []


def test_build_digest_is_deterministic(tmp_path):
    repo = pathlib.Path(__file__).parent.parent
    out = []
    for run_dir in ("a", "b"):
        r = subprocess.run(
            [sys.executable, "deploy/build.py", "--solution", "sales",
             "--sha", "test", "--out", str(tmp_path / run_dir)],
            cwd=repo, capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stderr
        out.append(json.loads((tmp_path / run_dir / "release-manifest.json").read_text())["content_digest"])
    assert out[0] == out[1]


def test_foreign_guid_in_dbt_fails(tmp_path):
    item(tmp_path, "s1", "nb_a", "Notebook")
    d = tmp_path / "s1" / "dbt" / "warehouse" / "models"
    d.mkdir(parents=True)
    (d / "stg.sql").write_text('select "12345678-1234-1234-1234-123456789abc" as ws')
    assert any("hardcoded GUID" in v for v in guards.run(tmp_path))


def test_malformed_platform_is_a_violation(tmp_path):
    d = item(tmp_path, "s1", "nb_a", "Notebook")
    (d / ".platform").write_text("{not json")
    assert any("invalid .platform" in v for v in guards.run(tmp_path))


def test_local_dbt_artifacts_are_ignored(tmp_path):
    item(tmp_path, "s1", "nb_a", "Notebook")
    d = tmp_path / "s1" / "dbt" / "warehouse" / "logs"
    d.mkdir(parents=True)
    (d / "dbt.log").write_text('guid 12345678-1234-1234-1234-123456789abc')
    assert guards.run(tmp_path) == []


def test_tmdl_lineage_tags_allowed(tmp_path):
    d = item(tmp_path, "s1", "sm", "SemanticModel")
    (d / "model.tmdl").write_text(
        "model Model\n\tlineageTag: 12345678-1234-1234-1234-123456789abc\n")
    assert guards.run(tmp_path) == []


def test_parameter_yml_guids_allowed(tmp_path):
    item(tmp_path, "s1", "nb_a", "Notebook")
    (tmp_path / "s1" / "fabric" / "parameter.yml").write_text(
        'find_replace:\n  - find_value: "X"\n    replace_value:\n      dev: "12345678-1234-1234-1234-123456789abc"\n')
    assert guards.run(tmp_path) == []


def shortcut(tmp_path, consumer, producer_placeholder, target_path):
    d = tmp_path / consumer / "fabric" / "lh_x.Lakehouse"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".platform").write_text(json.dumps({
        "metadata": {"type": "Lakehouse", "displayName": "lh_x"},
        "config": {"logicalId": "aaaaaaaa-1111-2222-3333-444444444444"}}))
    (d / "shortcuts.metadata.json").write_text(json.dumps(
        [{"path": "Tables", "name": "borrowed",
          "target": {"oneLake": {"workspaceId": producer_placeholder,
                                 "itemId": "X_ITEM_ID", "path": target_path}}}]))
    return d


def model(tmp_path, solution, name):
    m = tmp_path / solution / "dbt" / "warehouse" / "models" / "marts"
    m.mkdir(parents=True, exist_ok=True)
    (m / f"{name}.sql").write_text("select 1")


def test_contract_target_missing_is_caught(tmp_path):
    """The producer renamed its mart; the consumer's shortcut now points at a
    table dbt will never rebuild."""
    shortcut(tmp_path, "consumer", "PRODUCER_WORKSPACE_ID", "Tables/gold/fct_orders")
    model(tmp_path, "producer", "fct_orders_daily")
    assert any("never updates again" in v for v in guards.run(tmp_path))


def test_contract_checks_the_named_producer_only(tmp_path):
    """A same-named model in an unrelated solution must not satisfy the contract."""
    shortcut(tmp_path, "consumer", "PRODUCER_WORKSPACE_ID", "Tables/gold/fct_orders")
    model(tmp_path, "producer", "fct_orders_daily")
    model(tmp_path, "unrelated", "fct_orders")
    assert any("never updates again" in v for v in guards.run(tmp_path))


def test_contract_target_present_is_allowed(tmp_path):
    shortcut(tmp_path, "consumer", "PRODUCER_WORKSPACE_ID", "Tables/gold/fct_orders")
    model(tmp_path, "producer", "fct_orders")
    assert guards.run(tmp_path) == []


def test_lakehouse_shortcut_is_not_a_contract(tmp_path):
    """Two-part paths are lakehouse tables, not dbt output — free-form."""
    shortcut(tmp_path, "consumer", "PRODUCER_WORKSPACE_ID", "Tables/customers")
    assert guards.run(tmp_path) == []


def schedules(tmp_path, solution, item, item_type, job_type="RunNotebook"):
    f = tmp_path / solution / "fabric"
    f.mkdir(parents=True, exist_ok=True)
    (f / "schedules.yml").write_text(
        f"schedules:\n  - item: {item}\n    item_type: {item_type}\n"
        f"    job_type: {job_type}\n    configuration:\n      type: Cron\n")


def test_schedule_for_missing_item_is_caught(tmp_path):
    """The notebook was renamed; the trigger now names nothing."""
    item(tmp_path, "s1", "nb_ingest_new", "Notebook")
    schedules(tmp_path, "s1", "nb_ingest_old", "Notebook")
    assert any("never fire" in v for v in guards.run(tmp_path))


def test_schedule_for_shipped_item_is_allowed(tmp_path):
    item(tmp_path, "s1", "nb_ingest_orders", "Notebook")
    schedules(tmp_path, "s1", "nb_ingest_orders", "Notebook")
    assert guards.run(tmp_path) == []
