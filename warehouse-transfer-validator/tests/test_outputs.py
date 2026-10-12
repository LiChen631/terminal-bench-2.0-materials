# CANARY: WAREHOUSE_TRANSFER_VALIDATOR_TEST_CANARY_20260710
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def write_case(root: Path, warehouses: list[dict], files: dict[str, list[dict]]) -> Path:
    input_dir = root / "input"
    transfers = input_dir / "transfers"
    transfers.mkdir(parents=True)
    (input_dir / "warehouses.json").write_text(json.dumps({"warehouses": warehouses}), encoding="utf-8")
    for name, records in files.items():
        (transfers / name).write_text(json.dumps({"transfers": records}), encoding="utf-8")
    return input_dir


def run_validator(tmp_path: Path, warehouses: list[dict], files: dict[str, list[dict]]) -> dict:
    input_dir = write_case(tmp_path, warehouses, files)
    output = tmp_path / "out.json"
    app_root = Path(os.environ.get("APP_ROOT", "/app"))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(app_root) + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "warehouse_validator.audit", str(input_dir), str(output)],
        cwd=str(app_root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    assert output.exists(), "validator did not create output JSON"
    return json.loads(output.read_text(encoding="utf-8"))


def wh(wid: str, capacity: int, inventory: dict) -> dict:
    return {"id": wid, "capacity": capacity, "inventory": inventory}


def item(on_hand: int, reserved: int = 0, pack_size: int = 1) -> dict:
    return {"on_hand": on_hand, "reserved": reserved, "pack_size": pack_size}


def tr(tid: str, sku: str, source: str, dest: str, qty: int, ts: str) -> dict:
    return {
        "transfer_id": tid,
        "sku": sku,
        "source": source,
        "destination": dest,
        "qty": qty,
        "timestamp": ts,
    }


def test_basic_transfer_and_summary(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [
            wh("north", 50, {"widget": item(20, reserved=2, pack_size=2)}),
            wh("south", 50, {"widget": item(1, pack_size=2)}),
        ],
        {"a.json": [tr("T-1", "widget", "north", "south", 6, "2026-01-01T09:00:00Z")]},
    )
    assert [r["transfer_id"] for r in result["accepted"]] == ["t-1"]
    assert result["rejected"] == []
    assert result["inventory"]["north"]["widget"]["on_hand"] == 14
    assert result["inventory"]["south"]["widget"]["on_hand"] == 7
    assert result["summary"] == {"accepted_count": 1, "rejected_count": 0, "total_moved": {"widget": 6}}


def test_invalid_later_duplicate_does_not_shadow_earlier_valid(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [wh("a", 100, {"sku": item(9)}), wh("b", 100, {})],
        {
            "a.json": [
                tr("DUP-1", "sku", "a", "b", 5, "2026-01-01T08:00:00Z"),
                tr("dup-1", "sku", "a", "b", -5, "2026-01-01T08:01:00Z"),
            ]
        },
    )
    assert [r["transfer_id"] for r in result["accepted"]] == ["dup-1"]
    assert result["inventory"]["a"]["sku"]["on_hand"] == 4
    assert any(w["code"] == "invalid_transfer" and w.get("transfer_id") == "dup-1" for w in result["warnings"])


def test_later_valid_warehouse_definition_wins(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [
            wh("main", 100, {"bolt": item(5)}),
            wh("MAIN", 100, {"bolt": item(20)}),
            wh("dock", 100, {}),
        ],
        {"a.json": [tr("W-1", "bolt", "main", "dock", 12, "2026-01-01T08:00:00Z")]},
    )
    assert [r["transfer_id"] for r in result["accepted"]] == ["w-1"]
    assert result["inventory"]["main"]["bolt"]["on_hand"] == 8


def test_identity_fields_are_trimmed_and_casefolded(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [wh(" North ", 100, {"Widget": item(11)}), wh("SOUTH", 100, {})],
        {"a.json": [tr(" ID-Case ", " widget ", "north", " south ", 4, "2026-01-01T08:00:00Z")]},
    )
    assert result["accepted"][0]["transfer_id"] == "id-case"
    assert result["accepted"][0]["source"] == "north"
    assert result["accepted"][0]["destination"] == "south"
    assert result["inventory"]["north"]["widget"]["on_hand"] == 7


def test_reserved_units_are_not_available_to_ship(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [wh("a", 100, {"sku": item(10, reserved=6)}), wh("b", 100, {})],
        {"a.json": [tr("R-1", "sku", "a", "b", 5, "2026-01-01T08:00:00Z")]},
    )
    assert result["accepted"] == []
    assert result["rejected"][0]["reason"] == "insufficient_available_stock"
    assert result["inventory"]["a"]["sku"]["on_hand"] == 10


def test_destination_capacity_uses_realtime_total_across_all_skus(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [wh("a", 100, {"y": item(10)}), wh("b", 11, {"x": item(5)})],
        {"a.json": [tr("CAP-1", "y", "a", "b", 7, "2026-01-01T08:00:00Z")]},
    )
    assert result["accepted"] == []
    assert result["rejected"][0]["reason"] == "destination_capacity_exceeded"
    assert result["inventory"]["b"] == {"x": {"on_hand": 5, "reserved": 0, "pack_size": 1}}


def test_rejected_transfer_has_no_inventory_side_effect(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [wh("a", 100, {"sku": item(6, reserved=4)}), wh("b", 100, {}), wh("c", 100, {})],
        {
            "a.json": [
                tr("SIDE-1", "sku", "a", "b", 5, "2026-01-01T08:00:00Z"),
                tr("SIDE-2", "sku", "a", "c", 2, "2026-01-01T08:01:00Z"),
            ]
        },
    )
    assert [r["transfer_id"] for r in result["accepted"]] == ["side-2"]
    assert result["rejected"][0]["transfer_id"] == "side-1"
    assert result["inventory"]["a"]["sku"]["on_hand"] == 4
    assert result["inventory"]["c"]["sku"]["on_hand"] == 2


def test_pack_size_is_taken_from_source_item(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [
            wh("a", 100, {"sku": item(20, pack_size=4)}),
            wh("b", 100, {"sku": item(1, pack_size=3)}),
        ],
        {"a.json": [tr("PACK-1", "sku", "a", "b", 8, "2026-01-01T08:00:00Z")]},
    )
    assert [r["transfer_id"] for r in result["accepted"]] == ["pack-1"]
    assert result["inventory"]["a"]["sku"]["on_hand"] == 12
    assert result["inventory"]["b"]["sku"]["on_hand"] == 9


def test_selected_transfers_are_executed_by_timestamp_not_file_order(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [wh("a", 100, {"sku": item(20)}), wh("b", 10, {})],
        {
            "a.json": [
                tr("SECOND", "sku", "a", "b", 6, "2026-01-01T09:00:00Z"),
                tr("FIRST", "sku", "a", "b", 6, "2026-01-01T08:00:00Z"),
            ]
        },
    )
    assert [r["transfer_id"] for r in result["accepted"]] == ["first"]
    assert [r["transfer_id"] for r in result["rejected"]] == ["second"]
    assert result["rejected"][0]["reason"] == "destination_capacity_exceeded"


def test_valid_later_duplicate_is_selected_before_timeline_execution(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [wh("a", 100, {"sku": item(20)}), wh("b", 10, {})],
        {
            "a.json": [
                tr("OTHER", "sku", "a", "b", 6, "2026-01-01T09:00:00Z"),
                tr("DUP", "sku", "a", "b", 2, "2026-01-01T10:00:00Z"),
                tr("dup", "sku", "a", "b", 6, "2026-01-01T08:00:00Z"),
            ]
        },
    )
    assert [r["transfer_id"] for r in result["accepted"]] == ["dup"]
    assert [r["transfer_id"] for r in result["rejected"]] == ["other"]


def test_invalid_timestamp_and_same_warehouse_are_reported_deterministically(tmp_path: Path):
    result = run_validator(
        tmp_path,
        [wh("a", 100, {"sku": item(5)})],
        {
            "b.json": [
                tr("BAD-TS", "sku", "a", "a", 1, "2026-01-01 08:00:00"),
                tr("SAME", "sku", "a", "a", 1, "2026-01-01T08:01:00Z"),
            ]
        },
    )
    assert result["accepted"] == []
    assert result["rejected"] == [
        {
            "transfer_id": "same",
            "sku": "sku",
            "source": "a",
            "destination": "a",
            "qty": 1,
            "timestamp": "2026-01-01T08:01:00Z",
            "reason": "same_warehouse",
        }
    ]
    assert result["warnings"] == [
        {"code": "invalid_transfer", "detail": "b.json[0]", "transfer_id": "bad-ts"}
    ]


def test_output_keys_are_stable_for_empty_transfer_directory(tmp_path: Path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "transfers").mkdir()
    (input_dir / "warehouses.json").write_text(
        json.dumps({"warehouses": [wh("b", 50, {}), wh("a", 50, {"sku": item(1)})]}),
        encoding="utf-8",
    )
    output = tmp_path / "out.json"
    app_root = Path(os.environ.get("APP_ROOT", "/app"))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(app_root) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run(
        [sys.executable, "-m", "warehouse_validator.audit", str(input_dir), str(output)],
        cwd=str(app_root),
        env=env,
        check=True,
        timeout=20,
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert list(result["inventory"].keys()) == ["a", "b"]
    assert result["summary"] == {"accepted_count": 0, "rejected_count": 0, "total_moved": {}}
