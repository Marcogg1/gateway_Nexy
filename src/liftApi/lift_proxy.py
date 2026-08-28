"""LiftProxy — single entry point to lift hardware for all consumers.

Owns the matched handler + lib pair based on the identified lift type.
All lift access (cloud, WiFi, BT) goes through this proxy.
"""

import asyncio
import time
from typing import Any, cast

from cloudApi.device_twin_desired_handler import DeviceTwinDesiredHandler
from cloudApi.device_twin_reported import DeviceTwinReporter
from cloudApi.event_sender import EventSender
from lib.ahl_lib import AhlLib
from lib.error_signals import LpCode, Rs232Code
from lib.logging_config import get_logger
from lib.thousand_lib import ThousandLib
from liftApi.idle_supervisor import IdleSupervisor, ParamChange
from liftApi.lift_identifier import LiftType, identify_lift
from liftApi.modbus_handler import ModBusHandler, parse_int_value
from liftApi.rs232_handler import Rs232Handler

logger = get_logger(__name__)

IDENTIFY_MAX_RETRIES = 10
IDENTIFY_RETRY_DELAY = 5
REIDENTIFY_INTERVAL = 5             # seconds between background probes
REIDENTIFY_LOG_EVERY = 12           # background probes between summary logs
REPORT_TIMEOUT = 30                 # seconds to wait for a twin patch
DEFAULT_ON_CHANGE_INTERVAL = 5      # seconds
DEFAULT_DAILY_INTERVAL = 86400      # 24 hours
AHL_AR_PARAM = 96


class LiftProxy:
    """Proxy layer between consumers and lift hardware.

    Creates both handlers, identifies the lift type, and keeps only
    the matched handler + lib pair. Consumers access lift data through
    this proxy — never directly through handlers.

    Usage:
        proxy = await LiftProxy.create()
    """

    def __init__(self, idle_supervisor: IdleSupervisor | None = None) -> None:
        self._handler: ModBusHandler | Rs232Handler | None = None
        self._lib: AhlLib | ThousandLib | None = None
        self._lift_type: LiftType = LiftType.UNKNOWN
        self._event_sender: EventSender | None = None
        self._desired_handler: DeviceTwinDesiredHandler | None = None
        self._handler_lock: asyncio.Lock = asyncio.Lock()
        self._idle_supervisor: IdleSupervisor | None = idle_supervisor
        self._force_read_all: bool = True
        self._modbus_handler: ModBusHandler | None = None
        self._rs232_handler: Rs232Handler | None = None
        self._thousand_lib: ThousandLib | None = None
        self._reporter: DeviceTwinReporter | None = None

    @classmethod
    async def create(
        cls,
        idle_supervisor: IdleSupervisor | None = None,
    ) -> "LiftProxy":
        """Async factory — creates handlers, identifies lift, keeps matched pair.

        Args:
            idle_supervisor: Optional observer notified of parameter changes
                after each poll cycle. If omitted, the proxy runs without
                supervision (useful in tests and minimal startup paths).

        Returns:
            Initialized LiftProxy with the correct handler + lib for the
            connected lift, or UNKNOWN if neither responds.
        """
        proxy = cls(idle_supervisor=idle_supervisor)
        await proxy._create_handlers()
        for attempt in range(IDENTIFY_MAX_RETRIES):
            if await proxy._try_identify():
                return proxy
            if attempt < IDENTIFY_MAX_RETRIES - 1:
                logger.warning(
                    "Identification attempt %d/%d failed, retrying in %ds",
                    attempt + 1, IDENTIFY_MAX_RETRIES, IDENTIFY_RETRY_DELAY
                )
                await asyncio.sleep(IDENTIFY_RETRY_DELAY)
        logger.error(
            "%s: %s - Failed to identify lift after %d attempts",
            LpCode.SOURCE.value, LpCode.IDENTIFY_ERR.name,
            IDENTIFY_MAX_RETRIES
        )
        return proxy

    @property
    def lift_type(self) -> LiftType:
        """The identified lift type (AHL, ONE_K, or UNKNOWN)."""
        return self._lift_type

    @property
    def handler(self) -> ModBusHandler | Rs232Handler | None:
        """The matched hardware handler for the identified lift type."""
        return self._handler

    @property
    def lib(self) -> AhlLib | ThousandLib | None:
        """The parameter library for the identified lift type."""
        return self._lib

    async def _create_handlers(self) -> None:
        """Construct both hardware handlers and the shared 1k lib.

        Both handlers stay alive while the lift type is UNKNOWN so the
        background re-identification loop can keep probing both buses.
        The losing handler is closed and dereferenced by _bind().
        """
        self._thousand_lib = ThousandLib()
        self._modbus_handler = await asyncio.to_thread(ModBusHandler)
        self._rs232_handler = await asyncio.to_thread(
            Rs232Handler, self._thousand_lib
        )

    async def _try_identify(self, *, quiet: bool = False) -> bool:
        """Run one identification round and bind the pair on success.

        Args:
            quiet: When True, the probe demotes its per-round failure
                logging to DEBUG. Used by the background loop so a lift
                that never answers does not flood the log (FR-010).

        Returns:
            True if the lift was identified and the handler + lib pair is
            bound, False if the probe returned UNKNOWN.
        """
        lift_type = await identify_lift(
            self._modbus_handler, self._rs232_handler, quiet=quiet
        )
        if lift_type == LiftType.UNKNOWN:
            return False
        await self._bind(lift_type)
        return True

    async def _bind(self, lift_type: LiftType) -> None:
        """Commit one handler + lib pair for the identified lift type.

        Runs under the handler lock so no consumer observes a half-bound
        pair. Everything that can still fail — the AHL polling-table
        detection and closing the losing handler — happens on locals
        first; only then are self._handler and self._lib published, the
        candidate references dropped, the cold-start full read re-armed
        and self._lift_type set last. That final block contains no await,
        so a raising probe or a cancellation before publication leaves the
        proxy exactly as it was: UNKNOWN, with both candidates alive
        (FR-008). The losing handler is closed only after publication, so a
        cancellation on that thread hop can leak its file descriptor but
        can never leave a half-bound proxy.

        Args:
            lift_type: The identified lift type (AHL or ONE_K).
        """
        async with self._handler_lock:
            handler: ModBusHandler | Rs232Handler | None
            lib: AhlLib | ThousandLib | None
            loser: ModBusHandler | Rs232Handler | None = None
            match lift_type:
                case LiftType.AHL:
                    handler = self._modbus_handler
                    ahl_lib = AhlLib()
                    lib = ahl_lib
                    if handler is None:
                        logger.error("_bind called for AHL without a Modbus handler")
                    else:
                        await self._detect_ahl_polling_table(handler, ahl_lib)
                    loser = self._rs232_handler
                    logger.info("LiftProxy initialized for AHL lift")
                case LiftType.ONE_K:
                    handler = self._rs232_handler
                    lib = self._thousand_lib
                    loser = self._modbus_handler
                    logger.info("LiftProxy initialized for 1k lift")
            # Publish the bound pair — no await below this line.
            self._handler = handler
            self._lib = lib
            self._modbus_handler = None
            self._rs232_handler = None
            self._thousand_lib = None
            self._force_read_all = True
            self._lift_type = lift_type
        # Release the losing bus after publication: a cancellation on this
        # thread hop can leak its file descriptor, but can never leave a
        # half-bound proxy behind (FR-008).
        if loser is not None:
            await asyncio.to_thread(loser.close)

    def get_param_value(self, param: int) -> tuple[int | str | None, LpCode]:
        """Read a parameter value from the lib's database.

        Args:
            param: Parameter number to read.

        Returns:
            Tuple of (value, LpCode) where value is None on INIT_ERR
            or -1 on lib errors.
        """
        if self._lib is None:
            return None, LpCode.INIT_ERR

        value, err_code_name = self._lib.get_param(param)
        try:
            return value, LpCode[err_code_name]
        except KeyError:
            logger.warning("Unknown error code from lib: %s", err_code_name)
            return value, LpCode.COM_ERR

    async def read_param_live(self, param: int) -> tuple[Any, str, str]:
        """Read a parameter through the handler.

        On AHL this is a live Modbus read from the LCM. On 1k the
        Rs232Handler answers from the ThousandLib database (the 1k
        protocol has no on-demand hardware read).

        Args:
            param: Parameter number to read.

        Returns:
            Tuple of (value, error_source, error_code) from the handler,
            or (None, LiftProxy, INIT_ERR) when no handler is initialised.
        """
        if self._handler is None:
            return None, LpCode.SOURCE.value, LpCode.INIT_ERR.name
        async with self._handler_lock:
            return await asyncio.to_thread(self._handler.read_parameter, [str(param)])

    async def read_ar_number(self) -> tuple[Any, str, str]:
        """Read the article (AR) number live, dispatched by lift type.

        AHL stores the AR number in read-only param 96. 1k exposes it as
        the ``liftRef1`` generic-text package.

        Returns:
            Tuple of (value, error_source, error_code). Value is a string
            on success, None on init failure.
        """
        if self._lift_type == LiftType.AHL:
            return await self.read_param_live(AHL_AR_PARAM)
        if self._lift_type == LiftType.ONE_K and self._handler is not None:
            rs232 = cast(Rs232Handler, self._handler)
            async with self._handler_lock:
                value, source, code = await asyncio.to_thread(
                    rs232.get_generic_text, "liftRef1"
                )
            if code == Rs232Code.NO_ERR.name and isinstance(value, list) and value:
                return value[0], source, code
            return value, source, code
        return None, LpCode.SOURCE.value, LpCode.INIT_ERR.name

    async def write_ar_number(self, value: str) -> tuple[Any, str, str]:
        """Write the article (AR) number, dispatched by lift type.

        AHL param 96 is read-only, so AHL writes are rejected. 1k writes
        the ``liftRef1`` generic-text package and returns the actual text.

        Args:
            value: New AR number string.

        Returns:
            Tuple of (actual_value, error_source, error_code). actual_value
            is None on rejection/init failure.
        """
        if self._lift_type == LiftType.AHL:
            return None, LpCode.SOURCE.value, LpCode.PARAM_READ_ONLY.name
        if self._lift_type == LiftType.ONE_K and self._handler is not None:
            rs232 = cast(Rs232Handler, self._handler)
            async with self._handler_lock:
                return await asyncio.to_thread(
                    rs232.write_generic_text, ["liftRef1", value]
                )
        return None, LpCode.SOURCE.value, LpCode.INIT_ERR.name

    async def write_param(self, param: str, value: str) -> tuple[int, str, str]:
        """Write a parameter value to lift hardware via the handler.

        Args:
            param: Parameter number as string.
            value: Value to write as string.

        Returns:
            Tuple of (status, error_source, error_code) matching the
            legacy cloud API contract.
        """
        if self._handler is None:
            return -1, LpCode.SOURCE.value, LpCode.INIT_ERR.name
        async with self._handler_lock:
            status, source, code = await asyncio.to_thread(
                self._handler.write_parameter, [param, value]
            )
        if status == 0:
            self._mirror_ahl_write_to_cache(param, value)
        return status, source, code

    async def write_read_param(
        self, param: str, value: str
    ) -> tuple[int, Any, str, str]:
        """Write a parameter, read it back, and sync the cache — atomically.

        Holds the handler lock across write and read-back so the polling
        loop cannot interleave. On AHL the read-back is a live hardware
        read that detects LCM-side clamping of the written value; only a
        verified read-back is written to the cache — on failure the
        cache is left for the next poll cycle to correct. On 1k the
        handler answers from the ThousandLib database (the protocol has
        no live read), so the read-back mirrors the written value and
        the cache is not rewritten; note the lock then spans the 1k
        write's full read/write file transfer round trip.

        Args:
            param: Parameter number as string.
            value: Value to write as string.

        Returns:
            Tuple of (status, read_back_value, error_source, error_code).
            status is the write status; read_back_value is None unless
            the read-back succeeded.
        """
        if self._handler is None:
            return -1, None, LpCode.SOURCE.value, LpCode.INIT_ERR.name
        async with self._handler_lock:
            status, source, code = await asyncio.to_thread(
                self._handler.write_parameter, [param, value]
            )
            if status != 0:
                return status, None, source, code
            rb_value, rb_source, rb_code = await asyncio.to_thread(
                self._handler.read_parameter, [param]
            )
        if rb_code != LpCode.NO_ERR.name:
            return 0, None, rb_source, rb_code
        if self._lib is not None and self._lift_type == LiftType.AHL:
            self._lib.set_param(int(param), rb_value)
        return 0, rb_value, rb_source, rb_code

    def _mirror_ahl_write_to_cache(self, param: str, value: str) -> None:
        """Mirror a successful AHL hardware write into the lib cache.

        parse_int_value already normalizes hex bit patterns to the
        signed decode the read path reports. 1k is skipped: Rs232Handler
        already updates the ThousandLib cache on write, and its values
        may be string-typed.

        Args:
            param: Parameter number as string.
            value: Written value as string (decimal or 0x-prefixed hex).
        """
        if self._lib is not None and self._lift_type == LiftType.AHL:
            self._lib.set_param(int(param), parse_int_value(value))

    async def poll_params(self, force_read_all: bool = False) -> list[int]:
        """Poll lift hardware for changed parameters.

        Delegates to the lib's poll_params method, which handles the
        hardware-specific polling strategy internally (bitmask decode
        for AHL, package-based poll for 1K).

        The pending cold-start flag (self._force_read_all, re-armed by
        _bind()) is read and cleared here, under the handler lock, so a
        poll cannot clear a flag that _bind() re-armed while the poll was
        queued on that same lock. A raising lib call skips the clear, so
        the next cycle retries the full read.

        Args:
            force_read_all: When True, force the lib to read every
                parameter from hardware even if the pending cold-start
                flag is already cleared. Callers that just want the
                normal behaviour pass nothing.

        Returns:
            List of parameter IDs that changed since last poll.
        """
        if self._lib is None or self._handler is None:
            return []
        async with self._handler_lock:
            force = force_read_all or self._force_read_all
            changed = await self._lib.poll_params(
                self._handler, force_read_all=force
            )
            self._force_read_all = False
        return changed

    async def run(
        self,
        event_sender: EventSender,
        desired_handler: DeviceTwinDesiredHandler,
        reporter: DeviceTwinReporter,
    ) -> None:
        """Report lift type, then start onChange and daily polling loops.

        Reports the current lift_type unconditionally, including "unknown"
        when identification hasn't completed yet — polling no-ops until
        identification succeeds and _reidentify_loop re-reports the real
        type via _on_identified() (see AIOT-183).

        Args:
            event_sender: For sending telemetry events to IoT Hub.
            desired_handler: For reading param push lists and intervals
                from device twin desired properties.
            reporter: For patching reported twin properties. Used here to
                announce the lift type once at startup, and again by
                _on_identified() after late identification.
        """
        self._event_sender = event_sender
        self._desired_handler = desired_handler
        self._reporter = reporter
        await self._report_lift_type(reporter)
        await asyncio.gather(
            self._polling_loop(),
            self._daily_loop(),
            self._reidentify_loop(),
        )

    async def _report_lift_type(self, reporter: DeviceTwinReporter) -> None:
        """Report the current lift type, bounded so it cannot stall startup.

        The twin request/response path has no timeout of its own, so a
        publish whose response never arrives would block ``run()`` before
        the polling and re-identification loops start. The timeout keeps the
        lift data path independent of cloud state; re-sending a patch lost
        while offline is tracked in AIOT-189.

        Args:
            reporter: Reporter used to patch the reported twin property.
        """
        try:
            await asyncio.wait_for(
                reporter.report_property("gw.liftType", self._lift_type.value),
                REPORT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out reporting gw.liftType after %ds - continuing startup",
                REPORT_TIMEOUT,
            )

    async def _reidentify_loop(self) -> None:
        """Probe both buses until the lift is identified, then stop.

        Runs alongside the polling loops so a lift powered up after the
        gateway still gets identified without a restart. Returns as soon
        as _try_identify() binds a handler + lib pair; gather() keeps the
        other loops running. A transient probe error is logged and never
        ends the loop, while cancellation propagates untouched.

        Logging is rate limited: the probe itself runs with quiet=True so
        its per-round failure lines drop to DEBUG, leaving one WARNING on
        the first miss and a summary every REIDENTIFY_LOG_EVERY attempts
        (FR-010).
        """
        attempts = 0
        while self._lift_type == LiftType.UNKNOWN:
            await asyncio.sleep(REIDENTIFY_INTERVAL)
            attempts += 1
            try:
                if await self._try_identify(quiet=True):
                    await self._on_identified()
                    return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Background lift identification failed")
            else:
                if attempts == 1:
                    logger.warning(
                        "Lift not identified, probing in background (%ds between rounds)",
                        REIDENTIFY_INTERVAL,
                    )
                elif attempts % REIDENTIFY_LOG_EVERY == 0:
                    logger.info(
                        "Lift still unidentified after %d background attempts",
                        attempts,
                    )

    async def _on_identified(self) -> None:
        """Announce a lift identified after startup.

        Called once by _reidentify_loop() right after the handler + lib
        pair is bound. Updates the telemetry lift type tag and re-reports
        the device twin property so every cloud-facing surface agrees
        with the newly bound lift type (see AIOT-183 US2/US3). A reporter
        failure is logged but never raised — it must not undo the bind.
        """
        logger.info("Lift identified in background as %s", self._lift_type.value)
        if self._event_sender is not None:
            self._event_sender.lift_type = self._lift_type
        if self._reporter is not None:
            try:
                await self._reporter.report_property(
                    "gw.liftType", self._lift_type.value
                )
            except Exception:
                logger.exception("Failed to report gw.liftType after late identification")

    async def _polling_loop(self) -> None:
        """Keep db fresh by polling hardware; push onChange params, notify supervisor.

        On the very first cycle the lib is asked to read every parameter
        (matching legacy `m_force_read_all`) so the db is fully populated
        from a cold start and the first push carries the full onChange
        list. poll_params() owns that pending flag — it consumes it under
        the handler lock and a raising call leaves it set for the next
        iteration to retry.
        """
        while True:
            try:
                changed = await self.poll_params()
                if changed:
                    await self._notify_supervisor(changed)
                    push_list = self._get_param_push_list("onChange")
                    push_set = set(push_list)
                    to_send = [p for p in changed if p in push_set]
                    if to_send:
                        await self._send_params(to_send)
            except Exception:
                logger.exception("onChange poll cycle failed")
            # Sleep after work so first poll runs immediately on startup.
            await asyncio.sleep(self._get_interval("liftAgentPolling", DEFAULT_ON_CHANGE_INTERVAL))

    async def _notify_supervisor(self, changed_ids: list[int]) -> None:
        """Build ParamChange list from changed ids and hand it to the supervisor.

        Reads the current cache value for each id (the new value, just written
        by lib.poll_params). Changes whose get_param returns a non-NO_ERR code
        are skipped. The supervisor call is bulkheaded: a raising supervisor
        never crashes the poll loop.
        """
        if self._idle_supervisor is None or self._lib is None:
            return
        changes: list[ParamChange] = []
        for pid in changed_ids:
            value, code = self._lib.get_param(pid)
            if code == LpCode.NO_ERR.name:
                changes.append(ParamChange(pid, value))
        if not changes:
            return
        try:
            await self._idle_supervisor.on_param_changes(changes)
        except Exception:
            logger.exception("IdleSupervisor failed")

    async def _daily_loop(self) -> None:
        """Push all daily params from the db on a 24h schedule."""
        while True:
            await asyncio.sleep(self._get_interval("dailyTimer", DEFAULT_DAILY_INTERVAL))
            try:
                daily_list = self._get_param_push_list("daily")
                await self._send_params(daily_list)
            except Exception:
                logger.exception("Daily poll cycle failed")

    async def _send_params(self, param_ids: list[int], source: str = "la.parameter.polling") -> None:
        """Build and send a parameter update event from db values."""
        if self._event_sender is None or self._lib is None:
            logger.error("_send_params called before proxy is initialised")
            return
        ts = int(time.time())
        data = []
        for pid in param_ids:
            value, code = self.get_param_value(pid)
            if code == LpCode.NO_ERR:
                data.append({"timestamp": ts, "value": value, "parameter": pid})
        if data:
            payload = {
                "data": data,
                "error": "",
                "event": "la.parameters.update",
                "source": source,
            }
            await self._event_sender.send_event(payload)

    async def push_param_event(self, param_ids: list[int]) -> None:
        """Emit a la.parameters.update event for params changed via DDM write.

        The poll loop suppresses DDM-initiated changes (write_param updates
        the cache, so the next poll sees no diff). This pushes them explicitly
        so the change enters telemetry history. Tagged with a DDM source.

        Args:
            param_ids: Parameter IDs that were just written.
        """
        await self._send_params(param_ids, source="la.parameter.ddm")

    def _get_param_push_list(self, list_type: str) -> list[int]:
        """Get param push list from desired properties, or lib defaults.

        Args:
            list_type: "onChange" or "daily".

        Returns:
            List of parameter IDs to push.
        """
        if self._lib is None:
            logger.error("_get_param_push_list called before proxy is initialised")
            return []
        try:
            if self._desired_handler is not None:
                param_push = self._desired_handler.desired_properties.get("paramPush", {})
                twin_list = param_push.get(list_type)
                if isinstance(twin_list, list) and twin_list:
                    return [int(p) for p in twin_list]
        except (TypeError, ValueError, KeyError):
            logger.debug("Invalid paramPush.%s in desired properties, using defaults", list_type)

        if list_type == "onChange":
            return self._lib.DEFAULT_ON_CHANGE_PARAMS
        return self._lib.DEFAULT_DAILY_PARAMS

    def _get_interval(self, key: str, default: int) -> int:
        """Get a polling interval from desired properties, or default.

        Args:
            key: Property name under "intervals" (e.g. "liftAgentPolling").
            default: Fallback interval in seconds.

        Returns:
            Interval in seconds.
        """
        try:
            if self._desired_handler is not None:
                intervals = self._desired_handler.desired_properties.get("intervals", {})
                value = intervals.get(key)
                if value is not None:
                    interval = int(value)
                    if interval > 0:
                        return interval
                    logger.warning("Invalid interval %s=%d, using default %d", key, interval, default)
        except (TypeError, ValueError, KeyError):
            logger.debug("Could not read intervals.%s, using default %d", key, default)
        return default

    async def _detect_ahl_polling_table(
        self, handler: ModBusHandler, lib: AhlLib
    ) -> None:
        """Detect which AHL polling table to use by reading param 127.

        If param 127 is readable, the lift uses new firmware with the
        new polling table. Otherwise, fall back to the old table.

        Takes the handler explicitly because it runs before _bind()
        publishes self._handler (FR-008).

        Args:
            handler: The Modbus handler to probe param 127 with.
            lib: The AhlLib instance whose polling table should be configured.
        """
        value, _, code = await asyncio.to_thread(
            handler.read_parameter, ["127"]
        )
        new_table = code == "NO_ERR"
        lib.set_polling_table(new_table)
        logger.info(
            "AHL polling table: %s (param 127 %s)",
            "new" if new_table else "old",
            "readable" if new_table else "not readable",
        )
