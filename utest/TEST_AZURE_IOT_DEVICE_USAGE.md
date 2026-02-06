# Azure IoT Device Usage Unit Tests

This document describes the unit tests in [utest/test_azure_iot_device_usage.py](utest/test_azure_iot_device_usage.py). The tests verify how the app uses Azure IoT SDK APIs, with calls mocked to avoid network or cloud dependencies.

## Test Coverage Overview

- DPS provisioning client registration and result handling
- IoT Hub device client factory creation
- Telemetry event send flow and message properties
- Direct method request handling and response sending
- Device twin desired property retrieval and update loop
- Device twin reported property patching with dot notation
- Blob upload success and failure notification paths

## Test Cases

### TestDPSClient

- **test_create_provisioning_device_assigned**
  - Mocks `ProvisioningDeviceClient.create_from_x509_certificate()` and `register()`.
  - Ensures `DPSClient.create_provisioning_device()` returns the registration result when status is `assigned`.
  - Verifies the provisioning client is created and `register()` is awaited.

### TestDeviceClientFactory

- **test_create_client**
  - Mocks `IoTHubDeviceClient.create_from_x509_certificate()`.
  - Ensures `DeviceClientFactory.create_client()` returns the created client.
  - Verifies the factory calls the SDK constructor exactly once.

### TestEventSender

- **test_send_event_sends_message**
  - Mocks `Message` and `device_client.send_message()`.
  - Ensures payload is JSON-encoded and assigned to `Message`.
  - Verifies the custom property `LIFT_TYPE` is set to `1`.
  - Confirms the message is sent via the device client.

### TestMethodRequestHandler

- **test_listen_for_method_sends_response**
  - Mocks `receive_method_request()` to return a known method request and then stop the loop.
  - Mocks `MethodResponse.create_from_method_request()` and `send_method_response()`.
  - Ensures a response is created and sent for `la.read.parameter`.

### TestDeviceTwinDesiredHandler

- **test_create_populates_desired_properties**
  - Mocks `get_twin()` to return desired properties.
  - Ensures `DeviceTwinDesiredHandler.create()` stores the desired properties.

- **test_listen_for_desired_updates_loops**
  - Mocks `receive_twin_desired_properties_patch()` to return a patch and then stop the loop.
  - Confirms the update loop awaits at least one patch.

### TestDeviceTwinReporter

- **test_report_property_nested_dict**
  - Mocks `patch_twin_reported_properties()`.
  - Ensures dot notation is converted to nested dictionaries.
  - Verifies the reported properties are patched with the expected nested structure.

### TestBlobUploadHandler

- **test_upload_to_blob_success**
  - Mocks `get_storage_info_for_blob()`, `BlobClient.from_blob_url()`, and `upload_blob()`.
  - Ensures success path notifies IoT Hub with status `200` and `OK`.

- **test_upload_to_blob_failure_reports_error**
  - Forces `upload_blob()` to raise an exception.
  - Ensures failure path notifies IoT Hub with status `500` and the error message.

## Running the Tests

From the repo root:

```bash
pytest -q utest/test_azure_iot_device_usage.py
```
