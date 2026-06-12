# iot-test — GatewayApp DDM acceptance harness

Drives Azure IoT Hub from the dev PC against a real GW running the app:
invokes direct methods, patches the desired twin, monitors telemetry, and
asserts the EG-64 compressed-envelope contract. Nothing is deployed to the GW.

## Setup (once)

```
az login
az extension add --name azure-iot
```

Then fill in `iot_config.py`:
- `TEST_HUB_ALLOWLIST` — the test IoT hub name(s). The harness REFUSES to run
  against any hub not listed (defense against targeting prod).
- `TEST_DEVICE_ALLOWLIST` — bench device ids.

Create the dedicated consumer group on the hub once (never use `$Default`):

```
az iot hub consumer-group create --hub-name <test-hub> --resource-group <rg> --name nhGwTest
```

If the hub has custom message routes with `condition: true` (SmartFleet hubs
do), they swallow ALL device telemetry and the built-in `events` endpoint —
the thing `monitor-events` reads — receives nothing, so the telemetry group
sees 0 events forever. Add a copy route to the built-in endpoint once
(multi-route delivery is additive; existing routes and billing unaffected):

```
az iot hub message-route create --hub-name <test-hub> -g <rg> --route-name nexyhub-telemetryTesting --source devicemessages --endpoint-name events --enabled true --condition true
```

## Usage

Fully automated bench run — picks a safe write param from
`iot_config.SAFE_WRITE_PARAMS` (cosmetic lighting params from the Smartlift
Parameters spec), re-writes the current AR number, restores the param after:

```
python iot_test.py --hub <test-hub> --auto
```

Manual control over the write target:

```
python iot_test.py --hub <test-hub> --bench --write-param 1 --write-value 7
```

First time against a new target: add `--dry-run` and eyeball the printed az
commands before running for real.

No subscription RBAC (`AuthorizationFailed` on `Microsoft.Devices/IotHubs/read`)?
Pass the hub's `service` policy connection string as `--hub` instead of the
name — `az iot` then talks straight to the hub and skips ARM. The hub name
inside the connection string is still checked against the allowlist.

```
python iot_test.py --hub "HostName=<hub>.azure-devices.net;SharedAccessKeyName=service;SharedAccessKey=..." --auto
```

| Flag | Meaning |
|---|---|
| `--bench` | bare-LCM mode: write tests enabled, no value restore |
| `--auto` | automated bench run: safe params + AR auto-picked, params restored (implies `--bench`) |
| `--all-params` | with `--auto`: cycle every safe param instead of one random per value-shape class |
| `--write-param/--write-value` | required for write_readback + telemetry groups |
| `--ar-number` | la.write.ar-number happy path (default in `--auto`: `iot_config.TEST_AR_NUMBER`) |
| `--only <group>` | one of: read_only, malformed, device_errors, download_rejects, write_readback, twin, telemetry |
| `--consumer-group` | Event Hub consumer group (default `nhGwTest`) |
| `--telemetry-window` | monitor inactivity timeout, seconds after last event (default 15) |
| `--dry-run` | print az commands, execute nothing |
| `--unsafe-target` | bypass allowlists (you'd better know why) |
| `--out results.json` | write results JSON (gitignored) |

Exit code: 0 all pass, 1 any FAIL, 2 preflight refused — CI-ready.

## What it covers (and doesn't)

Covers the cloud-facing DDM contract: envelope shape, error codes,
malformed-payload 400s, download security rejects (no blob needed — validation
rejects before any fetch), twin patch hub-acceptance, and the EG-64
DDM-write telemetry fix (`la.parameters.update` with `source=la.parameter.ddm`).

In `--auto` mode the write_readback group picks ONE RANDOM param per
value-shape class in `iot_config.SAFE_WRITE_PARAM_CLASSES` (bool, small-int,
step16, 24bit — the write path is identical within a class, and randomness
sweeps all registers over repeated runs; `--all-params` cycles every param)
and runs each through all three write/read DDMs:
`la.write.parameter` (change value) → `la.read.parameter` (readback) →
`la.write.read.parameter` (restore original — testing the combined DDM and
undoing the change in one call). The AR number written is
`iot_config.TEST_AR_NUMBER` (991337), a known SmartFleet test AR.

The la.write.ar-number case is lift-type aware: AHL stores the AR in
read-only param 96 and the app rejects writes by design, so on AHL the
harness asserts the `PARAM_READ_ONLY` rejection envelope and that the
stored AR is unchanged; on 1K it asserts the happy path and readback.

Known limits:
- **Write readback is a cache echo, not persistence proof** (the write updates
  the cache; only a live re-read/restart proves the LCM stored it).
- **Twin desired changes apply on app restart** (desired-patch merge stub) —
  the twin group asserts hub-acceptance only.
- **Download happy-path needs a real SAS URL** — see cheatsheet.md; the
  transport itself is covered by `tests/test_blob_integration.py`.
- Telemetry monitoring depends on hub plumbing: the consumer group and the
  built-in-endpoint copy route from Setup must exist. The harness reads from
  slightly before monitor launch (`--enqueued-time`), surfaces monitor stderr
  on zero events, and retries once before failing.

## Safety

- Allowlisted hub + device or it refuses to start.
- Destructive DDMs (reboot/reset/fwu) are never invoked by any group.
- Invocations are paced 0.5 s apart (LCM processing-window floor).
- All monitor windows and subprocesses are time-bounded — no unattended loops.
