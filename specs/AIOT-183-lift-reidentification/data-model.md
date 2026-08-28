# Data Model: AIOT-183 Background lift re-identification

No persisted data. The model is the in-memory state of `LiftProxy` and its cloud-visible mirrors.

## Lift-type state

`LiftType` enum (unchanged): `UNKNOWN = "unknown"`, `AHL = "AHL"`, `ONE_K = "1k"`.

### State machine

```
                 create()          _reidentify_loop()
  [start] ──► probing ──UNKNOWN──► probing (background, every 5 s)
                 │                        │
              AHL/1k                   AHL/1k
                 ▼                        ▼
             identified ◄──────────── identified
                 │
            (terminal for this process — no identified → UNKNOWN transition)
```

| Transition | Trigger | Effects (atomic under `_handler_lock`) |
|---|---|---|
| probing → identified | `identify_lift()` returns AHL/1k | `_handler`,`_lib` set; AHL polling table detected; loser handler `close()`d and dereferenced; `_force_read_all = True`; `_lift_type` set; then (outside lock) `event_sender.lift_type` updated, `gw.liftType` reported, INFO log |
| probing → probing | `identify_lift()` returns UNKNOWN or raises | no state change; rate-limited log |
| any → (cancelled) | task cancellation on shutdown | loop exits and starts no further round; a probe already running in a worker thread finishes its current transaction |

## `LiftProxy` fields

| Field | Type | Lifetime | Notes |
|---|---|---|---|
| `_lift_type` | `LiftType` | whole process | written only by `_bind()` (last step) and initial UNKNOWN |
| `_handler` | `ModBusHandler \| Rs232Handler \| None` | None while UNKNOWN | bound pair with `_lib` |
| `_lib` | `AhlLib \| ThousandLib \| None` | None while UNKNOWN | |
| `_modbus_handler` **(new)** | `ModBusHandler \| None` | created in `create()`, cleared at bind | candidate while UNKNOWN |
| `_rs232_handler` **(new)** | `Rs232Handler \| None` | created in `create()`, cleared at bind | candidate while UNKNOWN |
| `_thousand_lib` **(new)** | `ThousandLib \| None` | created in `create()`; becomes `_lib` on 1k, dropped on AHL | shared with `Rs232Handler` |
| `_reporter` **(new)** | `DeviceTwinReporter \| None` | set in `run()` | needed for late twin report |
| `_force_read_all` | `bool` | re-armed at bind | cold-start full read; read and cleared by `poll_params()` under `_handler_lock` |
| `_handler_lock` | `asyncio.Lock` | unchanged | guards bind + all hardware I/O |

Constants (module level): `REIDENTIFY_INTERVAL = 5` (s), `REIDENTIFY_LOG_EVERY = 12` (attempts between summary logs). Existing `IDENTIFY_MAX_RETRIES = 10`, `IDENTIFY_RETRY_DELAY = 5` unchanged.

## Cloud-visible mirrors

| Surface | Source of truth | Update moment |
|---|---|---|
| Reported twin `gw.liftType` | `proxy.lift_type.value` | `run()` start (always, incl. `"unknown"`) and `_on_identified()` |
| Telemetry custom property `LIFT_TYPE` | `EventSender.lift_type.value` | constructed from `proxy.lift_type` in `main()`; overwritten by `_on_identified()` |
| DDM `la.read.lift-type` → `lt` | `_LIFT_TYPE_CODE[proxy.lift_type]` (`"0"/"1"/"2"`) | read live per call — no change |

Validation rules: `gw.liftType` ∈ {`"unknown"`, `"AHL"`, `"1k"`}; `LIFT_TYPE` same set; `lt` ∈ {`"0"`,`"1"`,`"2"`}. See [contracts/cloud-lift-type.md](contracts/cloud-lift-type.md).

## Handler `close()` semantics

| Handler | Resource | After `close()` |
|---|---|---|
| `ModBusHandler` | `ModbusSerialClient` (`/dev/ttyLP1`, exclusive) | `client.close()`; `self.client = None`; further calls hit existing `assert self.client is not None` |
| `Rs232Handler` | `serial.Serial` (`/dev/ttyLP6`) | `client.close()`; `self.client = None`; further calls short-circuit via `__serial_available()` |

Idempotent; exceptions from the underlying close are logged, never raised.
