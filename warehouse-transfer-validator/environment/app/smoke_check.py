from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        input_dir = root / "input"
        transfers = input_dir / "transfers"
        transfers.mkdir(parents=True)
        (input_dir / "warehouses.json").write_text(
            json.dumps(
                {
                    "warehouses": [
                        {"id": "a", "capacity": 20, "inventory": {"sku": {"on_hand": 8, "reserved": 1, "pack_size": 2}}},
                        {"id": "b", "capacity": 20, "inventory": {}},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (transfers / "a.json").write_text(
            json.dumps(
                {
                    "transfers": [
                        {
                            "transfer_id": "t1",
                            "sku": "sku",
                            "source": "a",
                            "destination": "b",
                            "qty": 4,
                            "timestamp": "2026-01-01T08:00:00Z",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        output = root / "out.json"
        completed = subprocess.run(
            [sys.executable, "-m", "warehouse_validator.audit", str(input_dir), str(output)],
            cwd=str(Path(__file__).resolve().parent),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        if completed.returncode != 0 or not output.exists():
            return 1
        result = json.loads(output.read_text(encoding="utf-8"))
        if result.get("summary", {}).get("accepted_count") != 1:
            return 1
        if result.get("inventory", {}).get("a", {}).get("sku", {}).get("on_hand") != 4:
            return 1
    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
