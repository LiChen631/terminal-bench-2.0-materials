#!/bin/bash
# CANARY: WAREHOUSE_TRANSFER_VALIDATOR_VERIFIER_CANARY_20260710
set -u

mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt

export APP_ROOT=/app
export PYTHONPATH=/app:${PYTHONPATH:-}

if python3 -m pytest -q --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py; then
  printf '1\n' > /logs/verifier/reward.txt
  exit 0
fi

exit 0
