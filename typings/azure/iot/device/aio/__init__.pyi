from typing import Any, Dict
from azure.iot.device import Message, MethodRequest, MethodResponse, RegistrationResult, X509

class IoTHubDeviceClient:
    @classmethod
    def create_from_x509_certificate(
        cls,
        *,
        x509: X509,
        hostname: str,
        device_id: str
    ) -> "IoTHubDeviceClient": ...

    async def connect(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def get_storage_info_for_blob(self, blob_name: str) -> Dict[str, str]: ...
    async def notify_blob_upload_status(
        self,
        correlation_id: str,
        is_success: bool,
        status_code: int,
        status_description: str
    ) -> None: ...
    async def send_message(self, message: Message) -> None: ...
    async def receive_method_request(self) -> MethodRequest: ...
    async def send_method_response(self, response: MethodResponse) -> None: ...
    async def get_twin(self) -> Dict[str, Any]: ...
    async def receive_twin_desired_properties_patch(self) -> Dict[str, Any]: ...
    async def patch_twin_reported_properties(self, reported_properties: Dict[str, Any]) -> None: ...

class ProvisioningDeviceClient:
    # Private pipeline — reached by cloudApi.dps_client._shutdown_pipeline
    # because the SDK has no public shutdown on this client (guard test:
    # utest/test_azure_iot_device_usage.py).
    _pipeline: Any

    def __init__(self, pipeline: Any) -> None: ...

    @classmethod
    def create_from_x509_certificate(
        cls,
        *,
        provisioning_host: str,
        registration_id: str,
        id_scope: str,
        x509: X509
    ) -> "ProvisioningDeviceClient": ...

    async def register(self) -> RegistrationResult: ...
