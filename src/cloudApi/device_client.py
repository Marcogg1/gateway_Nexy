from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import X509
from config import Config

class DeviceClientFactory:
    def __init__(self, registration_result) -> None:
        self.registration_result = registration_result

    def create_client(self) -> IoTHubDeviceClient:
        x509 = X509(
            cert_file=Config.TT_CERT, 
            key_file=Config.TT_KEY,
            pass_phrase=None
        )
        return IoTHubDeviceClient.create_from_x509_certificate(
            x509=x509,
            hostname=self.registration_result.registration_state.assigned_hub,
            device_id=self.registration_result.registration_state.device_id
        )    
