# Warehouse Transfer Validator

This is a bounded repair task for `/app/warehouse_validator/audit.py`.

Required workflow for the agent:

- Edit only `/app/warehouse_validator/audit.py`.
- Do not inspect or run `/tests`.
- Do not run pytest, fuzzers, generated tests, or broad searches.
- Read the target file at most once before patching.
- Prefer one focused patch.
- Run one final command batch only:

```bash
python3 -m py_compile /app/warehouse_validator/audit.py && python3 /app/smoke_check.py
```

When `SMOKE_OK` appears, stop immediately and mark the task complete using the outer terminus-2 response schema.
