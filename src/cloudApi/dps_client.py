from azure.iot.device import X509, RegistrationResult
from azure.iot.device.aio import ProvisioningDeviceClient
from config import Config


class DPSClient:
    def __init__(self) -> None:
        self.x509 = X509(
            cert_file=Config.TT_CERT, 
            key_file=Config.TT_KEY,
            pass_phrase=None
        )

    async def create_provisioning_device(self) -> RegistrationResult:
        provisioning_client = ProvisioningDeviceClient.create_from_x509_certificate(
            provisioning_host=Config.PROVISIONING_HOST,
            registration_id=Config.DEVICE_NAME,
            id_scope=Config.SCOPE_ID,
            x509=self.x509
        )

        register_result = await provisioning_client.register()
        if register_result.status == "assigned" and register_result.registration_state:
            print("Device successfully registered.")
            return register_result
        else:
            raise Exception (f"Provisioning failed: {register_result.status}")
            return None
