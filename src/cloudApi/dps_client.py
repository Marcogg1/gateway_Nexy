import logging
from azure.iot.device import X509, RegistrationResult
from azure.iot.device.aio import ProvisioningDeviceClient
from config import Config

logger = logging.getLogger(__name__)


class DPSClient:
    """
    Class for handling Device Provisioning Service (DPS) operations.

    Attributes:
        x509 (X509): The X.509 certificate details for device authentication.
    
    Methods:
        create_provisioning_device() -> RegistrationResult:
        
        Asynchronously create and register a provisioning device using X.509 certificates.
    """

    def __init__(self) -> None:
        """
        Initialize the DPSClient with X.509 certificate details.
        
        Args:
            None
        """
        self.x509 = X509(
            cert_file=Config.TT_CERT, 
            key_file=Config.TT_KEY,
            pass_phrase=None
        )

    async def create_provisioning_device(self) -> RegistrationResult:
        """
        Asynchronously create and register a provisioning device using X.509 certificates.

        Args:
            None

        Returns:
            RegistrationResult: The result of the device registration process.
        """
        provisioning_client = ProvisioningDeviceClient.create_from_x509_certificate(
            provisioning_host=Config.PROVISIONING_HOST,
            registration_id=Config.DEVICE_NAME,
            id_scope=Config.SCOPE_ID,
            x509=self.x509
        )

        register_result = await provisioning_client.register()
        if register_result.status == "assigned" and register_result.registration_state:
            logger.info("Device successfully registered.")
            return register_result
        else:
            logger.error(f"Provisioning failed: {register_result.status}")
            raise Exception (f"Provisioning failed: {register_result.status}")
            return None
