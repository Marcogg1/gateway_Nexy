import os
import sys
import asyncio
from azure.iot.device import X509
from azure.iot.device.aio import ProvisioningDeviceClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from config import Config

print(f'Invoking __init__.py for {__name__}')
print(f'Conn_str = {Config.CONNECTION_STRING}')

async def register_device():

    try:
        device_client = ProvisioningDeviceClient.create_from_x509_certificate(
            provisioning_host = Config.PROVISIONING_HOST,
            registration_id = Config.DEVICE_NAME,
            id_scope = Config.SCOPE_ID,
            x509=X509(cert_file=Config.TT_CERT, key_file=Config.TT_KEY))
    except:
        print("DPS init failed")

    if not device_client:
        print("Error: Failed to initiate dps client")

    try:
        register_result = await device_client.register()
    except Exception as e:
        print(e)
        print("Registration failed")

    # Values can be "unassigned", "assigning", "assigned", "failed", "disabled"
    print(f"status: {register_result.status}")
    if register_result.status != "assigned":
        print(f"Not assigned: {register_result.status}")

    iot_hub_url = register_result.registration_state.assigned_hub
    device_id = register_result.registration_state.device_id
    print("Register done!")
    print(f"Device ID: {device_id}")
    print(f"IoT hub url: {iot_hub_url}")

asyncio.run(register_device())