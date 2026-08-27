# Tasks: Background lift re-identification when lift type is UNKNOWN

**Input**: Design documents from `specs/AIOT-183-lift-reidentification/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cloud-lift-type.md, quickstart.md

**Tests**: REQUIRED (spec FR-011). TDD: each story's tests are written first and must fail before the implementation task runs. Tests are `unittest` classes under `utest/` (see `.claude/rules/unit-tests.md`), run with `pytest utest/`; `python -m mypy .` must stay clean.

**Organization**: grouped by user story. Foundational phase carries the refactor every story needs. No commits from the executor — **ticket-commit** owns commits at closeout (prefix `AIOT-183 - …`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1 = self-recovery (P1), US2 = twin shows unknown (P2), US3 = all surfaces agree (P3)

## Path Conventions

Single project: `src/` (app), `utest/` (tests) at repository root. Tests prepend `src/` to `sys.path` as the existing modules do.

---

## Phase 1: Setup

**Purpose**: nothing to scaffold — existing project. One hygiene item from plan §Open items.

- [X] T001 Add `.specify/feature.json` to `.gitignore` (machine-local pointer written by `/speckit-specify`; keep `specs/` tracked)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: split `LiftProxy._identify_and_init()` into reusable pieces and give handlers a `close()`. Every story builds on this. Behaviour after this phase is unchanged for the identified path; on UNKNOWN both handlers are now retained.

**⚠️ CRITICAL**: no user story work until T002–T009 are done and `pytest utest/` + `python -m mypy .` are green.

- [X] T002 [P] Write failing tests for `ModBusHandler.close()` in `utest/test_modbus_handler.py`: closes `self.client`, sets `client = None`, second call is a no-op, exception from `client.close()` is logged not raised
- [X] T003 [P] Write failing tests for `Rs232Handler.close()` in `utest/test_rs232_handler.py`: same four cases against a mocked `serial.Serial`
- [X] T004 [P] Implement idempotent `close()` on `ModBusHandler` in `src/liftApi/modbus_handler.py` (Google docstring; `client.close()` in try/except with `logger.warning(..., exc_info=True)`; `self.client = None`) — T002 green
- [X] T005 [P] Implement idempotent `close()` on `Rs232Handler` in `src/liftApi/rs232_handler.py` (same shape; `self.client = None` so `__serial_available()` guards later calls) — T003 green
- [X] T006 Write failing tests in `utest/test_lift_proxy.py` (new class `TestBind`) for the refactored bind path: (a) AHL bind sets `_handler`=modbus, `_lib`=AhlLib, calls `rs232.close()`, clears `_rs232_handler`/`_modbus_handler` refs, sets `_force_read_all=True`; (b) 1k bind mirrors with `modbus.close()`; (c) UNKNOWN after `create()` keeps both `_modbus_handler` and `_rs232_handler` non-None and calls no `close()`; (d) `_lift_type` is set only after handler/lib are bound (assert ordering via a side-effect on the lib constructor or lock-held check)
- [X] T007 Refactor `src/liftApi/lift_proxy.py`: add fields `_modbus_handler`, `_rs232_handler`, `_thousand_lib`, `_reporter` (typed `| None`, initialised in `__init__`); add module constants `REIDENTIFY_INTERVAL = 5`, `REIDENTIFY_LOG_EVERY = 12`; split `_identify_and_init()` into `_create_handlers()` (constructs the three objects once via `asyncio.to_thread` as today), `_try_identify() -> bool` (one `identify_lift()` round; on non-UNKNOWN result `await self._bind(lift_type)` and return True), and `async _bind(lift_type)` (runs under `_handler_lock`: match arms from the old code, `_detect_ahl_polling_table` for AHL, `close()` + dereference of the loser, `_force_read_all = True`, set `self._lift_type` last). Keep `create()` semantics: call `_create_handlers()` then the existing `IDENTIFY_MAX_RETRIES` × `IDENTIFY_RETRY_DELAY` burst using `_try_identify()`; on exhaustion log the existing `IDENTIFY_ERR` line and **retain** both handlers. Google docstrings on every new method — T006 green, all existing `TestLiftProxyCreate` tests still green
- [X] T008 Update the module docstring of `src/liftApi/lift_identifier.py` ("Runs once during startup" → note that `LiftProxy` re-runs it in the background while UNKNOWN, AIOT-183); no logic change
- [X] T009 Run `pytest utest/` and `python -m mypy .`; both must be clean before Phase 3

**Checkpoint**: proxy refactored, handlers closable, all existing tests green, behaviour unchanged.

---

## Phase 3: User Story 1 — Gateway self-recovers when the lift comes up later (Priority: P1) 🎯 MVP

**Goal**: while `lift_type == UNKNOWN`, `LiftProxy.run()` keeps probing every `REIDENTIFY_INTERVAL` s and switches to the identified handler/lib without a restart; polling and DDMs then work.

**Independent Test**: unit — `identify_lift` patched to `[UNKNOWN, UNKNOWN, AHL]` makes `run()`'s loop bind AHL after two sleeps and exit the loop; DDM path returns INIT_ERR before, real values after. Bench — quickstart T1 (both rigs), T2, T4.

### Tests for User Story 1 (write first, must fail)

- [X] T010 [US1] Add class `TestReidentifyLoop` to `utest/test_lift_proxy.py` (uses `LiftProxyTestBase`; patch `liftApi.lift_proxy.asyncio.sleep` with `AsyncMock`; patch `identify_lift` with `AsyncMock(side_effect=[...])`; run `proxy._reidentify_loop()` directly via `await` — it returns on identification — and for the never-identifies case wrap in `asyncio.wait_for`/cancel after N side-effects): (a) `[UNKNOWN, UNKNOWN, AHL]` → `lift_type == AHL`, `identify_lift` called 3×, `sleep` awaited 3× with `REIDENTIFY_INTERVAL`; (b) `[RuntimeError("bus"), ONE_K]` → loop survives the exception (`logger.exception` path) and binds 1k; (c) `CancelledError` raised from `sleep` propagates (loop does not swallow cancellation); (d) already identified proxy → loop returns immediately without calling `identify_lift`; (e) log rate-limit: with 25 UNKNOWN results then AHL, `logger.warning` called once and `logger.info` summary called `25 // REIDENTIFY_LOG_EVERY` times (patch the module `logger`); (f) `run()` gathers the loop: with `lift_type == UNKNOWN` and `identify_lift` → `[AHL]`, `run()` (cancelled after the bind) has called `_bind` — assert `proxy.lift_type == AHL` and polling loop then calls `lib.poll_params` with `force_read_all=True`
- [X] T011 [P] [US1] Extend `utest/test_main.py::test_unknown_lift_type_still_boots_cloud_stack` (or add sibling) to assert the UNKNOWN warning text mentions background re-identification and that `proxy.run` is still gathered — keeps `main()` wiring locked

### Implementation for User Story 1

- [X] T012 [US1] Implement `_reidentify_loop()` in `src/liftApi/lift_proxy.py` per plan §Design item 2: `while self._lift_type == LiftType.UNKNOWN: await asyncio.sleep(REIDENTIFY_INTERVAL)`; `try: if await self._try_identify(): await self._on_identified(); return` / `except asyncio.CancelledError: raise` / `except Exception: logger.exception("Background lift identification failed")`; attempt counter with first-failure `logger.warning` and every-`REIDENTIFY_LOG_EVERY` `logger.info` summary; add `_on_identified()` stub that logs `"Lift identified in background as %s"` (US2/US3 fill it in). Gather the loop in `run()` alongside `_polling_loop()` / `_daily_loop()`. Google docstrings — T010 green
- [X] T013 [US1] Update `src/main.py` UNKNOWN branch log to `"Could not identify lift type, continuing with cloud stack — will keep probing in background"`; no wiring change — T011 green
- [X] T014 [US1] Run `pytest utest/` and `python -m mypy .`; clean

**Checkpoint**: US1 complete — gateway recovers without restart (unit-verified; bench in Phase 6).

---

## Phase 4: User Story 2 — Fleet sees "unknown lift" instead of stale data (Priority: P2)

**Goal**: `gw.liftType` is reported at `run()` start with the current value (including `"unknown"`) and again with the real type after late identification. Contract: `contracts/cloud-lift-type.md` §1.

**Independent Test**: unit — reporter mock receives `("gw.liftType", "unknown")` at `run()` start when UNKNOWN, then `("gw.liftType", "AHL")` after the loop binds; identified-at-start path reports exactly once. Bench — quickstart T1 twin reads, T3.

### Tests for User Story 2 (write first, must fail)

- [X] T015 [US2] Add class `TestRunReportsLiftType` to `utest/test_lift_proxy.py`: (a) UNKNOWN at `run()` start → `reporter.report_property` awaited with `("gw.liftType", "unknown")` before any sleep; (b) after background bind to AHL → second call `("gw.liftType", "AHL")`; (c) identified at start (AHL) → exactly one call `("gw.liftType", "AHL")` and `identify_lift` not called by the loop; (d) `run()` stores the reporter (`proxy._reporter is reporter`); (e) reporter raising in `_on_identified` is logged and does not undo the bind (`lift_type` stays AHL)

### Implementation for User Story 2

- [X] T016 [US2] In `src/liftApi/lift_proxy.py` `run()`: store `self._reporter = reporter`; replace the UNKNOWN skip/warning branch with an unconditional `await reporter.report_property("gw.liftType", self._lift_type.value)`; update the docstring ("Tolerates an UNKNOWN lift_type…" → reports `"unknown"` and lets `_reidentify_loop` re-report). In `_on_identified()`: `if self._reporter is not None: await self._reporter.report_property("gw.liftType", self._lift_type.value)` wrapped so a reporter failure is logged (`logger.exception`) but never raised — T015 green
- [X] T017 [US2] Run `pytest utest/` and `python -m mypy .`; clean

**Checkpoint**: US1 + US2 — cloud always sees the truthful lift type.

---

## Phase 5: User Story 3 — All cloud-facing surfaces agree after recovery (Priority: P3)

**Goal**: telemetry `LIFT_TYPE` tag follows late identification (`la.read.lift-type` already reads live — verify, don't change). Contract: `contracts/cloud-lift-type.md` §2–3.

**Independent Test**: unit — after background bind, `event_sender.lift_type == proxy.lift_type`; `MethodRequestHandler._la_read_lift_type` returns `"1"`/`"2"` against a proxy whose `lift_type` flipped after construction. Bench — quickstart T1 telemetry + DDM checks.

### Tests for User Story 3 (write first, must fail)

- [X] T018 [P] [US3] In `utest/test_lift_proxy.py` `TestRunReportsLiftType` (or new `TestSurfacesAfterLateIdentification`): after background bind to 1k, `event_sender.lift_type == LiftType.ONE_K`; when `_event_sender is None` (loop run without `run()`), `_on_identified` does not raise
- [X] T019 [P] [US3] In `utest/test_method_request_handler.py`: `la.read.lift-type` returns `lt == "0"` while proxy mock `lift_type = UNKNOWN`, then `"1"` after setting the same mock's `lift_type = AHL` — no handler re-construction (proves live read; expected to pass immediately — keep as regression guard, note in test docstring)

### Implementation for User Story 3

- [X] T020 [US3] In `src/liftApi/lift_proxy.py` `_on_identified()`: `if self._event_sender is not None: self._event_sender.lift_type = self._lift_type` (before the twin report). Add a one-line comment in `src/cloudApi/event_sender.py` on `lift_type` noting `LiftProxy` updates it on late identification (AIOT-183); no code change there — T018 green
- [X] T021 [US3] Run `pytest utest/` and `python -m mypy .`; clean

**Checkpoint**: all three stories complete and unit-verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: hardware verification (constitution VI — run on `dev` after merge, integrated test stage), docs, final gates.

- [X] T022 [P] Update `README.md` / architecture notes if they describe startup identification as "once per power cycle" (grep `identif` in `README.md`, `docs/`); align wording with AIOT-183 behaviour
- [X] T023 [P] Review `AUDIT_BACKLOG.md` entries AUD-004 / AUD-033: do **not** edit statuses in this PR (memory rule: backlog is future-reference only); list them in the PR summary as addressed so they can be closed on a housekeeping ticket
- [ ] T024 (post-merge, tester on `dev`) Hardware bench verification per `specs/AIOT-183-lift-reidentification/quickstart.md` T1, T1b (offline identification), T2–T4 on AHL (RS485) and 1000-series (RS232) rigs — **~3 h** (2 rigs × ~1 h + T2 soak ≥ 1 h overlapping + harness runs). Record rig, image tag, recovery time (must be ≤ 60 s), fd/RSS samples for T2, and twin/telemetry observations; draft the Jira verification comment (instructions for a colleague to reproduce on `dev` after merge, not "I verified it")
- [ ] T025 Full gate: `pytest utest/` and `python -m mypy .` clean; `git diff --stat` reviewed for whitespace-only hunks to split into their own commit at closeout
- [ ] T026 Closeout (dev-driven, not the executor): ticket-commit (split formatting vs logic), PR to `dev` with Summary bullets incl. AUD-004/AUD-033 note and a request for Backend sign-off on `"unknown"` twin value / mid-session `LIFT_TYPE` change; Jira: AIOT-183 → PR, EG-50 → Duplicate (dev confirms each JIRA action)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: independent; T001 can run any time.
- **Foundational (Phase 2)**: T002/T003 ∥; T004 after T002, T005 after T003 (∥ with each other); T006 after T004+T005 (bind tests need `close()`); T007 after T006; T008 ∥ with T007; T009 last. **Blocks all stories.**
- **US1 (Phase 3)**: after T009. T010 and T011 ∥; T012 after T010; T013 after T011; T014 last.
- **US2 (Phase 4)**: after T014 (needs `_on_identified` + loop). T015 → T016 → T017.
- **US3 (Phase 5)**: after T014 (needs `_on_identified`); independent of US2 but touches the same method — run after T017 to avoid merge churn in `_on_identified`. T018/T019 ∥; T020; T021.
- **Polish (Phase 6)**: T022/T023 ∥ any time after T009; T024 after T021 (needs full behaviour on the image); T025 after T024; T026 last.

### User Story Dependencies

- US1: foundational only.
- US2: US1's `_on_identified` hook and loop (cannot be independently *tested* end-to-end without the loop, but the startup-time `"unknown"` report (T015a/T016) is independently valuable and testable).
- US3: US1's hook; independent of US2.

### Parallel Opportunities

- T002 ∥ T003; T004 ∥ T005 (different handler files).
- T010 ∥ T011 (different test files).
- T018 ∥ T019 (different test files).
- T022 ∥ T023 ∥ any code task (docs only).

---

## Parallel Example: Foundational

```bash
# Handler close() — two independent file pairs:
Task: "T002 failing tests for ModBusHandler.close() in utest/test_modbus_handler.py"
Task: "T003 failing tests for Rs232Handler.close() in utest/test_rs232_handler.py"
# then
Task: "T004 implement ModBusHandler.close() in src/liftApi/modbus_handler.py"
Task: "T005 implement Rs232Handler.close() in src/liftApi/rs232_handler.py"
```

## Parallel Example: User Story 1

```bash
Task: "T010 TestReidentifyLoop in utest/test_lift_proxy.py"
Task: "T011 main() UNKNOWN wording/wiring test in utest/test_main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (T001) + Phase 2 (T002–T009) — refactor with zero behaviour change, all tests green.
2. Phase 3 (T010–T014) — background loop. **STOP and VALIDATE**: unit tests + a quick bench T1 on one rig if available.
3. This alone fixes the field defect (gateway recovers without reboot).

### Incremental Delivery

1. + US2 (T015–T017): truthful twin — small, same file.
2. + US3 (T018–T021): telemetry tag consistency — two lines + regression guard.
3. Phase 6: bench (T024, ~3 h) gates the PR; docs + gates; closeout.

### Notes

- Executor (subagent-driven-development via `/speckit-implement`) must not commit; leave the tree dirty for ticket-commit.
- Every new function/method: Google docstring, `str | None` typing, `get_logger` — never `import logging`.
- No hard-coded counts that break when parameter tables grow; the only counts asserted here are on mocked `identify_lift` sequences.
- Keep `IDENTIFY_MAX_RETRIES` / `IDENTIFY_RETRY_DELAY` untouched — existing `TestIdentifyRetry` tests depend on them.
