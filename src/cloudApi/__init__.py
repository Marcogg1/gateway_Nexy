import os
import sys
import asyncio
from azure.iot.device import X509, MethodResponse, RegistrationResult, MethodRequest
from azure.iot.device.aio import ProvisioningDeviceClient, IoTHubDeviceClient
from typing import Any, Optional
from azure.iot.device.custom_typing import JSONSerializable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from config import Config

print(f'Invoking __init__.py for {__name__}')
print(f'Conn_str = {Config.CONNECTION_STRING}')

iot_device_client: Optional[IoTHubDeviceClient] = None

# Direktmetod-handler
async def method_request_handler(method_request: MethodRequest) -> None:
    global iot_device_client
    print(f"Direct method received: {method_request.name}")
    
    if method_request.name == "test-method":
        print("test method")
        print(f"Payload: {method_request.payload}")
        response_payload: Optional[JSONSerializable]  = {"result": True, "message": "Test method executed"}
        status: int = 200
    elif method_request.name == "reboot":
        print("reboot method")
        print(f"Payload: {method_request.payload}")
        response_payload = {"result": True, "message": "Reboot method executed"}
        status = 200
    elif method_request.name == "la.read.parameter":
        print("la.read.parameter method")
        print(f"Payload: {method_request.payload}")
        response_payload = {"result": True, "message": "la.read.parameter method executed"}
        status = 200    
    else:
        print(f"Unknown method: {method_request.name}")
        response_payload = {"result": False, "message": "Unknown method"}
        status = 404

    method_response: MethodResponse = MethodResponse.create_from_method_request(
        method_request=method_request, status=status, payload=response_payload
    )
    if iot_device_client is not None:
        await iot_device_client.send_method_response(method_response)
    else:
        print("Error: iot_device_client is None, cannot send method response.")


async def register_device() -> None:

    try:
        provisioning_client: ProvisioningDeviceClient = ProvisioningDeviceClient.create_from_x509_certificate(
            provisioning_host = Config.PROVISIONING_HOST,
            registration_id = Config.DEVICE_NAME,
            id_scope = Config.SCOPE_ID,
            x509=X509(cert_file=Config.TT_CERT, key_file=Config.TT_KEY))
    except:
        print("DPS init failed")

    if not provisioning_client:
        print("Error: Failed to initiate dps client")

    try:
        register_result: RegistrationResult  = await provisioning_client.register()
    except Exception as e:
        print(e)
        print("Registration failed")

    # Values can be "unassigned", "assigning", "assigned", "failed", "disabled"
    print(f"status: {register_result.status}")
    if register_result.status == "assigned" and register_result.registration_state:
        print(f"Assigned: {register_result.status}")

        iot_hub_url: str = register_result.registration_state.assigned_hub
        device_id: str = register_result.registration_state.device_id
        print("Register done!")
        print(f"Device ID: {device_id}")
        print(f"IoT hub url: {iot_hub_url}")
    else:
        print(f"Error: {register_result.status}")
        return
        
    try:
        global iot_device_client
        iot_device_client = IoTHubDeviceClient.create_from_x509_certificate(
            x509=X509(cert_file=Config.TT_CERT, key_file=Config.TT_KEY),
            hostname=iot_hub_url,
            device_id=device_id
        )
    except Exception as e:
        print(e)    
        print("IoT Hub init failed")   

    if iot_device_client:
        await iot_device_client.connect()
        print("Device connected to IoT Hub")
        iot_device_client.on_method_request_received = method_request_handler
    else:
        print("Error: iot_device_client is None, cannot connect to IoT Hub")

    while True:
        await asyncio.sleep(10)

asyncio.run(register_device())