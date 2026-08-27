# Quickstart: validating AIOT-183

## Prerequisites

- Branch `AIOT-183-lift-reidentification` checked out; `pip install -r requirements_host.txt`.
- For bench tests: one AHL rig (RS485, `/dev/ttyLP1`) and one 1000-series rig (RS232, `/dev/ttyLP6`), a gateway image built from this branch, access to the device twin in the test IoT Hub (see memory note "Test hub setup" — harness route `nexyhub-telemetryTesting`, consumer group `nhGwTest`).

## Unit level (every commit)

```bash
pytest utest/                 # all green; new tests in test_lift_proxy / test_modbus_handler / test_rs232_handler
python -m mypy .              # clean
```

Expected new test coverage (names indicative):

- `TestReidentifyLoop`: stops after identification; continues through `identify_lift` exceptions; sleeps `REIDENTIFY_INTERVAL` between rounds; exits cleanly on cancellation.
- `TestBind`: AHL/1k bind sets handler+lib, closes the loser, clears candidate refs, re-arms `_force_read_all`.
- `TestRunReportsLiftType`: `report_property("gw.liftType", "unknown")` at `run()` start when UNKNOWN; `"AHL"`/`"1k"` after late identification; `event_sender.lift_type` updated.
- `TestClose` in both handler modules: idempotent, `client` set to `None`, close errors logged not raised.

## Bench level (on `dev` after merge, integrated test stage — constitution Principle VI hardware test)

| # | Steps | Expected |
|---|---|---|
| T1 | Lift controller **off**. Boot gateway. Wait > 60 s. Read twin. Power lift. Wait ≤ 60 s. Read twin; invoke `la.read.lift-type` and `la.read.parameter`; watch telemetry. | Twin `gw.liftType` = `"unknown"` after boot; log shows periodic re-identification summaries (not one line per 5 s). After lift power: log "Lift identified …", twin flips to `"AHL"` / `"1k"`, `lt` = `"1"`/`"2"`, parameter read succeeds, telemetry `LIFT_TYPE` = real type, first poll pushes the full onChange list. Repeat on both rigs. |
| T1b | As T1, but pull the uplink (Wi-Fi/LTE) before powering the lift. Power lift, wait for the identification log line, then restore uplink. Read twin. | Identification succeeds offline (log). After reconnect the twin must show the real type. **If it still shows `"unknown"`**, the twin patch was lost while offline (`DeviceTwinReporter` is fire-and-forget) — that is AIOT-189 (reconnect re-sync) — record the result there; not a blocker for this PR. |
| T2 | Serial cable unplugged. Boot gateway. Leave ≥ 1 h. Sample `ls /proc/$(pidof python)/fd \| wc -l` and RSS at 0 / 30 / 60 min. Plug cable. Also sample log line rate (`wc -l` on the app log at 0 / 30 / 60 min). | Heartbeats every interval throughout; fd count and RSS flat; recovery as T1 after plugging; background probing adds no INFO/WARNING lines from `lift_identifier` (handler-level per-transaction lines remain — follow-up ticket). |
| T3 | Lift on first, then gateway (normal order). | Identical to current behaviour: identified in the startup burst, single `gw.liftType` report, no re-identification log lines. |
| T4 | While in T1's unknown phase, invoke the remote-reboot DDM. | Gateway reboots normally; re-identification never blocked the method path. |

These rows ARE the Jira verification comment: instructions for the tester on `dev` after merge (Gateway practice: bench runs integrated on `dev`, not per branch).

## What "done" looks like

- All bench rows (T1, T1b, T2, T3, T4) pass on both rigs; T1b outcome recorded even if it fails (it decides the reconnect re-report follow-up).
- Unit + mypy green.
- Backend dev acknowledged `"unknown"` value / mid-session `LIFT_TYPE` change in the PR.
