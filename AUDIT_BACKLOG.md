# GatewayApp Audit Backlog

- **Scope:** Full working-tree audit of GatewayApp (branch `EG-64-lift-data-ddms`, uncommitted changes included) — src/cloudApi, src/liftApi, src/bluetoothApi, src/lib, src/filemgmt, utest/, CI config. `.venv/` excluded.
- **Date:** 2026-06-12
- **Method:** 5 parallel auditors (security, implementation, functionality/legacy-parity, stability, testing) + adversarial verification of every finding. 56 verified findings deduplicated into **43 backlog items** (5 additional findings were refuted and excluded).
- **Provenance:** Audit performed by Claude Fable 5 (multi-agent workflow). The audit was run in advance because the included Fable usage expires on 2026-06-22. At audit time no Jira/Azure DevOps issues were created — that happened post-vacation: on 2026-08-18 the findings were re-verified (40 of 43 still open) and structured into Jira tickets **EG-69..EG-75** (all labeled `audit`), plus finding-comments on existing tickets EG-49/50/61/62/67. Jira is the tracking source of truth; this file remains the detailed findings reference.
- **Counts:** P0: 4 | P1: 17 | P2: 10 | P3: 12
- **Audience:** Implementation agent. Repo conventions apply to every fix: error-code-name-string returns, async I/O, Google docstrings, `unittest` with `setUp`/`tearDown`, type hints (`str | None` style), run `pytest utest/` and `python -m mypy .` before every commit. Do not add abstraction layers — match existing patterns.

Known/by-design items that must NOT be "fixed": EG-56 DDM placeholders (EG-64..68 track them), gw.* identity via injected env vars with `"undefined"` fallback, pymodbus serial `echo=False`/`retries=0` (kernel-driven RS485 DE).

---

## P0 — Fix immediately (crashes, security holes, data corruption)

### AUD-001 [P0] [security] Replace `eval()` on raw serial data in `__split_response`
- **Location:** `src/liftApi/rs232_handler.py:590` and `:600`
- **Problem:** `__split_response()` runs bare `eval()` on the raw UTF-8 string read from the RS232 serial buffer (lines 590 `rsp_list = eval(rsp_list)` and 600 `rsp_list = [eval(rsp_full)]`), *before* any validation (`__decode_and_validate_serial_response` runs only at line 616). A crafted frame like `{"x": __import__("os").system("...")}` executes arbitrary code in the cloud-connected gateway process; a frame like `[9**9**9]` is a resource bomb; `{exit()}` raises SystemExit which escapes the `except Exception`. eval also breaks on legal JSON literals (`true`/`false`/`null` → NameError → whole buffer dropped as ARG_TYPE_ERR). Attack vector is the physical RS232 link / compromised AR-Gate controller, so not remotely reachable directly — but it is a code-injection primitive with a trivial fix. (Merged: 3 auditors found this independently.)
- **Evidence:** `rsp_full` originates from `read_serial()` → `self.client.read(size=waiting_bytes).decode('utf-8')` (line 533). The same file already uses safe `ast.literal_eval` at line 835 for an equivalent parse, and the code json.dumps's the eval result back to JSON at lines 608-610 — proving the data is JSON.
- **Fix:** Replace both eval calls with `json.loads(f'[{rsp_full.replace("}{", "},{")}]')` (or `ast.literal_eval` as a minimal drop-in) and remove the now-redundant `json.dumps` round-trip at lines 608-610 / the re-`json.loads` in `__decode_and_validate_serial_response` (line 318). Keep the existing ARG_TYPE_ERR mapping on `json.JSONDecodeError`. Run the full rs232 test suite — the quoting semantics change (single→double quotes no longer needed).
- **Effort:** small–medium (the round-trip removal touches `__decode_and_validate_serial_response`).
- **Dependencies:** None. Do before AUD-041 (test-file migration) so tests are only touched once if assertions change.

### AUD-002 [P0] [stability] Fix infinite loop in `Rs232Handler.read_serial` on partial frame
- **Location:** `src/liftApi/rs232_handler.py:527-561`
- **Problem:** Retry counter `i` is incremented only in the `if not rsp:` branch (line 544). `rsp` accumulates via `rsp +=`, so once any non-empty data arrives, a UTF-8-decodable truncated frame that never ends with `}` takes the `elif not rsp.endswith('}')` branch (lines 549-550), sleeps 0.5 s, and loops forever — `while i < retries` never exits. The call runs inside `asyncio.to_thread` while `LiftProxy._handler_lock` is held (`lift_proxy.py:243`), so the polling loop hangs permanently and every lift DDM blocks on the lock until process restart. On an idle 1k lift there is no rescuing traffic. Silent loss of all lift monitoring; heartbeat keeps running so the failure is invisible cloud-side.
- **Evidence:** No deadline/timeout anywhere in the chain: `get_signal_from_serial_buffer` → `poll_lift` → `thousand_lib.poll_params` (to_thread) → `LiftProxy.poll_params` under `_handler_lock`; no `asyncio.wait_for` and no watchdog.
- **Fix:** Bound the loop regardless of branch: increment `i` (or track a `time.monotonic()` deadline) in the partial-frame branch too; on expiry discard the buffer and return `(-1, SERIAL_DECODE_ERR-or-NO_WAITING_BYTES_ERR name)` per the error-code-string convention. Add a unit test feeding a truncated frame (`'{"cmd":"par'` with no closing brace) asserting the function returns within `retries` iterations.
- **Effort:** small
- **Dependencies:** None.

### AUD-003 [P0] [implementation] Fix platform-dependent sign decode of 32-bit parameters (`ctypes.c_long`)
- **Location:** `src/liftApi/modbus_handler.py:644-645`
- **Problem:** `_validate_read_param_response` does `value = (reg0 << 16) + reg1; value = ctypes.c_long(value).value`. `c_long` is 8 bytes on linux/arm64 (the production target per `scripts/build_image.sh:27` / README), so the cast is a no-op and registers `[0xFFFF, 0xFFFF]` decode to `4294967295` instead of `-1`. Every negative parameter (FLOORx_LEVEL_ADJUST mm, PARAM_LAST_SYNC_DIFFERENCE — `ahl_lib.py:247-259`) is silently corrupted in cache, telemetry, and `la.read.parameter` / `la.read.parameters` / `la.write.read.parameter` responses. Masked on Windows dev machines where c_long is 4 bytes. The write side correctly packs `-1` → `[0xFFFF, 0xFFFF]`, so write-then-readback reports `4294967295`. Ported verbatim from smartlift2, which ran on 32-bit ARM. (Merged: 2 auditors.)
- **Fix:** Replace with `ctypes.c_int32(value).value` (or `int.from_bytes(..., signed=True)`). Add a unit test in `utest/test_modbus_handler.py`: mocked response registers `[0xFFFF, 0xFFFF]` → `-1`.
- **Effort:** small
- **Dependencies:** None. The new test naturally seeds AUD-022's response-validator coverage.

### AUD-004 [P0] [stability] Eliminate permanent give-up paths at startup (DPS, connect, lift identification)
- **Location:** `src/main.py:39-41, 49-51, 57-59`
- **Problem:** Three startup failures each `return` from `main()`, terminating the process — with **exit code 0**, so even an external restart-on-failure policy would not restart it (no systemd unit / Docker restart policy exists in the repo; `scripts/entrypoint.sh` just execs the CMD). (a) DPS provisioning failure — no retry at all; (b) `device_client.connect()` failure — no retry; (c) lift identification UNKNOWN after only 10×5 s ≈ 50 s. A boot race against the cellular/network link, or a lift powered on after the gateway, leaves the device permanently dead until a site visit. Legacy main.cpp kept the cloud stack (heartbeat, direct methods, ca.download-file, remote reboot) running with `lift_attached == unknown` and gated lift paths per-call. LiftProxy was already written to tolerate UNKNOWN: `read_param_live`/`write_param`/`read_ar_number` return INIT_ERR envelopes when handler is None, `poll_params` returns `[]`. The UNKNOWN exit also makes lift-simulator mode unreachable. (Merged: 2 auditors.)
- **Fix:** (1) Wrap DPS provisioning and `connect()` in an indefinite retry loop with capped exponential backoff (device is useless without the connection). (2) On UNKNOWN lift type, **continue startup** with the full cloud stack; let lift-dependent DDMs return their existing INIT_ERR envelopes; optionally retry identification in a background task. (3) If any path must still exit, exit non-zero.
- **Effort:** medium
- **Dependencies:** Do together with AUD-010 (both restructure `main()`'s task setup/supervision) to avoid touching `main.py` twice.

---

## P1 — Fix soon (contract violations, reliability risks)

### AUD-005 [P1] [functionality] Apply desired-twin patches; add state-asserting tests
- **Location:** `src/cloudApi/device_twin_desired_handler.py:32-37`; tests `utest/test_azure_iot_device_usage.py:145-187`
- **Problem:** `listen_for_desired_updates()` receives each desired-properties patch, logs it, and discards it — `self.desired_properties` is populated only once by `get_twin()` in `create()`. Every runtime-tunable consumer reads the dict live each cycle (heartbeat interval `heartbeat_handler.py:92`, paramPush/intervals `lift_proxy.py:381/404`, downloadMaxBytes `method_request_handler.py:150`) so cloud config changes silently do nothing until restart — and `gw.reboot` is itself a placeholder, so there is no remote recovery path. Legacy applied patches immediately (twin_observer.cpp OnSetTwinRequest). The three existing tests assert only `receive_twin_desired_properties_patch.await_count`, so they pass whether patches are applied or dropped. (Merged: 3 findings — functionality + stability + testing.)
- **Fix:** In the loop, merge each patch into `self.desired_properties` (top-level key replace; honor `null` = delete per IoT Hub semantics / legacy FindAndEraseNulls; skip `$version`), inside try/except so a malformed patch cannot kill the loop. Add tests that feed a patch via AsyncMock side_effect and assert `handler.desired_properties` reflects it, plus a MethodRequestHandler test showing a post-patch `downloadMaxBytes` change is honored by ca.download-file.
- **Effort:** small
- **Dependencies:** Land before AUD-018 (outbox flush could key off connection/twin events) — soft ordering only.

### AUD-006 [P1] [functionality] Heartbeat telemetry must use nested `{"gw": {...}}`, not flat dotted keys
- **Location:** `src/cloudApi/heartbeat_handler.py:52-55`
- **Problem:** Payload is built as `{"gw.uptime": ..., "gw.rssiGsm": ...}` and json.dumps'd as-is. Legacy boost-ptree serialized dotted paths as nested JSON — a real legacy device log shows `{"gw":{"uptime":"137","rssiGsm":"-71"}}` — and the backend coldstorage extractor gates on `if 'gw' in body` then indexes `["gw"]["rssiGsm"]`, so flat-keyed heartbeats are **silently skipped**. The fleet device-alive/RSSI feed dies with no error anywhere.
- **Fix:** Build nested: `{"gw": {"uptime": ..., "rssiGsm": ...}}` (DeviceTwinReporter.report_property in `device_twin_reported.py:19-22` already implements dot→nested conversion, confirming the convention — reuse or hardcode). Update `utest/test_heartbeat_handler.py:44-47` which currently enshrines the flat format.
- **Effort:** small
- **Dependencies:** None. Verify with backend whether values are strings in legacy (`"137"`) and match.

### AUD-007 [P1] [functionality] Report lift type with legacy numeric codes everywhere (twin + message property)
- **Location:** `src/liftApi/lift_proxy.py:272` and `src/cloudApi/event_sender.py:41`
- **Problem:** Two sites send enum strings instead of the legacy numeric codes `0/1/2` (unknown/AHL/1000): (a) `gw.liftType` twin report sends `self._lift_type.value` (`"AHL"`/`"1k"`); legacy main.cpp:71-77 documents and sends `"1"`/`"2"`. (b) Every telemetry message's `LIFT_TYPE` custom property sends the enum string; legacy event_sender.cpp:78 sent `std::to_string(lift_attached)`. IoT Hub routing rules and dashboards keyed on `'1'`/`'2'` silently stop matching. The repo is internally inconsistent: `method_request_handler.py:21` already defines `_LIFT_TYPE_CODE = {UNKNOWN:"0", AHL:"1", ONE_K:"2"}` and uses it for the la.read.lift-type DDM. (Merged: 2 findings, same root cause/same map.)
- **Fix:** Hoist `_LIFT_TYPE_CODE` to a shared location (e.g. `lift_identifier.py` next to the enum), and use it at both sites. Update affected tests.
- **Effort:** small
- **Dependencies:** Hoist the map first, then fix the three call sites (including the existing DDM usage) in one commit.

### AUD-008 [P1] [stability] Move blocking blob transfer I/O off the event loop
- **Location:** `src/cloudApi/blob_download_handler.py:37-39` (primary); `src/cloudApi/blob_upload_handler.py:42` (latent)
- **Problem:** `download_from_blob` is `async def` but uses the sync `azure.storage.blob.BlobClient`: `download_blob()` + `stream.readall()` + sync file write, awaited directly from `file_download.py:93` (ca.download-file DDM — real EG-64 code, not a placeholder). A transfer up to the 50 MiB cap (twin-raisable) blocks the entire event loop: heartbeats, lift polling, and all direct methods stall; the 30 s direct-method timeout expires; no read timeout is passed so a stalled connection blocks indefinitely. The properties fetch a few lines earlier (`file_download.py:82`) IS wrapped in `asyncio.to_thread` — this is a deviation, not design. `readall()` also buffers the whole file in RAM. `upload_to_blob` has the same sync call (currently uncalled in src/). (Merged: 2 auditors.)
- **Fix:** Wrap the download body in `await asyncio.to_thread(...)` (or switch to `azure.storage.blob.aio`), and stream to the `.tmp` file in chunks (`chunks()`/`readinto`) instead of `readall()`. Apply the same to `upload_to_blob`. Pass a read timeout.
- **Effort:** small
- **Dependencies:** None.

### AUD-009 [P1] [stability] modbus_file_record is dead under pymodbus 3.x — port it and add tests; pin deps
- **Location:** `src/liftApi/modbus_file_record.py:61-69` (whole `FileRecordAritco.run`); `requirements.txt`
- **Problem:** `run()` uses pymodbus 2.x private internals (`transaction._transaction_lock`, `_transact`, `_no_response_devices`, `framer._buffer`, `utilities.ModbusTransactionState`, etc.). Verified at runtime against installed pymodbus 3.12.1: **every attribute is absent — `run()` raises AttributeError on its first statement.** Callers swallow it broadly (`generate_trace_log` → LOG_RUN_ERR, `write_upgrade_package` → FILE_TRANSFER_ERR), so trace-log download and firmware upload are silently non-functional and will be dead-on-arrival when the EG-64..68 DDM wiring lands. Zero tests reference the module (grep utest/ → no matches). `requirements.txt` pins no version (`pymodbus` bare), so any rebuild can shift behavior again. (Merged: 2 findings — testing high + stability medium.)
- **Fix:** Port `FileRecordAritco.run` to the pymodbus 3.x transaction API (or implement the raw ADU exchange on the serial socket directly, which is what the SW-2650 workaround effectively needs). Add `utest/test_modbus_file_record.py` exercising `run()` against a `ModbusSerialClient` with mocked transport, plus the `response_length` calculation and response validation (a plain smoke test would have caught the current breakage). Pin `pymodbus` (and other deps) to known-good versions.
- **Effort:** large
- **Dependencies:** Must complete **before** wiring la.lift-log-generate / la.fwu-trigger DDMs (EG-65+). Coordinate with AUD-022 (handler-level file-transfer tests).

### AUD-010 [P1] [stability] Guard SDK receive loops and supervise top-level tasks
- **Location:** `src/cloudApi/method_request_handler.py:90`; `src/cloudApi/device_twin_desired_handler.py:35`; `src/main.py:102`
- **Problem:** `await device_client.receive_method_request()` sits outside the try in `listen_for_method`; `listen_for_desired_updates` has no try at all; `main()` runs all four long-lived loops under a bare `asyncio.gather`. Any exception escaping a receive call (one-time `_enable_feature` SUBSCRIBE on first iteration, credential errors, SDK-internal faults) kills its task, gather propagates, `asyncio.run` cancels the siblings, and the whole process exits. Steady-state receive rarely raises (SDK inbox + auto-reconnect), so this is a narrow-trigger / high-impact robustness gap, not a routine-hiccup crash. (Merged: 2 findings.)
- **Fix:** Move the receive awaits inside try/except with logging and capped-backoff sleep + `continue` (backoff matters — don't spin on a persistent enable failure). Wrap each top-level task in a small supervisor coroutine that logs and restarts with capped exponential backoff. Keep it simple — no framework.
- **Effort:** medium
- **Dependencies:** Do together with AUD-004 (same `main()` surgery).

### AUD-011 [P1] [stability] Fix CWD-relative log file paths; remove import-time `setup_logging()` calls
- **Location:** `src/lib/logging_config.py:30` + `logging_config.yaml:25,34`; import side effects in `modbus_handler.py:33`, `rs232_handler.py:20`, `ahl_lib.py:15`, `thousand_lib.py:17`
- **Problem:** `setup_logging` creates `<src>/logs` via `__file__`, but the YAML hands RotatingFileHandler the **relative** paths `logs/gateway_app.log` resolved against CWD. The production Dockerfile (WORKDIR /src, no `logs/` there) makes `dictConfig` raise unconditionally on every run; the broad except silently falls back to console-only `basicConfig` — all persistent/rotated file logging is lost in the shipped image (smoking gun: `Dockerfile.dev:60` adds `RUN mkdir -p /src/logs` as a workaround the prod Dockerfile lacks). Four modules also call `setup_logging()` at import, re-running dictConfig as a hidden side effect.
- **Fix:** Rewrite `config['handlers'][*]['filename']` to absolute paths against the created `log_dir` before `dictConfig`; remove the module-level `setup_logging()` calls (main.py already configures once). Make the except log loudly that file logging is disabled.
- **Effort:** small
- **Dependencies:** None.

### AUD-012 [P1] [implementation] Fix post-write `int(value)` crash and 1k cache type corruption in `LiftProxy.write_param`
- **Location:** `src/liftApi/lift_proxy.py:221-223`
- **Problem:** After a successful hardware write, `self._lib.set_param(int(param), int(value))`. (1) ModBusHandler explicitly accepts hex strings (`int(x,0)` in `_validate_inputs`/`_pack_value`), so a successful AHL hex write (`'0x10'`) then raises ValueError in base-10 `int(value)` → dispatcher catch-all → DDM returns 500 "Internal error" and the telemetry push is skipped **even though the hardware was written**. (2) The 1k ThousandLib db is string-typed (`rs232_handler.py:1649` stores `value_str`; every `__unpack_*` returns str); `set_param` overwrites with an int, so the next poll's `5 != '5'` comparison emits a spurious duplicate telemetry change, and Rs232Handler's already-has-value shortcut (`:1551-1552`) never matches again, causing redundant hardware writes.
- **Fix:** Use `int(value, 0)` for the AHL path inside try/except, and **skip the manual cache update entirely for 1k** (Rs232Handler.write_parameter already updates the shared ThousandLib db with the correct str type). Add tests: hex write returns success envelope; 1k write does not change db value type.
- **Effort:** small
- **Dependencies:** Do before AUD-013 (the live read-back will replace part of this cache-update logic — see note there).

### AUD-013 [P1] [functionality] la.write.read.parameter must read back from hardware, not the cache it just wrote
- **Location:** `src/cloudApi/method_request_handler.py:281-283`
- **Problem:** `write_param()` itself sets the cache to the requested value, then `_la_write_read_parameter` "reads back" via `get_param_value()` (cache) — the read-back tautologically returns the requested value and can never detect LCM clamping/transformation (e.g. the reset-alarm bitshift in `_handle_reset_alarms`). Legacy did a live `ParameterReadRequest` after the write (device_direct_method.cpp:317). Also: for params not in the lib db, the hardware write succeeds but `set_param` fails silently and the read-back returns `-1`/PARAM_NOT_IN_DB — a successful write reported as an error. Cache self-corrects on the next poll, so the wrong data is confined to the DDM response.
- **Fix:** Read back via `await self._proxy.read_param_live(int(param))` (already exists, `lift_proxy.py:143-156`) and update the cache from the live value so cache/telemetry/response reflect hardware truth. Add a test where the mocked live read returns a transformed value and assert the response carries it.
- **Effort:** small
- **Dependencies:** After AUD-012 (write_param's cache behavior changes first; the live read-back then updates the cache with the actual value).

### AUD-014 [P1] [implementation] Don't clear `_force_read_all` when the cold-start sweep failed
- **Location:** `src/liftApi/lift_proxy.py:289-290`; `src/lib/ahl_lib.py:202-203`; `src/lib/thousand_lib.py:127-133`
- **Problem:** `_polling_loop`'s docstring promises "a raising call leaves the flag set and the next iteration retries", but both libs swallow hardware failures and return `[]`, and the flag is cleared unconditionally and never re-armed. A transient com error during the first cycle permanently skips the cold-start full read: the cache serves db defaults, `_daily_loop` pushes defaults to cloud telemetry indefinitely, and static params never converge (DDM reads are unaffected — `read_param_live` bypasses cache). AhlLib's forced path also silently `continue`s on per-param read failures (realistic given the LCM's known frame-drop behavior), leaving partial sweeps un-healed.
- **Fix:** Make `lib.poll_params` signal failure distinctly (return `None` vs `[]`, or raise — pick one and keep both libs consistent), and clear `_force_read_all` only after a *successful* forced sweep. For AhlLib, count per-param failures during a forced sweep and treat a non-trivial failure count as an unsuccessful sweep.
- **Effort:** medium
- **Dependencies:** Coordinate with AUD-019 (both touch the forced-sweep path in ahl_lib; do in the same batch to avoid conflicting edits).

### AUD-015 [P1] [implementation] Guard `int()` of unpolled version params in `check_if_above_or_equal_to_versions`
- **Location:** `src/liftApi/rs232_handler.py:1709-1712`
- **Problem:** Four bare `int(self.tl.database[...].value)` calls; version Signals initialise to `""` and remain `""` if the 'version'/'2' packages failed to poll (poll_lift continues with PARTIAL_ERR on package failure). `int("")` → ValueError propagates out of `poll_lift` (hit every cycle at the doorOpenCount check, line 1402), aborting the cycle; already-applied db updates from earlier packages mean the changed-param IDs collected that cycle are **lost permanently** (onChange telemetry silently dropped, not re-detected). Realistic on restart with a noisy serial link.
- **Fix:** Wrap the conversions in `try/except (ValueError, TypeError)` and return `False` (unknown version = "not supported"), matching conservative legacy behavior. Add a test with empty version values.
- **Effort:** small
- **Dependencies:** None.

### AUD-016 [P1] [functionality] la.parameters.update: rename `error` → `errors` array and stop dropping failed reads
- **Location:** `src/liftApi/lift_proxy.py:341-353`
- **Problem:** `_send_params` sends `{"data": [...], "error": "", "event": "la.parameters.update", ...}` — a singular always-empty `error` key — and silently skips params whose cache read fails. The legacy contract (lift_agent_api.cpp:254-281, documented in `doc/azure/parameter-change-notification.md`) carries BOTH a `data` child and an `errors` array (failed items with parameter/value/errorSource/errorCode/timestamp). Backend consumers reading `errors` get nothing; failed-read visibility is lost. Legacy also serialized values as strings; new code sends raw ints. The bad pattern was copied from `lift_simulator.py:52` — fix that too.
- **Fix:** Rename to `errors`, populate it with failed items per the documented schema, and confirm with backend whether values must be strings (legacy ptree says yes) — cast accordingly. Mirror in lift_simulator. Update tests.
- **Effort:** small
- **Dependencies:** None.

### AUD-017 [P1] [functionality] Replace literal `"TODO"` twin metadata with env-var values; add missing fields
- **Location:** `src/cloudApi/heartbeat_handler.py:71-78`
- **Problem:** First heartbeat (re-run after every restart) patches `gw.serialNumber`/`gw.hardwareVersion`/`ca.softwareVersion`/`gw.wifi` = literal `"TODO"` into the reported twin of every device, polluting fleet inventory the backend keys on; `gw.imei`/`gw.iccid`/`gw.bomRevision` (legacy main.cpp:757-766) are never reported. The agreed platform design is injected env vars with `"undefined"` fallback — this code implements neither (no getenv for these fields anywhere in src/).
- **Fix:** Wire metadata to the injected env vars with `"undefined"` fallback; report real `ca.softwareVersion` from the app version; add `gw.bomRevision` (defer imei/iccid until the GSM container lands — note it in a comment/ticket).
- **Effort:** small
- **Dependencies:** Needs the env-var names from the platform design (see MEMORY: project_gw_identity_sources).

### AUD-018 [P1] [stability] Buffer/retry telemetry instead of silently dropping on send failure
- **Location:** `src/cloudApi/event_sender.py:46-47`
- **Problem:** `send_event` catches every exception and only logs. Parameter-change events are one-shot: the lib db has already recorded new values (and reading PARAM_POLLING cleared the LCM hardware change flags), so after a connectivity outage all la.parameters.update events in that window are permanently lost — a silent gap in cloud parameter history. Daily push re-sends latest values for daily-list params only; onChange-only params and intermediate values are gone.
- **Fix:** Add a small bounded outbox (e.g. `collections.deque(maxlen=~200)`, drop-oldest): on send failure enqueue the payload; flush on next successful send or connection-state callback. Re-queueing must live at the EventSender/proxy layer since the diff baseline and LCM flags are already consumed. Keep it simple — no persistence to disk.
- **Effort:** medium
- **Dependencies:** After AUD-010 (supervision/reconnect behavior settles first).

### AUD-019 [P1] [stability] Bound AHL forced-sweep duration so the handler lock isn't held for ~an hour
- **Location:** `src/lib/ahl_lib.py:168-207`; `src/liftApi/lift_proxy.py:243`
- **Problem:** `poll_params(force_read_all=True)` sweeps ~370 params sequentially; `read_parameter` costs ~9 s per dead param (3 tries × 3 s timeout; `_test_connection` only checks the tty path exists, so a powered-down lift yields slow timeouts, not fast LINK_ERR). Worst case ≈ 55 min holding `_handler_lock`, blocking every lift DDM (IoT Hub 30 s method timeout). One-shot per process start (flag is cleared after — see AUD-014), but a flaky bus (known LCM frame-dropping) stretches the sweep by minutes routinely.
- **Fix:** Abort the sweep after N consecutive COM_ERR/LINK_ERR failures (bus is down — individual params won't differ) and/or enforce a wall-clock budget per poll cycle. Optionally release/re-acquire the handler lock between individual param reads so DDMs can interleave.
- **Effort:** medium
- **Dependencies:** Same batch as AUD-014 (interacts with "what counts as a successful forced sweep").

### AUD-020 [P1] [security] Require authentication on BLE WiFi control characteristics
- **Location:** `src/bluetoothApi/server.py:216, 234-254`
- **Problem:** Scan/connect/disconnect characteristics are registered with plain `permissions=["write"]`; the DIS serial (AR number) with plain `["read"]`. No pairing, bonding, encrypt-write, or app-level auth anywhere; controller validates only payload format, and connect/disconnect invoke the real `wifi_connect.sh`. The BLE server starts unconditionally at boot with no commissioning window — any unauthenticated central in radio range can force the gateway onto an attacker SSID or knock it offline, for the device's whole uptime.
- **Fix:** Use the SDK's encrypted/authenticated permission level (`encrypt-write`/`secure-write`) on the write characteristics if the vendor nexyhub_ble SDK exposes it; otherwise add an app-layer auth handshake before honoring connect/disconnect, and/or limit advertising to a commissioning window.
- **Effort:** medium
- **Dependencies:** Check nexyhub_ble SDK capabilities first; may need a vendor question.

### AUD-021 [P1] [security] Remove shell-interpolated `xxd` call in `_validate_up_header`
- **Location:** `src/liftApi/modbus_handler.py:1020-1030`
- **Problem:** `command = f"xxd -l {bytes_to_read} {file_path}"` run with `subprocess.run(..., shell=True)`. The filename derives from cloud input (ca.download-file can drop an attacker-named file in the upgrade folder); `_safe_filename` permits `;`, spaces, `$()`, backticks, and `_validate_up_file` only checks length 5-24 + bare `endswith("up")` — so `up_$(reboot)up` passes validation and is injected into the shell. Latent today (la.fwu-trigger not wired) but guaranteed live when EG-66/67 land; also silently fails if `xxd` is absent from the image. shell=True is entirely unnecessary. (Merged: 2 auditors.)
- **Fix:** Replace the subprocess with pure Python: `with open(file_path, 'rb') as f: header = f.read(16)`; check `b'aritco' in header` (matching the current latin-1/ASCII-column semantics). Removes both the injection and the xxd dependency. Pair with AUD-031 (extension tightening) in the same commit.
- **Effort:** small
- **Dependencies:** Must land before wiring la.fwu-trigger. Pairs with AUD-031.

---

## P2 — Should fix (quality/coverage gaps)

### AUD-022 [P2] [testing] Add tests for ModBusHandler core read/write/file-transfer paths
- **Location:** `src/liftApi/modbus_handler.py` (read_parameter:212, write_parameter:253, log_generate:326, generate_trace_log:350, write_upgrade_package:502, `_validate_*_response` family)
- **Problem:** The primary lift-communication module (1373 lines) is tested only at helper level; all main public APIs and every response validator have zero coverage (the special-handler tests `@patch.object` read_parameter away, 10×). The comment at lines 677-680 documents a prior silent regression in exactly this validator code when pymodbus 3 changed its repr — the risk has materialized before. Sibling Rs232Handler has deep write tests, so this is a gap, not policy.
- **Fix:** Drive read_parameter/write_parameter through a mocked `ModbusSerialClient` (read_holding_registers/write_registers returns incl. ExceptionResponse and `isError()==True`), asserting `(value, source, error-code-name)` tuples; add write_upgrade_package/generate_trace_log tests with canned file-record responses covering the `_validate_*_response` failure branches. unittest style.
- **Effort:** large
- **Dependencies:** After AUD-009 (file-record paths must work before their handler tests mean anything); AUD-003's sign test slots in here.

### AUD-023 [P2] [functionality] Decide and (if kept) port the vsvParam / VFD-transformation pipeline
- **Location:** `src/liftApi/lift_proxy.py:367-390`; missing counterpart to legacy twin_observer.cpp:60-95, support.hpp:166-190, main.cpp:570-602
- **Problem:** Legacy maintained a vsvParam schedule (AHL {365,366,368-374}; 1k {155-160,169,170,172}) excluded from onChange push and instead written to a logged-params file uploaded to blob every 24 h, with vfdDataTransformation scaling params 169/170/171 (Schneider %, Toshiba current/voltage vs rated). New gateway collects VFD data into the db (rs232 vfdResult path is wired) but has no vsv schedule, no unit transformation, and nothing writes the logged-params file (`disk_handler` getters exist unused). Default push lists currently exclude the vsv params, so the wrong-units exposure is latent (twin-config dependent), but the whole VFD telemetry category and coldstorage upload are silently lost.
- **Fix:** Get explicit product sign-off whether VFD/logged-params telemetry is in scope for the new gateway. If yes: port the vsvParam twin schedule + transformation + daily blob upload. If no: document the drop and add a guard excluding params 169-172/vsv from raw pushes so twin config can't push wrong-unit data.
- **Effort:** large (port) / small (sign-off + guard)
- **Dependencies:** Product decision first.

### AUD-024 [P2] [testing] Neutralize real `time.sleep` in rs232 tests (~150 s of the 158 s suite)
- **Location:** `utest/test_rs232_handler.py:70` (setup); `src/liftApi/rs232_handler.py:38` (`serial_timeout = 0.5`, ~15 sleep sites)
- **Problem:** Tests never override `serial_timeout` or patch `time.sleep`, so every serial-path test sleeps for real: 66 s + 33 s top offenders, 157.8 s total for 487 tests — ~20× slower feedback, growing with every new rs232 test.
- **Fix:** In test setup, after constructing the handler, set `self.rs.serial_timeout = 0` (safe: it's not passed to the Serial constructor; mocked responses are synchronous). Verify the suite passes and runtime drops to seconds.
- **Effort:** small
- **Dependencies:** **Do this first** — every later batch's test runs get ~20× faster.

### AUD-025 [P2] [implementation] Check err_code before indexing in `sync_time_rs232`
- **Location:** `src/lib/sync_time_handler.py:44-47`
- **Problem:** `response = resp_wanted[0]['updated']` executes before the err_code check; on serial failure `get_signal_from_serial_buffer` returns `(-1, -1, -1, err)` so `(-1)[0]` raises TypeError. Currently unreachable in production (no sync-time DDM is wired; sole entry point `handle_sync_time_request` has no callers), but it's a guaranteed crash-path the moment the DDM lands, and the only call site of this helper pattern that skips the err check. (Merged: 2 auditors.)
- **Fix:** Move the `err_code != NO_ERR` check above the access; also validate `resp_wanted` is a non-empty list of dicts; return `(-1, self.name, err_code)` on failure. Add a failure-path test.
- **Effort:** small
- **Dependencies:** Land before the sync-time DDM is wired.

### AUD-026 [P2] [implementation] Fix UnboundLocalError fall-through in `set_vfd_id_1k`
- **Location:** `src/liftApi/rs232_handler.py:1286-1292`
- **Problem:** `response`/`vfd_err_code` are bound inside a try whose except only logs; execution falls through to `response.replace(",", "-")` → UnboundLocalError. Trigger is a stale `{"logs":...}` dict interleaved in the buffer during a vfdId exchange (note: `__split_response` line 629 *assigns* rather than appends the logs dict — that shape quirk is the actual trigger). No production callers yet (vfd DDMs unwired), so latent.
- **Fix:** Return `(-1, self.name, Rs232Code.JSON_KEY_ERR.name)` from the except block, mirroring `get_ar_version` (lines 749-754).
- **Effort:** small
- **Dependencies:** Land before vfd DDMs are wired. Related shape quirk noted in AUD-036's area.

### AUD-027 [P2] [implementation] Fix chained comparison in logfile block-count validation
- **Location:** `src/liftApi/rs232_handler.py:206`
- **Problem:** `if 0 < int(data) > 64:` evaluates as `x > 64` only — zero/negative block counts pass validation and are serialized to the AR-GATE. Intended range is 1..64 (the `0 <` clause and the valid-case test prove intent). Not yet wired to a DDM; AR-GATE timeout path would catch the worst case.
- **Fix:** `if not 1 <= int(data) <= 64:` (confirm lower bound = 1; the `data='0'` old-firmware fallback at line 487 happens post-validation and is unaffected). Update `utest/test_rs232_handler.py:251-263`.
- **Effort:** small

### AUD-028 [P2] [implementation] Tighten `_pack_value` lower bound to INT32_MIN
- **Location:** `src/liftApi/modbus_handler.py:1131`
- **Problem:** `val < -(1 << 32)` lets values in `[-(2**32), -(2**31))` through; `& 0xFFFF` masking silently wraps them to an unrelated positive register pair written to the LCM (e.g. `-2147483649` packs as `0x7FFFFFFF`). Reachable from la.write.parameter (no upstream range check). Existing test covers only the positive bound.
- **Fix:** `if val >= (1 << 32) or val < -(1 << 31): raise ValueError`; add a test for `-(2**31) - 1`.
- **Effort:** small
- **Dependencies:** Do with AUD-012/013 (same write path / same test file).

### AUD-029 [P2] [stability] Drain `saved_vfdResult_notification` before poll_lift's early return
- **Location:** `src/liftApi/rs232_handler.py:1470-1475` (early return), `:633` (append), `:1365` (only clear)
- **Problem:** Every vfdResult frame is appended during any serial read, but the list is only cleared in `get_vfd_motor_data`, which `poll_lift` skips via the `if not updated_parameters: return` early-out. vfd params can't defeat the early return themselves, so on a quiet lift with a periodic vfdRead, notifications accumulate unboundedly. Dormant today (vfdRead setters unwired; pattern inherited verbatim from smartlift2) but a real leak once vfd DDMs land.
- **Fix:** Call `get_vfd_motor_data()` before the early-return (vfd changes are themselves updated parameters), and cap the list defensively (newest N per vfd id).
- **Effort:** small
- **Dependencies:** Land before vfd DDMs are wired.

### AUD-030 [P2] [functionality] Move device identity (id/scope/cert paths) out of hardcoded Config
- **Location:** `src/config.py:7-13`; `src/cloudApi/dps_client.py:45-49`
- **Problem:** `DEVICE_NAME="GW-dev-test2"`, SCOPE_ID, and cert paths are hardcoded to one dev identity with no env override. The PEMs are NOT committed (gitignored — earlier claim refuted) and X.509 DPS requires registration_id == cert CN, so the fleet failure mode is *provisioning failure / device offline*, not session hijack — a production-readiness gap, not a live defect.
- **Fix:** Load device id, scope id, and cert/key paths from env vars (consistent with the gw.* env-var identity design) with the current values as dev defaults — and fail fast with a clear error in non-dev contexts when absent.
- **Effort:** small
- **Dependencies:** Coordinate env-var names with AUD-017.

### AUD-031 [P2] [implementation] Require literal `.up` extension (and strict charset) in `_validate_up_file`
- **Location:** `src/liftApi/modbus_handler.py:987, 997`
- **Problem:** `file_extension = "up"` (no dot) — `setup`/`backup` pass the gate meant to "prevent transferring any random file to LCM"; the docstring's own format is `up_<...>.up`. Bounded by the `aritco` header check downstream, but it's the only filename-based guard.
- **Fix:** `file_extension = ".up"`, plus a strict charset check (e.g. `^up_[A-Za-z0-9._-]+\.up$`) which also closes the metacharacter surface from AUD-021. Same commit as AUD-021.
- **Effort:** small
- **Dependencies:** Pairs with AUD-021.

---

## P3 — Nice to have

### AUD-032 [P3] [stability] DiskHandler: fail fast on config.json load failure
- `src/filemgmt/disk_handler.py:99-101` — except logs and continues (`# raise SystemExit TODO: Remove comment`), leaving sfs_config/gateway_config/file_status unset; surfaces later as opaque AttributeError via ModBusHandler init (modbus_handler.py:145-147 even has dead SystemExit-catch code expecting the raise). **Fix:** re-raise with a descriptive message (matches author intent); remove the dead catch. Effort: small.

### AUD-033 [P3] [implementation] Close the unmatched handler's serial port after lift identification
- `src/liftApi/lift_proxy.py:88-121` — both handlers open their tty in `__init__`; the identification loser is dropped relying on GC finalizers (works in CPython today, fragile). **Fix:** add `close()` to both handlers (`client.close()`); call it on the loser per match arm, both on UNKNOWN. Effort: small. Note: interacts with AUD-004's continue-on-UNKNOWN.

### AUD-034 [P3] [stability] Close stale ModbusSerialClient before recreating on port flap
- `src/liftApi/modbus_handler.py:186` — `_setup_connection` rebinds `self.client` without closing the old one; GC reclaims the fd in practice, but pymodbus opens with `exclusive=True` so a not-yet-collected stale fd could transiently block reconnection. **Fix:** `self.client.close()` (guarded) before recreating, or reuse + reconnect. Effort: small.

### AUD-035 [P3] [stability] Hold references to BLE `_dispatch` tasks
- `src/bluetoothApi/server.py:183-190` — `create_task` result discarded (weak-ref GC hazard, residual unlogged exceptions); controller coroutines already self-log I/O failures, so impact is hygiene. **Fix:** make `_dispatch` an instance method; keep `self._tasks` set with `add_done_callback` (discard + log `task.exception()`); cancel outstanding tasks in `stop()`. Effort: small. (Merged: 2 auditors.)

### AUD-036 [P3] [implementation] Remove dead `'time' in rsp` branch and unused KeyError-probe bindings
- `src/liftApi/rs232_handler.py:630, 433-437` — `elif 'time' in rsp:` is unreachable (time responses keyed `cmd`/`updated`) and would break sync_time's list-shape expectation if it ever fired; `rsp_data`/`rsp_type` bindings exist only as implicit KeyError probes. **Fix:** delete the dead branch; replace the bindings with explicit key-presence checks (don't just delete — the KeyError path is load-bearing). Effort: small. Also note the `'logs'` branch's assign-vs-append quirk feeding AUD-026.

### AUD-037 [P3] [testing] Add `testpaths = utest` to pytest.ini
- Bare `pytest` from repo root collects `tests/test_blob_integration.py` and `tests/iot-test/iot_test.py` (Azure-dependent operator scripts) at import time. CI passes the path explicitly, so behavior there is unchanged. Effort: tiny — do alongside AUD-024.

### AUD-038 [P3] [testing] Pin DOWNLOAD_HOST_ALLOWLIST contents in tests
- `utest/test_config_download.py:22-24` asserts only "non-empty list"; broadening the allowlist (a security control) passes the suite. Behavioral deny-path tests exist in test_file_download.py. **Fix:** assert the exact expected entries (`["*.blob.core.windows.net"]`). Effort: tiny.

### AUD-039 [P3] [testing] Replace wall-clock sleeps in heartbeat controller tests
- `utest/test_controller.py:207, 225` — 0.1 s/0.03 s real sleeps with tick-count/RSSI assertions; Windows CI timer resolution (~15.6 ms) leaves ~1-tick margin → intermittent flakes. **Fix:** use the mock_sleep / asyncio.Event pattern already in `utest/test_lift_proxy.py:120,176-179`. Effort: small.

### AUD-040 [P3] [testing] Fix broken mock and ticketless skip in `test_write_log_to_file_no_dir`
- `utest/test_rs232_handler.py:2676-2690` — skip reason ("Esseti-GW") is false: the test mocks `self.rs._RS232Handler__set_1000_log_file_dir` — wrong name-mangling (class is `Rs232Handler`) AND wrong method name (real: `__set_1000_file_dir`) — so the mock is dead and the assertion fails. **Fix:** correct the mock target to `_Rs232Handler__set_1000_file_dir`, unskip, or reference an EG ticket. Effort: small.

### AUD-041 [P3] [testing] Migrate test_rs232_handler.py to unittest conventions
- `utest/test_rs232_handler.py:65` — pytest-style class (no TestCase base, setup_method, monkeypatch, third-party `mock`, module-level mutable globals). Runs fine under the pytest-based CI; pure convention/hygiene debt. **Fix:** migrate to `unittest.TestCase` + `setUp`/`tearDown` + `unittest.mock` when next doing major work in the file (it is already modified on this branch). Effort: large. Do AFTER AUD-001/002 land so behavior changes aren't entangled with the migration.

### AUD-042 [P3] [testing] Commit tests/iot-test/ and document CI vs bench-only suites
- `tests/iot-test/` (the EG-64 DDM acceptance harness, CI-ready exit codes) is untracked; no pipeline runs it (inherent — needs a live hub + running gateway). **Fix:** commit it at branch closeout (per existing workflow); document in README/azure-pipelines.yml which suites are CI vs bench-only; optionally add a manual pipeline stage. Effort: small.

### AUD-043 [P3] [testing] Smoke tests for main.py composition root and LiftSimulator
- No test imports `main` or `lift_simulator`; main wiring is an active churn area (3d78d1f). **Fix:** patched smoke test of `main()` asserting each component is constructed with expected collaborators; one-iteration LiftSimulator test with asyncio.sleep patched. Effort: medium. Do AFTER AUD-004/010 (main() restructure) — writing it earlier creates churn.

---

## Suggested implementation order

Work in batches; after each batch run `pytest utest/` and `python -m mypy .` from repo root. Commit per batch with `EG-XX` prefixes (split whitespace-only cleanups into separate commits). Do not push without explicit approval.

**Batch 0 — Test infrastructure (makes everything after faster)**
AUD-024 (kill rs232 sleeps), AUD-037 (testpaths). ~30 min, immediately validates the suite runs in seconds.

**Batch 1 — P0 point fixes (small, independent, test-first)**
AUD-001 (eval → json.loads), AUD-002 (read_serial loop bound), AUD-003 (c_int32 + sign test). Each is a localized change with a clear failing-test-first opportunity.

**Batch 2 — main.py restructure (do as one unit)**
AUD-004 (startup retries + continue-on-UNKNOWN) + AUD-010 (guard receive loops, task supervision). Then AUD-043 (main smoke test) to lock the new wiring. AUD-033 (close loser handler) fits here since UNKNOWN handling changes.

**Batch 3 — Cloud contract parity (small fixes, big backend impact)**
AUD-006 (nested gw heartbeat), AUD-007 (lift-type numeric map — hoist map first), AUD-016 (errors array), AUD-017 (env-var metadata), AUD-005 (desired-patch merge + tests). Verify against the iot-test harness where possible.

**Batch 4 — Lift write/read path**
AUD-012 (write_param int/cache) → AUD-013 (live read-back, builds on 012) → AUD-028 (pack_value bound). Same test file; one coherent review unit.

**Batch 5 — Polling reliability**
AUD-014 (force_read_all) + AUD-019 (sweep bound) together (same code area), then AUD-015 (version int guard). AUD-018 (telemetry outbox) last in this batch.

**Batch 6 — Security hardening**
AUD-021 + AUD-031 (one commit: drop xxd shell, .up regex), AUD-008 (blob to_thread + chunked streaming), AUD-020 (BLE auth — gated on SDK capability check; start the vendor question early).

**Batch 7 — File-record resurrection (largest item, prerequisite for EG-65+)**
AUD-009 (pymodbus 3.x port + pin + smoke tests) → AUD-022 (ModBusHandler core tests, including file-transfer paths).

**Batch 8 — Pre-wiring latent fixes (land before the next DDM tickets)**
AUD-025 (sync_time), AUD-026 (set_vfd), AUD-029 (vfdResult drain), AUD-027 (logfile range).

**Batch 9 — P2/P3 cleanup, opportunistic**
AUD-023 (VFD — needs product decision first; raise it now, implement when answered), AUD-030, AUD-032, AUD-034, AUD-035, AUD-036, AUD-038, AUD-039, AUD-040, AUD-042. AUD-041 (test migration) only when next doing major rs232 test work.
