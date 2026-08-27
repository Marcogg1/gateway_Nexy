import asyncio
import random
from azure.iot.device.aio import IoTHubDeviceClient
from bluetoothApi.server import build_from_env as build_bluetooth_server
from bluetoothApi.wifi_cli import WifiCli
from cloudApi.connection_monitor import ConnectionMonitor
from cloudApi.dps_client import DPSClient
from cloudApi.device_client import DeviceClientFactory
from cloudApi.method_request_handler import MethodRequestHandler
from cloudApi.device_twin_reported import DeviceTwinReporter
from cloudApi.event_sender import EventSender
from cloudApi.heartbeat_handler import HeartbeatHandler
from cloudApi.device_twin_desired_handler import DeviceTwinDesiredHandler
from liftApi.lift_simulator import LiftSimulator
from liftApi.lift_proxy import LiftProxy
from liftApi.lift_identifier import LiftType
from liftApi.idle_supervisor import IdleSupervisor
from lib.logging_config import setup_logging, get_logger

# Setup logging at module level
setup_logging()
logger = get_logger(__name__)

# Capped exponential backoff for the startup retry loops.
CONNECT_BACKOFF_INITIAL_S = 1
CONNECT_BACKOFF_MAX_S = 60
# connect() attempts per DPS registration before re-provisioning.
CONNECT_ATTEMPTS_PER_PROVISION = 3


def _jittered(backoff: float) -> float:
    """Randomize a backoff delay to avoid fleet-wide retry alignment."""
    return backoff * (0.5 + random.random())


def _log_retry(step: str, error: Exception, backoff: float,
               first_failure: bool) -> None:
    """
    Log a startup retry — full traceback only on the first failure.

    Later retries log a one-line warning so an extended outage does not
    churn the rotating error log with identical tracebacks.
    """
    if first_failure:
        logger.error("%s failed, retrying in ~%ds: %s",
                     step, backoff, error, exc_info=True)
    else:
        logger.warning("%s failed, retrying in ~%ds: %s",
                       step, backoff, error)


async def _shutdown_client(device_client: IoTHubDeviceClient) -> None:
    """Best-effort shutdown of a device client being discarded."""
    try:
        await device_client.shutdown()
    except Exception:
        logger.exception("Device client shutdown failed")


async def provision_and_connect() -> IoTHubDeviceClient:
    """
    Provision via DPS and connect to IoT Hub, retrying until it succeeds.

    Retries indefinitely with capped, jittered exponential backoff.
    connect() is retried a few times on the same registration before a
    full re-provision, and a discarded client is shut down so its MQTT
    pipeline does not leak across retries.

    Returns:
        A connected IoTHubDeviceClient.
    """
    backoff = CONNECT_BACKOFF_INITIAL_S
    first_failure = True
    while True:
        try:
            dps = DPSClient()
            registration_result = await dps.create_provisioning_device()
            factory = DeviceClientFactory(registration_result)
            device_client = factory.create_client()
        except Exception as e:
            _log_retry("Provisioning", e, backoff, first_failure)
            first_failure = False
            await asyncio.sleep(_jittered(backoff))
            backoff = min(backoff * 2, CONNECT_BACKOFF_MAX_S)
            continue

        # Provisioning stage succeeded — restart the backoff schedule
        # so a fresh connect failure is not paced by earlier DPS delays.
        backoff = CONNECT_BACKOFF_INITIAL_S
        first_failure = True

        # Note: the sleep after the LAST failed attempt is intentional —
        # it paces the DPS re-provision that follows, not just the next
        # connect. Removing it would hammer DPS unpaced.
        for _ in range(CONNECT_ATTEMPTS_PER_PROVISION):
            try:
                await device_client.connect()
                logger.info("Device connected to IoT Hub")
                return device_client
            except Exception as e:
                _log_retry("Connect", e, backoff, first_failure)
                first_failure = False
                await asyncio.sleep(_jittered(backoff))
                backoff = min(backoff * 2, CONNECT_BACKOFF_MAX_S)

        # Connect attempts exhausted — hub assignment may be stale.
        # Discard the client and start over from provisioning.
        await _shutdown_client(device_client)


async def _create_desired_handler(
        device_client: IoTHubDeviceClient) -> DeviceTwinDesiredHandler:
    """
    Create the desired-twin handler, retrying its twin fetch on failure.

    DeviceTwinDesiredHandler.create() performs a live get_twin() round
    trip; a transient failure there must not kill a freshly connected
    gateway, so it retries with the same capped backoff as connect.

    Returns:
        An initialized DeviceTwinDesiredHandler.
    """
    backoff = CONNECT_BACKOFF_INITIAL_S
    first_failure = True
    while True:
        try:
            return await DeviceTwinDesiredHandler.create(device_client)
        except Exception as e:
            _log_retry("Desired-twin init", e, backoff, first_failure)
            first_failure = False
            await asyncio.sleep(_jittered(backoff))
            backoff = min(backoff * 2, CONNECT_BACKOFF_MAX_S)


async def main(lift_sim_enabled: bool = False):
    """
    Main asynchronous function to initialize and run the IoT device client.

    Args:
        lift_sim_enabled: When True, runs LiftSimulator's fake telemetry
            and twin-reporting loops alongside the real lift data path.
            Use only for cloud-pipeline testing without a connected lift.
            Defaults to False so production runs do not emit fake data.
    """
    
    logger.info("Starting main")

    # Provision and connect — retries indefinitely, never gives up
    device_client = await provision_and_connect()

    # From here on the client is connected: shut it down on any exit so
    # a fatal error does not leave an orphaned MQTT session behind (its
    # reconnect timer could otherwise stall interpreter exit).
    bluetooth_server = None
    try:
        # Initialize lift proxy (creates handlers, identifies lift type).
        # UNKNOWN lift type is not fatal: the cloud stack must still run
        # so the gateway stays reachable; lift DDMs return INIT_ERR
        # envelopes.
        try:
            idle_supervisor = IdleSupervisor()
            proxy = await LiftProxy.create(idle_supervisor=idle_supervisor)
            if proxy.lift_type == LiftType.UNKNOWN:
                logger.warning(
                    "Could not identify lift type, continuing with cloud stack "
                    "— will keep probing in background")
            else:
                logger.info("Lift type identified: %s", proxy.lift_type.value)
        except Exception as e:
            logger.error(f"Lift proxy initialization failed: {e}", exc_info=True)
            raise

        # Init handlers
        try:
            reporter = DeviceTwinReporter(device_client)
            send_event = EventSender(device_client, proxy.lift_type)
            lift_sim = LiftSimulator(reporter, send_event) if lift_sim_enabled else None
            desired_handler = await _create_desired_handler(device_client)
            method_handler = MethodRequestHandler(
                device_client, proxy, reporter, desired_handler)
            heartbeat_handler = HeartbeatHandler(send_event, reporter, desired_handler)
            connection_monitor = ConnectionMonitor(device_client)
            connection_monitor.attach()
        except Exception as e:
            logger.error(f"Handler initialization failed: {e}", exc_info=True)
            raise

        # Start BLE server for WiFi onboarding (modern protocol).
        # BLE failure is non-fatal — lift data path must keep running even
        # if the BLE adapter is missing or the SDK fails to load.
        try:
            bluetooth_server = build_bluetooth_server(wifi_cli=WifiCli())
            await bluetooth_server.start()
        except Exception as e:
            logger.error(f"Bluetooth server failed to start: {e}", exc_info=True)

        #Run in parallel
        tasks = [
            method_handler.listen_for_method(),
            desired_handler.listen_for_desired_updates(),
            heartbeat_handler.run(),
            proxy.run(send_event, desired_handler, reporter),
        ]
        if lift_sim is not None:
            tasks += [
                lift_sim.report_temperature_loop(),
                lift_sim.simulate_lift_operation(),
                lift_sim.send_parameter_data(),
            ]
        await asyncio.gather(*tasks)
    finally:
        if bluetooth_server is not None:
            try:
                await bluetooth_server.stop()
            except Exception:
                logger.exception("Bluetooth server stop failed")
        await _shutdown_client(device_client)


if __name__ == "__main__":
    asyncio.run(main())