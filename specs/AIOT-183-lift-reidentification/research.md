# Research: AIOT-183 Background lift re-identification

All Technical Context items were resolvable from the codebase; no external research needed. Decisions below resolve the spec's assumptions into concrete choices.

## R1. Retry cadence and shape

- **Decision**: single `identify_lift()` round every `REIDENTIFY_INTERVAL = 5` s, no backoff, indefinitely while UNKNOWN.
- **Rationale**: a round is one Modbus read (3 s timeout) + one RS232 query (≤ 10 s `serial_total_timeout`) when nothing answers; worst-case cycle ≈ 18 s, typical (ports absent / fast NAK) ≈ 5 s — comfortably inside the 60 s SC-001 target. Backoff would trade nothing (probe cost is negligible, bus is idle when no lift answers) for slower commissioning.
- **Alternatives considered**: re-running the full 10 × 5 s startup burst per cycle (rejected — the burst exists to bound startup time, meaningless for a forever loop); exponential backoff capped at 60 s (rejected — worsens SC-001 for no gain); reusing `intervals.liftAgentPolling` from the twin (rejected — couples an unrelated operator-tunable to recovery time; a module constant is simpler and testable).

## R2. Where the loop lives

- **Decision**: `LiftProxy._reidentify_loop()` gathered inside `LiftProxy.run()` next to `_polling_loop` / `_daily_loop`.
- **Rationale**: `run()` already owns the proxy's long-lived tasks and receives `event_sender` + `reporter`, which the success path needs. Keeps `main()` untouched and inherits EG-72's fail-loud semantics (an escaping exception ends `main()`'s gather → non-zero exit) while per-iteration `try/except Exception` keeps transient probe errors from ending retries (FR-009/FR-008).
- **Alternatives considered**: a task created in `main()` (rejected — EG-61 supervision is not landed; adding another top-level task now means re-wiring later); a separate `LiftIdentifierTask` class (rejected — abstraction with one caller; violates simplicity rule).

## R3. Atomic switch vs. DDM/polling concurrency

- **Decision**: `_bind()` runs under the existing `_handler_lock`; sets `_handler`, `_lib`, `_force_read_all = True`, closes loser, then `_lift_type` last.
- **Rationale**: every hardware path in the proxy takes `_handler_lock` before touching `_handler`/`_lib`; the `is None` pre-checks outside the lock only ever go None → non-None under this feature, so a caller that saw None returns INIT_ERR (today's behaviour) and one that saw a handler proceeds with a fully bound pair. `_detect_ahl_polling_table` is a live read; doing it inside the lock keeps the poll loop from interleaving with it.
- **Alternatives considered**: a separate identification lock (rejected — two locks, same critical resource); lock-free with an `asyncio.Event` (rejected — DDM callers still need the lock for I/O).

## R4. Telemetry lift-type tag after late identification

- **Decision**: proxy assigns `self._event_sender.lift_type = self._lift_type` in `_on_identified()`; `EventSender` unchanged.
- **Rationale**: `lift_type` is already a public attribute read on every `send_event`; the proxy already holds the sender. One line, no interface change, fully testable.
- **Alternatives considered**: `EventSender(lift_type_getter=...)` callable (rejected — indirection for one field); passing the proxy into `EventSender` (rejected — inverts dependency direction: proxy imports EventSender today).

## R5. `gw.liftType` value while unknown

- **Decision**: `LiftType.UNKNOWN.value` = `"unknown"`, reported via the same `report_property("gw.liftType", ...)` call as identified types.
- **Rationale**: one code path for all three values; matches the ticket text; legacy numeric codes ("0"/"1"/"2") are an EG-71 concern that then applies uniformly. `la.read.lift-type` already maps UNKNOWN → "0" for smartlift2 tooling.
- **Alternatives considered**: reporting `"0"` now (rejected — mixes schemes until EG-71 lands); omitting the field (rejected — that is the bug: cloud keeps the stale value).

## R6. Closing the losing handler (AUD-033)

- **Decision**: add idempotent `close()` to `ModBusHandler` (`self.client.close()`; `self.client = None`) and `Rs232Handler` (`self.client.close()`; `self.client = None`); `_bind()` calls it on the loser and drops the reference. Not called on shutdown (out of scope).
- **Rationale**: while UNKNOWN both ports must stay open for probing (unchanged from startup today); on bind the loser is otherwise released only by GC finalizers. Explicit close is small and sits in the same code path.
- **Alternatives considered**: context-manager handlers (rejected — handlers are long-lived, no natural scope); closing in `main()` finally only (rejected — does not fix the runtime leak at bind).

## R7. Cold-start full read after late bind

- **Decision**: `_bind()` sets `_force_read_all = True`.
- **Rationale**: `_polling_loop` clears the flag after the first (empty) poll while UNKNOWN, so without re-arming, the first real poll would only read "changed" params and the db would stay sparse until values move. Re-arming preserves legacy `m_force_read_all` semantics for the late case.
- **Alternatives considered**: only clearing the flag when `_lib is not None` in `_polling_loop` (viable, but re-arming at bind is more explicit and also covers any future path that binds late).

## R8. Test strategy

- **Decision**: extend `utest/test_lift_proxy.py` with `patch("liftApi.lift_proxy.identify_lift")` sequences (`[UNKNOWN, UNKNOWN, AHL]`), `asyncio.sleep` patched to `AsyncMock`, and a bounded runner (cancel `run()` after the loop exits / after N iterations). Assert: loop stops on identification; loop keeps going on exceptions; `_handler`/`_lib` bound; loser `close()` called; `_force_read_all` re-armed; `event_sender.lift_type` updated; reporter called with `"unknown"` at start and real type after; no reporter call skipped. Handler `close()` tests in the existing handler test modules with mocked clients.
- **Rationale**: matches existing `LiftProxyTestBase` fixtures; no real serial; no hard-coded loop counts beyond the sequence length.
