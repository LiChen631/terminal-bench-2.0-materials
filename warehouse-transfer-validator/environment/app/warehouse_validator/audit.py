from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass
class InventoryItem:
    on_hand: int
    reserved: int
    pack_size: int


@dataclass
class Warehouse:
    warehouse_id: str
    capacity: int
    inventory: dict[str, InventoryItem]


@dataclass
class TransferCandidate:
    transfer_id: str
    sku: str
    source: str
    destination: str
    qty: int
    timestamp: str
    timestamp_key: datetime
    source_file: str
    ordinal: int


def _json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _norm(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_ts(value: Any) -> tuple[str, datetime] | None:
    if not isinstance(value, str) or not _TS_RE.match(value):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return value, parsed


def _warning(warnings: list[dict[str, str]], code: str, transfer_id: str | None, detail: str) -> None:
    item = {"code": code, "detail": detail}
    if transfer_id is not None:
        item["transfer_id"] = transfer_id
    warnings.append(item)


def _load_warehouses(input_dir: Path, warnings: list[dict[str, str]]) -> dict[str, Warehouse]:
    path = input_dir / "warehouses.json"
    data = _json_load(path)
    rows = data.get("warehouses") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("warehouses.json must contain a warehouses list")

    warehouses: dict[str, Warehouse] = {}
    for idx, row in enumerate(rows):
        detail = f"warehouses[{idx}]"
        if not isinstance(row, dict):
            _warning(warnings, "invalid_warehouse", None, detail)
            continue
        wid = _norm(row.get("id"))
        cap = row.get("capacity")
        inv = row.get("inventory")
        if wid is None or not _is_int(cap) or cap < 0 or not isinstance(inv, dict):
            _warning(warnings, "invalid_warehouse", wid, detail)
            continue
        inventory: dict[str, InventoryItem] = {}
        valid_inventory = True
        for raw_sku, raw_item in inv.items():
            sku = _norm(raw_sku)
            if sku is None or not isinstance(raw_item, dict):
                _warning(warnings, "invalid_inventory_item", wid, f"{detail}.inventory.{raw_sku}")
                valid_inventory = False
                continue
            on_hand = raw_item.get("on_hand")
            reserved = raw_item.get("reserved", 0)
            pack_size = raw_item.get("pack_size", 1)
            if (
                not _is_int(on_hand)
                or on_hand < 0
                or not _is_int(reserved)
                or reserved < 0
                or reserved > on_hand
                or not _is_int(pack_size)
                or pack_size <= 0
            ):
                _warning(warnings, "invalid_inventory_item", wid, f"{detail}.inventory.{raw_sku}")
                valid_inventory = False
                continue
            inventory[sku] = InventoryItem(on_hand=on_hand, reserved=reserved, pack_size=pack_size)
        if valid_inventory and wid not in warehouses:
            warehouses[wid] = Warehouse(warehouse_id=wid, capacity=cap, inventory=inventory)
    return warehouses


def _iter_transfer_rows(input_dir: Path) -> list[tuple[str, int, Any]]:
    transfers_dir = input_dir / "transfers"
    if not transfers_dir.exists():
        return []
    rows: list[tuple[str, int, Any]] = []
    for path in sorted(transfers_dir.glob("*.json"), key=lambda p: p.name):
        data = _json_load(path)
        if isinstance(data, dict) and isinstance(data.get("transfers"), list):
            records = data["transfers"]
        elif isinstance(data, list):
            records = data
        else:
            records = []
        for idx, record in enumerate(records):
            rows.append((path.name, idx, record))
    return rows


def _select_transfers(input_dir: Path, warnings: list[dict[str, str]]) -> list[TransferCandidate]:
    selected: dict[str, TransferCandidate] = {}
    global_ordinal = 0
    for file_name, local_idx, record in _iter_transfer_rows(input_dir):
        global_ordinal += 1
        detail = f"{file_name}[{local_idx}]"
        if not isinstance(record, dict):
            _warning(warnings, "invalid_transfer", None, detail)
            continue
        tid = _norm(record.get("transfer_id"))
        sku = _norm(record.get("sku"))
        source = _norm(record.get("source"))
        destination = _norm(record.get("destination"))
        qty = record.get("qty")
        parsed_ts = _parse_ts(record.get("timestamp"))
        if (
            tid is None
            or sku is None
            or source is None
            or destination is None
            or not _is_int(qty)
            or qty <= 0
            or parsed_ts is None
        ):
            _warning(warnings, "invalid_transfer", tid, detail)
            if tid is not None:
                selected.pop(tid, None)
            continue
        timestamp, timestamp_key = parsed_ts
        selected[tid] = TransferCandidate(
            transfer_id=tid,
            sku=sku,
            source=source,
            destination=destination,
            qty=qty,
            timestamp=timestamp,
            timestamp_key=timestamp_key,
            source_file=file_name,
            ordinal=global_ordinal,
        )
    return sorted(selected.values(), key=lambda item: (item.source_file, item.ordinal))


def _warehouse_total(warehouse: Warehouse) -> int:
    return sum(item.on_hand for item in warehouse.inventory.values())


def _transfer_record(candidate: TransferCandidate, reason: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "transfer_id": candidate.transfer_id,
        "sku": candidate.sku,
        "source": candidate.source,
        "destination": candidate.destination,
        "qty": candidate.qty,
        "timestamp": candidate.timestamp,
    }
    if reason is not None:
        record["reason"] = reason
    return record


def _apply_transfers(warehouses: dict[str, Warehouse], transfers: list[TransferCandidate]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in transfers:
        source = warehouses.get(candidate.source)
        destination = warehouses.get(candidate.destination)
        reason: str | None = None
        if source is None:
            reason = "unknown_source"
        elif destination is None:
            reason = "unknown_destination"
        elif candidate.source == candidate.destination:
            reason = "same_warehouse"
        elif candidate.sku not in source.inventory:
            reason = "unknown_sku"
        else:
            source_item = source.inventory[candidate.sku]
            pack_item = destination.inventory.get(candidate.sku, source_item)
            if candidate.qty % pack_item.pack_size != 0:
                reason = "invalid_pack_quantity"
            elif source_item.on_hand < candidate.qty:
                reason = "insufficient_available_stock"
            elif destination.inventory.get(candidate.sku, InventoryItem(0, 0, 1)).on_hand + candidate.qty > destination.capacity:
                reason = "destination_capacity_exceeded"
        if reason is not None:
            rejected.append(_transfer_record(candidate, reason))
            continue

        source_item = source.inventory[candidate.sku]
        source_item.on_hand -= candidate.qty
        if candidate.sku not in destination.inventory:
            destination.inventory[candidate.sku] = InventoryItem(on_hand=0, reserved=0, pack_size=source_item.pack_size)
        destination.inventory[candidate.sku].on_hand += candidate.qty
        accepted.append(_transfer_record(candidate))
    return accepted, rejected


def _inventory_output(warehouses: dict[str, Warehouse]) -> dict[str, dict[str, dict[str, int]]]:
    result: dict[str, dict[str, dict[str, int]]] = {}
    for wid in sorted(warehouses):
        result[wid] = {}
        for sku in sorted(warehouses[wid].inventory):
            item = warehouses[wid].inventory[sku]
            result[wid][sku] = {"on_hand": item.on_hand, "reserved": item.reserved, "pack_size": item.pack_size}
    return result


def validate(input_dir: str | Path) -> dict[str, Any]:
    root = Path(input_dir)
    warnings: list[dict[str, str]] = []
    warehouses = _load_warehouses(root, warnings)
    transfers = _select_transfers(root, warnings)
    accepted, rejected = _apply_transfers(warehouses, transfers)
    total_moved: dict[str, int] = {}
    for record in accepted:
        sku = record["sku"]
        total_moved[sku] = total_moved.get(sku, 0) + record["qty"]
    warnings = sorted(warnings, key=lambda w: (w.get("code", ""), w.get("transfer_id", ""), w.get("detail", "")))
    return {
        "accepted": accepted,
        "rejected": rejected,
        "inventory": _inventory_output(warehouses),
        "warnings": warnings,
        "summary": {
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "total_moved": {sku: total_moved[sku] for sku in sorted(total_moved)},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate warehouse transfer requests.")
    parser.add_argument("input_dir")
    parser.add_argument("output_json")
    args = parser.parse_args(argv)
    try:
        result = validate(args.input_dir)
    except Exception as exc:  # keep CLI deterministic for malformed top-level inputs
        result = {
            "accepted": [],
            "rejected": [],
            "inventory": {},
            "warnings": [{"code": "fatal_input_error", "detail": str(exc)}],
            "summary": {"accepted_count": 0, "rejected_count": 0, "total_moved": {}},
        }
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
