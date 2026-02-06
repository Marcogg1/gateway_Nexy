from typing import Dict, Optional
from .custom_typing import JSONSerializable

class X509:
    def __init__(self, cert_file: str, key_file: str, pass_phrase: Optional[str]) -> None: ...

class Message:
    custom_properties: Dict[str, str]
    def __init__(self, data: str) -> None: ...

class MethodRequest:
    name: str
    payload: JSONSerializable

class MethodResponse:
    @classmethod
    def create_from_method_request(
        cls,
        method_request: MethodRequest,
        status: int,
        payload: Optional[JSONSerializable]
    ) -> "MethodResponse": ...

class RegistrationState:
    assigned_hub: str
    device_id: str

class RegistrationResult:
    status: str
    registration_state: Optional[RegistrationState]
