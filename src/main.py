import asyncio
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

    #Provisioning device client
    try:
        dps = DPSClient()
        registration_result = await dps.create_provisioning_device()
    except Exception as e:
        logger.error(f"Provisioning failed: {e}", exc_info=True)
        return

    #Create device client
    try:
        factory = DeviceClientFactory(registration_result)  
        device_client = factory.create_client()
        await device_client.connect()
        logger.info("Device connected to IoT Hub")
    except Exception as e:
        logger.error(f"Device client creation/connect failed: {e}", exc_info=True)
        return

    # Initialize lift proxy (creates handlers, identifies lift type)
    try:
        idle_supervisor = IdleSupervisor()
        proxy = await LiftProxy.create(idle_supervisor=idle_supervisor)
        if proxy.lift_type == LiftType.UNKNOWN:
            logger.error("Could not identify lift type, exiting")
            return
        logger.info("Lift type identified: %s", proxy.lift_type.value)
    except Exception as e:
        logger.error(f"Lift proxy initialization failed: {e}", exc_info=True)
        return

    # Init handlers
    try:
        reporter = DeviceTwinReporter(device_client)
        send_event = EventSender(device_client, proxy.lift_type)
        lift_sim = LiftSimulator(reporter, send_event) if lift_sim_enabled else None
        desired_handler = await DeviceTwinDesiredHandler.create(device_client)
        method_handler = MethodRequestHandler(
            device_client, proxy, reporter, desired_handler)
        heartbeat_handler = HeartbeatHandler(send_event, reporter, desired_handler)
        connection_monitor = ConnectionMonitor(device_client)
        connection_monitor.attach()
    except Exception as e:
        logger.error(f"Handler initialization failed: {e}", exc_info=True)
        return

    # Start BLE server for WiFi onboarding (modern protocol).
    # BLE failure is non-fatal — lift data path must keep running even
    # if the BLE adapter is missing or the SDK fails to load.
    bluetooth_server = None
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
    try:
        await asyncio.gather(*tasks)
    finally:
        if bluetooth_server is not None:
            try:
                await bluetooth_server.stop()
            except Exception:
                logger.exception("Bluetooth server stop failed")


if __name__ == "__main__":
    asyncio.run(main())