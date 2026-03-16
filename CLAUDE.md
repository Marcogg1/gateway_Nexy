# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GatewayApp** is a Python 3.14 gateway application for Aritco lift systems. It merges functionality from three legacy repositories:
- `aritco-gw-cloud-agent` (C++ cloud agent)
- `bluetooth_api` (C++ Bluetooth controller)
- `smartlift2` (Python 3.6 lift agent)

The gateway connects lift equipment to Azure IoT Hub for cloud monitoring and management.

## Development Commands

### Running Tests

**First, install test dependencies:**
```bash
pip install -r requirements_host.txt
```

**Then run tests:**
```bash
# Run all tests (pytest — preferred for async tests)
pytest utest/

# Run all tests (unittest — also works for non-async tests)
python -m unittest discover utest

# Run specific test file
pytest utest/test_method_request_handler.py -v

# Run single test class (unittest style)
python -m unittest utest.test_disk_handler.TestDiskHandler
```

### Running the Application
```bash
# Local development (with virtual environment)
python src/main.py

# Docker build and run
docker build -t gatewayapp .
docker run -p 8080:8080 gatewayapp
```

### Code Quality
```bash
# Type checking (mypy configuration is minimal - currently commented out)
mypy src/

# Linting
pylint src/

# Install dependencies
pip install -r requirements.txt          # Runtime dependencies
pip install -r requirements_host.txt     # Development dependencies
```

### CI Pipeline
The Azure Pipelines CI runs `utils/delivery_check.py` with flags `-a -x -l -u` for automated delivery checks.

## Architecture

### Application Entry Point
`src/main.py` orchestrates the application lifecycle:
1. **Device Provisioning**: Uses DPS (Device Provisioning Service) with X.509 certificates
2. **Device Client Creation**: Establishes Azure IoT Hub connection
3. **Lift Proxy Initialization**: Creates `LiftProxy` which identifies the connected lift type (AHL or 1k) and pairs the correct handler + parameter library
4. **Handler Initialization**: Sets up concurrent async handlers
5. **Parallel Execution**: Runs all handlers using `asyncio.gather()`

### Core Components

**Cloud API (`src/cloudApi/`)**
- `dps_client.py` - Device Provisioning Service client for device registration
- `device_client.py` - Factory for creating IoT Hub device clients with X.509 auth
- `method_request_handler.py` - Handles direct method invocations from cloud (e.g., `la.read.parameter`)
- `device_twin_reported.py` - Reports device properties to IoT Hub device twin
- `device_twin_desired_handler.py` - Listens for desired property updates from cloud
- `blob_upload_handler.py` - Uploads files to Azure Blob Storage via IoT Hub

**Lift API (`src/liftApi/`)**
- `lift_proxy.py` - Single entry point to lift hardware for all consumers (cloud, WiFi, BT). Owns the matched handler + lib pair based on identified lift type.
- `modbus_handler.py` - Modbus RTU communication with AHL lift equipment
- `rs232_handler.py` - RS232 serial communication with 1k lift equipment
- `lift_identifier.py` - Probes handlers to determine connected lift type (AHL or 1k)
- `lift_simulator.py` - Test simulator for development (remove in production)

**File Management (`src/filemgmt/`)**
- `disk_handler.py` - Manages file system access, disk usage monitoring, file status checks

**Library (`src/lib/`)**
- `error_signals.py` - Centralized error code enums for all handlers
- `ahl_lib.py` - Parameter database and definitions for AHL lifts
- `thousand_lib.py` - Parameter database and utility library for 1k lifts
- `sync_time_handler.py` - Time synchronization with lift equipment

### Configuration

**`config.json`** - Defines shared file system paths and gateway configuration:
- File types with paths, filenames, access permissions, and type codes (0x02-0x13)
- Gateway config paths for certificates, WiFi credentials, connection status
- Used by `disk_handler.py` to locate and manage files

**`src/config.py`** - Python configuration constants:
- Azure credentials: `PROVISIONING_HOST`, `DEVICE_NAME`, `SCOPE_ID`
- Certificate paths for X.509 authentication

### Error Handling Pattern

The codebase uses a consistent error handling pattern inherited from the Python 3.6 legacy code:

```python
# Functions return error code name strings
def validate_input(self, args: list) -> str:
    if invalid:
        return self.ErrorCode.ARGS_IN_LEN_ERR.name
    return self.ErrorCode.NO_ERR.name
```

**Each handler has an error enum in `error_signals.py`:**
- `DhCode` - DiskHandler errors
- `Rs232Code` - RS232Handler errors
- `SyncTimeCode` - SyncTimeHandler errors
- Each enum has `SOURCE` attribute for error tracking in cloud

**Note:** New async functions (like `upload_to_blob`) return `None` to match old C++ fire-and-forget pattern. Errors are logged, not returned.

## Coding Standards

### Documentation
- **Google docstrings** for all functions and classes
- Type hints required for all function signatures
- Use modern Python 3.14 type syntax: `str | None` instead of `Optional[str]`

### Async Pattern
All I/O operations use async/await:
```python
async def operation():
    result = await async_call()
    return result

# Run concurrent operations
await asyncio.gather(
    operation1(),
    operation2(),
    operation3()
)
```

### Simplicity Principle
When implementing features based on old C++/Python 3.6 code:
1. Match the old function signature and return type
2. Use simple, direct implementations - avoid overengineering
3. Return `None` if old code returned `void`
4. Return error code strings if old code used error codes
5. Don't add complex result objects unless necessary

### Blob Upload Example
The blob upload implementation demonstrates the migration pattern:
- **Old C++**: `void UploadToBlob(const std::string &name, const std::string &data)`
- **New Python**: `async def upload_to_blob(device_client, blob_name: str, data: bytes) -> None`
- Simple, typed, async, matches old behavior exactly

## Testing

New tests use `pytest` with `pytest-asyncio` (`asyncio_mode = auto` in `pytest.ini`):
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.some_async_method = AsyncMock()
    return client

async def test_something(mock_client):
    # async tests work automatically — no decorator needed
    result = await mock_client.some_async_method()
    assert result is not None
```

Older tests use `unittest` with a manual async wrapper:
```python
def async_test(coro):
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper
```

## Important Context

- **Python Version**: 3.14 (RC1 in Docker)
- **Authentication**: X.509 certificates (`dantest.fullchain.pem`, `dantest.key.pem`)
- **Azure Services**: IoT Hub with Device Provisioning Service (DPS), Blob Storage
- **Development Branch**: Work is typically done on feature branches (e.g., `EG-30-Create-file-upload-from-GW-to-Cloud`)
- **Main Branch**: `dev` (not `main` or `master`)

## File System Paths

Production paths are defined in `config.json` under `/opt/smartlift/`:
- `/opt/smartlift/trace/` - Trace files
- `/opt/smartlift/log/system/` - System logs
- `/opt/smartlift/loggedParams/` - Logged parameters
- `/opt/smartlift/up/` - Upgrade packages

Development uses different paths - check `config.json` for current configuration.
