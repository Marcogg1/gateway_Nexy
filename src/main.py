import asyncio
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
from lib.logging_config import setup_logging, get_logger

# Setup logging at module level
setup_logging()
logger = get_logger(__name__)


async def main():
    """
     Main asynchronous function to initialize and run the IoT device client.
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
        proxy = await LiftProxy.create()
        if proxy.lift_type == LiftType.UNKNOWN:
            logger.error("Could not identify lift type, exiting")
            return
        logger.info("Lift type identified: %s", proxy.lift_type.value)
    except Exception as e:
        logger.error(f"Lift proxy initialization failed: {e}", exc_info=True)
        return

    # Init handlers
    try:
        method_handler = MethodRequestHandler(device_client)
        reporter = DeviceTwinReporter(device_client)
        send_event = EventSender(device_client, proxy.lift_type)
        liftSim = LiftSimulator(reporter, send_event) # Init lift simulator, used for testing device twin reporting. Remove when not needed
        desired_handler = await DeviceTwinDesiredHandler.create(device_client)
        heartbeat_handler = HeartbeatHandler(send_event, reporter, desired_handler)
    except Exception as e:
        logger.error(f"Handler initialization failed: {e}", exc_info=True)
        return

    #Run in parallel
    await asyncio.gather(
        method_handler.listen_for_method(),
        desired_handler.listen_for_desired_updates(),
        heartbeat_handler.run(),
        proxy.run(send_event, desired_handler),
        liftSim.report_temperature_loop(), # Start temperature reporting loop testing. Remove when not needed
        liftSim.simulate_lift_operation(), # Simulate lift reporting, add properties. Remove when not needed
        liftSim.send_parameter_data() # Simulate telemetry data sending. Remove when not needed
    )


if __name__ == "__main__":
    asyncio.run(main())