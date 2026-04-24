# CLAUDE.md

## Project Overview

**GatewayApp** is a Python 3.14 gateway application for Aritco lift systems. It merges functionality from three legacy repositories:
- `aritco-gw-cloud-agent` (C++ cloud agent)
- `bluetooth_api` (C++ Bluetooth controller)
- `smartlift2` (Python 3.6 lift agent)

The gateway connects lift equipment to Azure IoT Hub for cloud monitoring and management.

## Commands

```bash
pytest utest/                        # Run all tests (preferred)
pip install -r requirements_host.txt # Dev dependencies
```

CI runs `utils/delivery_check.py -a -x -l -u` via Azure Pipelines.

## Branching

- **Main branch**: `dev` (not `main` or `master`)
- **Feature branches**: `EG-XX-description`

## Design Principles

### Simplicity over abstraction
When implementing features based on old C++/Python 3.6 code:
1. Match the old function signature and return type
2. Use simple, direct implementations - avoid overengineering
3. Return `None` if old code returned `void`
4. Return error code strings if old code used error codes
5. Don't add complex result objects unless necessary

### Error handling pattern
The codebase returns error code name strings (inherited from legacy code):

```python
def validate_input(self, args: list) -> str:
    if invalid:
        return self.ErrorCode.ARGS_IN_LEN_ERR.name
    return self.ErrorCode.NO_ERR.name
```

Each handler has an error enum in `error_signals.py` with a `SOURCE` attribute for cloud error tracking. New async functions return `None` to match the old C++ fire-and-forget pattern.

## Coding Standards

- **Google docstrings** for all functions and classes
- Type hints required: use `str | None` not `Optional[str]`
- All I/O operations use async/await
- Callbacks/hooks invoked from async loops use `async def` even if body is sync — prevents blocking when impl grows I/O
- Tests use `unittest` with `setUp`/`tearDown` (not pytest fixtures)
