from azure.iot.device import MethodResponse
from typing import Optional
from azure.iot.device.custom_typing import JSONSerializable

class MethodRequestHandler:
    def __init__(self, device_client) -> None:
        self.device_client = device_client  

    async def listen_for_method(self, method_request) -> None:
        while True:
            method_request = await self.device_client.receive_method_request()
            print(f"Received method request: {method_request.name}")

            if method_request.name == "la.read.parameter":
                print("la.read.parameter method")
                print(f"Payload: {method_request.payload}")
                response_payload: Optional[JSONSerializable] = {"result": True, "message": "la.read.parameter method executed"}
                status = 200
            else:
                print(f"Unknown method: {method_request.name}")
                response_payload = {"result": False, "message": "Unknown method"}
                status = 404
            # Create a MethodResponse
            method_response = MethodResponse.create_from_method_request(
                method_request, status, response_payload)
            
            await self.device_client.send_method_response(method_response)
            print(f"Sent method response for: {method_request.name}")

