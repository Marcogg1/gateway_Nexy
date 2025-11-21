from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import X509
from config import Config

class DeviceClientFactory:
    """
    Factory class for creating IoTHubDeviceClient instances using DPS registration results.
    
    Args:
        registration_result (RegistrationResult): The result from the DPS registration process.
    
    Methods:
        create_client() -> IoTHubDeviceClient:
    
    Returns:
    """

    def __init__(self, registration_result) -> None:
        """
        Initialize the DeviceClientFactory with the given registration result.
        
        Args:
            registration_result (RegistrationResult): The result from the DPS registration process.
        
        Returns:
            None
        """

        self.registration_result = registration_result

    def create_client(self) -> IoTHubDeviceClient:
        """
        Create an IoTHubDeviceClient instance using the DPS registration result.
        
        Args:
            None
            
        Returns:
            IoTHubDeviceClient: The created IoT Hub device client.
        """
        
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
