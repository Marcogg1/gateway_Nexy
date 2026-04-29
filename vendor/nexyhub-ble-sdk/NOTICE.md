# nexyhub_ble — third-party SDK from Esse-ti

This directory contains the Python package portion of Esse-ti's NexyHub BLE
SDK. It is **not Aritco code**. We vendor it because the package is not
published to PyPI — Esse-ti delivers it as source via their SDK ZIP.

## Contents

- `setup.py` — packaging metadata (`nexyhub_ble`, version 0.7.0)
- `nexyhub_ble/` — Python package providing `GATTServer`, `Service`,
  `Characteristic`, exceptions, utils. Wraps `bless` / BlueZ / D-Bus.

These files are an exact copy of the corresponding files from the Esse-ti
delivery at:

```
.../Esse-ti/delivery/nexyhub-ble-sdk/nexyhub-ble-sdk/
```

The Dockerfile in the project root installs this directory via
`pip install /tmp/nexyhub-ble-sdk` during `docker build`, so the
GatewayApp container can `import nexyhub_ble` at runtime.

## Refreshing

When Esse-ti ships a new SDK version, replace this directory's contents
with the matching files from the new delivery. Only `setup.py` and the
`nexyhub_ble/` package are needed — the rest of Esse-ti's delivery
(their reference Dockerfile, docker-compose, scripts, host configs,
docs) is not used here.

## Modifications

Do not modify these files. If a fix is required, raise it with Esse-ti
and update via a new SDK release. Local patches diverge silently from
upstream and become a maintenance burden.
