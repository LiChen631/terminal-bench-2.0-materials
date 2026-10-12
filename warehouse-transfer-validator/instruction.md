# Warehouse Transfer Validator

This is a bounded repair task.

- Edit only `/app/warehouse_validator/audit.py`.
- Do not inspect or run `/tests`.
- Do not run pytest, fuzzers, random tests, or generated test suites.
- Read `/app/warehouse_validator/audit.py` at most once before patching.
- Prefer one focused patch instead of repeated exploratory edits.
- Run exactly one final self-check command batch:

```bash
python3 -m py_compile /app/warehouse_validator/audit.py && python3 /app/smoke_check.py
```

- If `SMOKE_OK` appears, do not run another command.
- Finish with `task_complete=true` and `commands=[]` using the outer terminus-2 JSON schema.
- If completion is requested again, confirm immediately without new analysis.

## Goal

Repair the Python CLI at `/app/warehouse_validator/audit.py`. The command must validate warehouse transfer requests, apply only accepted transfers to in-memory inventory, and write a deterministic JSON report.

CLI:

```bash
python -m warehouse_validator.audit INPUT_DIR OUTPUT_JSON
```

The process must exit with status code `0` and create `OUTPUT_JSON`. For malformed top-level input files, still write a JSON report with no accepted transfers and a `fatal_input_error` warning instead of crashing.

## Input layout

`INPUT_DIR` contains:

```text
INPUT_DIR/
├── warehouses.json
└── transfers/
    ├── <any-name>.json
    └── ...
```

`warehouses.json` must contain:

```json
{
  "warehouses": [
    {
      "id": "north",
      "capacity": 100,
      "inventory": {
        "widget": {"on_hand": 20, "reserved": 2, "pack_size": 2}
      }
    }
  ]
}
```

Each transfer file may either be a JSON list of transfer objects or an object with a `transfers` list:

```json
{
  "transfers": [
    {
      "transfer_id": "T-1",
      "sku": "widget",
      "source": "north",
      "destination": "south",
      "qty": 4,
      "timestamp": "2026-01-01T08:00:00Z"
    }
  ]
}
```

## Normalization and validation rules

Identifiers for warehouses, SKUs, and transfer IDs are normalized with `strip()` followed by Unicode `casefold()`. Empty normalized identifiers are invalid. Output records must use normalized identifiers.

Integers must be JSON integers, not booleans. Warehouse `capacity`, item `on_hand`, item `reserved`, item `pack_size`, and transfer `qty` are invalid if they use booleans or non-integer values. `capacity`, `on_hand`, and `reserved` must be non-negative. `reserved` must not exceed `on_hand`. `pack_size` defaults to `1` and must be positive. Transfer `qty` must be positive.

Timestamps are valid only when they are strict UTC RFC3339 seconds in the form `YYYY-MM-DDTHH:MM:SSZ` and represent a real calendar time.

Valid duplicate warehouses are resolved by normalized warehouse ID. Later valid warehouse definitions win. Invalid later warehouse definitions do not shadow earlier valid definitions.

Transfers are selected in two phases:

1. Validate candidate records from transfer files in lexicographic file-name order and in-file list order.
2. Resolve duplicates by normalized `transfer_id`; the later valid candidate wins. Invalid later candidates do not shadow earlier valid candidates.

After transfer selection, execute the selected transfers in chronological order by `(timestamp, source file name, original input ordinal)`.

## Transfer execution rules

For each selected transfer, reject it without changing inventory when the first applicable reason below applies:

1. `unknown_source` when the source warehouse does not exist.
2. `unknown_destination` when the destination warehouse does not exist.
3. `same_warehouse` when normalized source and destination are the same.
4. `unknown_sku` when the normalized SKU is absent from the source warehouse.
5. `invalid_pack_quantity` when `qty` is not a multiple of the source inventory item's `pack_size`.
6. `insufficient_available_stock` when `source.on_hand - source.reserved < qty`.
7. `destination_capacity_exceeded` when the destination's real-time total `on_hand` across all SKUs plus `qty` would exceed destination `capacity`.

Accepted transfers reduce the source item's `on_hand` by `qty` and increase the destination item's `on_hand` by `qty`. If the destination lacks that SKU, create it with `on_hand=0`, `reserved=0`, and the source item's `pack_size` before applying the inbound quantity. Rejected transfers must not change any inventory or capacity state.

## Output JSON schema

Write a deterministic JSON object:

```json
{
  "accepted": [
    {
      "transfer_id": "t-1",
      "sku": "widget",
      "source": "north",
      "destination": "south",
      "qty": 4,
      "timestamp": "2026-01-01T08:00:00Z"
    }
  ],
  "rejected": [
    {
      "transfer_id": "t-2",
      "sku": "widget",
      "source": "north",
      "destination": "south",
      "qty": 99,
      "timestamp": "2026-01-01T09:00:00Z",
      "reason": "insufficient_available_stock"
    }
  ],
  "inventory": {
    "north": {
      "widget": {"on_hand": 16, "reserved": 2, "pack_size": 2}
    }
  },
  "warnings": [
    {"code": "invalid_transfer", "transfer_id": "bad", "detail": "a.json[0]"}
  ],
  "summary": {
    "accepted_count": 1,
    "rejected_count": 1,
    "total_moved": {"widget": 4}
  }
}
```

`accepted` and `rejected` are ordered by transfer execution order. `inventory` warehouse keys and SKU keys are sorted lexicographically. `summary.total_moved` keys are sorted lexicographically.

Warnings must be deterministic. Use these warning codes when applicable: `invalid_warehouse`, `invalid_inventory_item`, `invalid_transfer`, and `fatal_input_error`. Sort warnings by `(code, transfer_id or "", detail)`.
