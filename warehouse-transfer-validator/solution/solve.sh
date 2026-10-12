#!/bin/bash
# CANARY: WAREHOUSE_TRANSFER_VALIDATOR_SOLUTION_CANARY_20260710
set -euo pipefail

cp /solution/audit.py /app/warehouse_validator/audit.py
python3 -m py_compile /app/warehouse_validator/audit.py
