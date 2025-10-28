import asyncio
from cloudApi.dps_client import DPSClient 
from cloudApi.device_client import DeviceClientFactory
from cloudApi.method_request_handler import MethodRequestHandler
from azure.iot.device.aio import IoTHubDeviceClient

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
    except Exception as e:
        print(f"Handler initialization failed: {e}")
        return
    

    #Run in parallel
    await asyncio.gather(
        method_handler.listen_for_method()
    )


if __name__ == "__main__":
    asyncio.run(main())