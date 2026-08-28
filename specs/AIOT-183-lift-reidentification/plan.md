# Implementation Plan: Background lift re-identification when lift type is UNKNOWN

**Branch**: `AIOT-183-lift-reidentification` | **Date**: 2026-08-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/AIOT-183-lift-reidentification/spec.md`

## Summary

`LiftProxy` currently identifies the lift exactly once in `create()` (10 × 5 s burst) and, on UNKNOWN, drops both handlers and never probes again. This plan keeps both handlers alive while UNKNOWN, adds a `_reidentify_loop()` coroutine to `LiftProxy.run()` that re-probes every `REIDENTIFY_INTERVAL` s until a lift answers, then binds the matched handler/lib pair under the existing `_handler_lock`, closes the losing handler's serial port (AUD-033), re-arms the cold-start full read, updates the telemetry lift-type tag and reports `gw.liftType` to the twin. `run()` also stops skipping the twin report on UNKNOWN so the cloud sees `"unknown"` instead of a stale value. Pure application-level change inside `src/liftApi/lift_proxy.py` + two small handler `close()` methods; no contract or image change.

## Technical Context

**Language/Version**: Python 3.14 (async/await, `match`), as per repo.

**Primary Dependencies**: stdlib `asyncio`; existing `pymodbus` (`ModbusSerialClient`) and `pyserial` (`serial.Serial`) handlers; `azure-iot-device` for twin/telemetry (unchanged usage).

**Storage**: N/A (in-memory lift-type state only).

**Testing**: `unittest` (`IsolatedAsyncioTestCase`) under `utest/`, run with `pytest utest/`; `python -m mypy .` gate; conventions in `.claude/rules/unit-tests.md`.

**Target Platform**: `linux/arm64` container on Esse-ti NexyHub gateway; RS485 `/dev/ttyLP1` (AHL), RS232 `/dev/ttyLP6` (1000-series).

**Project Type**: single async service (`src/main.py` orchestrating handlers via `asyncio.gather`).

**Performance Goals**: identified ≤ 60 s after lift becomes responsive (SC-001); probe cost negligible (one Modbus read, one RS232 query per cycle).

**Constraints**: must not block the event loop (serial I/O via `asyncio.to_thread` as today); must not hold `_handler_lock` longer than one probe round; offline-capable (no cloud dependency); no growth in handles/memory over 24 h (SC-003).

**Scale/Scope**: 1 proxy, 2 handlers, 1 background task; ~120 LOC change + ~150 LOC tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I Spec-First | PASS | spec.md → this plan → `/speckit-tasks` → `/speckit-implement` (subagent-driven). Bug with contained root cause, but cross-cutting enough (proxy, event sender, handlers, twin) to warrant pipeline. |
| II Single driving repo | PASS | Gateway-originated (lift-protocol / startup behaviour) → Gateway drives; no Backend change. |
| III JIRA traceability | PASS | AIOT-183; branch/spec dir/commit prefix per convention. fixVersion: not set on ticket (created by dev 2026-08-24) — **flag to dev**: constitution requires fixVersion on dev-initiated tickets; propose SmartLift 5.0 when confirming JIRA actions. |
| IV PR-gated | PASS | PR to `dev`; no scope divergence from JIRA description (adds AUD-033 + force-read re-arm, both listed as related/implied — will note in PR summary, no PO comment needed). |
| V Honest status | PENDING dev action | Transition To be planned → Working on + Start/Due date proposed; awaiting confirmation. |
| VI Hardware-aware | PASS | Hardware & Field Impact in spec; bench plan T1–T4 (~3 h) carried into tasks.md. Not safety-relevant (read-only probes). |
| VII Cross-component | PASS | `gw.liftType` gains value `"unknown"` (already the enum's value; field previously absent on UNKNOWN). Backend tolerates absent/any string today — confirm with Backend dev in PR (no code change expected). |
| VIII Graceful degradation | PASS | Re-identification is local; twin report goes through existing reporter; no cloud dependency. |
| IX Tier gate | N/A | Gateway does not gate on tier. |
| Gateway-local: simplicity over abstraction | PASS | No new classes/protocols; loop lives on `LiftProxy`; `EventSender.lift_type` attribute is updated in place rather than introducing a getter/callback. |
| Gateway-local: error-code-name strings, async I/O, Google docstrings, `get_logger` | PASS | Unchanged patterns. |

**Gate result (pre-research)**: PASS — no violations, Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/AIOT-183-lift-reidentification/
├── spec.md              # Feature spec
├── plan.md              # This file
├── research.md          # Phase 0: decisions (cadence, lock strategy, event-sender fix, close semantics)
├── data-model.md        # Phase 1: lift-type state machine + proxy fields
├── quickstart.md        # Phase 1: bench + unit validation guide
├── contracts/
│   └── cloud-lift-type.md   # gw.liftType twin, LIFT_TYPE telemetry tag, la.read.lift-type
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── main.py                        # log wording only (UNKNOWN → "will keep probing in background")
├── liftApi/
│   ├── lift_proxy.py              # MAIN CHANGE: keep handlers while UNKNOWN, _try_identify(), _bind(), _reidentify_loop(), twin report on UNKNOWN
│   ├── lift_identifier.py         # docstring: "runs once" → "re-run while UNKNOWN (AIOT-183)"; no logic change
│   ├── modbus_handler.py          # + close(): release ModbusSerialClient (AUD-033)
│   └── rs232_handler.py           # + close(): release serial.Serial (AUD-033)
└── cloudApi/
    └── event_sender.py            # no code change required; proxy updates .lift_type in place (documented)

utest/
├── test_lift_proxy.py             # + TestReidentifyLoop, + TestRunReportsLiftType, + bind/close tests
├── test_modbus_handler.py         # + close() tests
├── test_rs232_handler.py          # + close() tests
└── test_main.py                   # existing UNKNOWN boot test stays green; assert new log wording if asserted
```

**Structure Decision**: existing single-project layout; all logic stays in `LiftProxy` (the documented single entry point to lift hardware). No new modules.

## Design

### Lift-proxy changes (`src/liftApi/lift_proxy.py`)

1. **Keep handlers while UNKNOWN.** `_identify_and_init()` becomes:
   - `_create_handlers()` — constructs `ThousandLib`, `ModBusHandler`, `Rs232Handler` once (as today, via `asyncio.to_thread`) and stores them as `self._modbus_handler`, `self._rs232_handler`, `self._thousand_lib`.
   - `_try_identify() -> bool` — one `identify_lift()` round; on success calls `_bind(lift_type)` and returns `True`.
   - `_bind(lift_type)` — the existing `match` arms: set `_handler`/`_lib`, run `_detect_ahl_polling_table` for AHL, **close the losing handler** (`modbus_handler.close()` / `rs232_handler.close()`), drop the loser references, set `_force_read_all = True`, set `self._lift_type` last. Executed under `_handler_lock` so DDMs never observe a half-bound pair.
   - `create()` keeps the startup burst (`IDENTIFY_MAX_RETRIES` × `IDENTIFY_RETRY_DELAY`, unchanged constants, unchanged tests) using `_try_identify()`; on UNKNOWN it now **retains** both handlers instead of dropping them.
2. **Background loop.** `run()` gathers `_reidentify_loop()` alongside `_polling_loop()` / `_daily_loop()`:
   ```
   while self._lift_type == UNKNOWN:
       await asyncio.sleep(REIDENTIFY_INTERVAL)      # 5 s, module constant
       try:
           if await self._try_identify():
               await self._on_identified()
       except asyncio.CancelledError: raise
       except Exception: logger.exception(...)     # never ends the loop on a transient error
   ```
   Log discipline: first failure at WARNING, then one INFO summary every `REIDENTIFY_LOG_EVERY = 12` attempts (~1 min at 5 s); success at INFO. The loop simply returns once identified (gather keeps the other loops alive).
2b. **Bounded twin report.** `run()` reports `gw.liftType` through `_report_lift_type()`, which wraps the patch in `asyncio.wait_for(..., REPORT_TIMEOUT)`. The SDK's twin request/response path has no timeout of its own, so an unanswered patch would otherwise block `run()` before the polling and re-identification loops start.
3. **`_on_identified()`** — `event_sender.lift_type = self._lift_type` (telemetry tag), `await reporter.report_property("gw.liftType", self._lift_type.value)`, log once. `run()` stores `self._reporter` for this.
4. **Twin report on UNKNOWN.** `run()` always reports `gw.liftType` = `self._lift_type.value` (`"unknown"` included). Remove the skip branch + its warning.
5. **Startup-time flag bug.** `_polling_loop` cleared `_force_read_all` after an empty poll even when `_lib is None`, and a poll already blocked on the handler lock could clear the flag `_bind` had just re-armed. Ownership therefore moves into `poll_params()`: it reads and clears the flag **inside `_handler_lock`** (the same lock `_bind` re-arms it under) and only after the lib call returns, so a raising sweep retries next cycle. `_polling_loop` calls `poll_params()` with no argument; the `force_read_all` parameter stays for API compatibility.

### Handler `close()` (`modbus_handler.py`, `rs232_handler.py`)

`def close(self) -> None` — idempotent, logs close errors instead of raising, and sets `self.client = None` in both handlers so any later call fails on the existing `assert self.client is not None` / `__serial_available()` guards rather than on a closed fd. `ModBusHandler.close()` also clears `_modbus_link` so `check_modbus_connection` cannot silently reopen the exclusive port on a closed handler. Not wired into shutdown (`main()` finally) — out of scope (EG-61 territory).

### Untouched by design

- `identify_lift()` logic, `_LIFT_TYPE_CODE` in `MethodRequestHandler` (reads `proxy.lift_type` live), `DeviceTwinReporter`, `HeartbeatHandler`.
- `IDENTIFY_MAX_RETRIES` / `IDENTIFY_RETRY_DELAY` values — the startup burst is still what T3 (normal power order) exercises.

## Hardware & Field Impact (from spec, plan-level detail)

- **Compat**: twin field `gw.liftType` may now be `"unknown"`; telemetry `LIFT_TYPE` custom property may flip from `unknown` to `AHL`/`1k` mid-session (previously constant per session). Backend/SmartFleet to be informed in PR; no contract-shape change.
- **Image/OTA**: none.
- **Bench**: T1–T4 per spec on AHL + 1000-series rigs, ~3 h; T2 soak ≥ 1 h with cable unplugged, watch `ls /proc/<pid>/fd | wc -l` and RSS.
- **Safety**: read-only probes; not safety-relevant.

## Complexity Tracking

No constitution violations — table intentionally empty.

## Post-Design Constitution Re-check

Re-evaluated after Phase 1 artifacts: all rows unchanged (PASS / N/A / pending dev JIRA action). Design introduces no new abstraction, no contract change, no unsupervised task (loop is part of `run()`'s gather → EG-72 fail-loud semantics apply).

## Agent context update

`.specify/scripts/bash/update-agent-context.sh` is not present in this 0.12.1 scaffold; `CLAUDE.md` / `.claude/rules/` already carry the conventions this plan relies on. Nothing to update.

## Open items for the dev (not blockers)

1. Confirm JIRA actions: AIOT-183 → Working on, assignee, Start 2026-08-25, Due, fixVersion (proposal: SmartLift 5.0); EG-50 → Duplicate of AIOT-183.
2. `.specify/feature.json` is untracked and not ignored — add to `.gitignore` (machine-local pointer) on AIOT-181 or here.
3. Retry cadence 5 s with no backoff — veto if bus noise on the 1000-series rig is a concern (RS232 probe waits up to `serial_total_timeout` = 10 s when nothing answers, so worst-case cycle ≈ 15–18 s, still inside SC-001).
