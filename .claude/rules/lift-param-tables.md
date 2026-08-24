---
paths:
  - "src/lib/ahl_lib.py"
  - "src/lib/thousand_lib.py"
  - "config.json"
---

Hand-maintained lift parameter tables and runtime config (AHL Modbus parameters, 1000-series
RS232 signals, shared-file-system config). Preserve the tuned values and their ordering, don't
reformat, and explain any value change before making it. The parameter cross-reference CSVs in
`Code/Aritco/GW/` are the reference source — ask first if a change isn't backed by one.
