import asyncio
from cloudApi.dps_client import DPSClient 
from cloudApi.device_client import DeviceClientFactory
from cloudApi.method_request_handler import MethodRequestHandler
from cloudApi.device_twin_reported import DeviceTwinReporter
from azure.iot.device.aio import IoTHubDeviceClient
from cloudApi.device_twin_desired_handler import DeviceTwinDesiredHandler    
from liftApi.lift_simulator import LiftSimulator


async def main():
    print("Starting main")

    #Provisioning device client
    try:
        dps = DPSClient()
        registration_result = await dps.create_provisioning_device()
    except Exception as e:
        print(f"Provisioning failed: {e}")
        return

    #Create device client
    try:
        factory = DeviceClientFactory(registration_result)  
        device_client = factory.create_client()
        await device_client.connect()
        print("Device connected to IoT Hub")
    except Exception as e:
        print(f"Device client creation/connect failed: {e}")
        return
    
    
    #Init handlers
    try:
        method_handler = MethodRequestHandler(device_client)
        reporter = DeviceTwinReporter(device_client)
        liftSim = LiftSimulator(reporter) # Init lift simulator, used for testing device twin reporting. Remove when not needed
        desired_handler = await DeviceTwinDesiredHandler.create(device_client)   
    except Exception as e:
        print(f"Handler initialization failed: {e}")
        return

    #Run in parallel
    await asyncio.gather(
        method_handler.listen_for_method(),
        desired_handler.listen_for_desired_updates(),
        liftSim.report_temperature_loop(), # Start temperature reporting loop testing. Remove when not needed
        liftSim.simulate_lift_operation() # Simulate lift reporting, add properties. Remove when not needed
    )


if __name__ == "__main__":
    asyncio.run(main())