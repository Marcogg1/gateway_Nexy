# YAML-Based Logging System

## Overview
The GatewayApp now includes a flexible logging system configured via YAML. This allows you to adjust log levels, formats, and outputs without modifying code.

## Files Created

### 1. `logging_config.yaml`
Main configuration file in the project root. Contains:
- **Formatters**: default, detailed, and simple formats
- **Handlers**: 
  - `console`: stdout with DEBUG level
  - `file`: rotating file handler (logs/gateway_app.log, 10MB max, 5 backups)
  - `error_file`: error-only logs (logs/gateway_errors.log, 10MB max, 3 backups)
- **Loggers**: Per-module loggers (cloudApi, liftApi, filemgmt, lib)
- **Root logger**: INFO level by default

### 2. `src/lib/logging_config.py`
Logging setup module providing:
- `setup_logging()`: Initialize logging from YAML
- `get_logger(name)`: Get a named logger
- `set_log_level(logger_name, level)`: Dynamically change log levels
- `reload_logging_config()`: Reload config without restart

### 3. Updated `src/main.py`
Integrated logging with:
- `logger.info()` for informational messages
- `logger.error()` with `exc_info=True` for exceptions

## Usage

### Basic Usage
```python
from lib.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

### Adjusting Log Levels in YAML

Edit `logging_config.yaml`:

```yaml
# Set a specific module to DEBUG
loggers:
  cloudApi:
    level: DEBUG  # Changed from INFO
```

### Dynamic Log Level Changes

```python
from lib.logging_config import set_log_level
import logging

# Change cloudApi to DEBUG at runtime
set_log_level('cloudApi', logging.DEBUG)
```

### Reload Configuration

```python
from lib.logging_config import reload_logging_config

# Reload after modifying logging_config.yaml
reload_logging_config()
```

## Configuration Options

### Log Levels (from least to most verbose)
- CRITICAL (50)
- ERROR (40)
- WARNING (30)
- INFO (20)
- DEBUG (10)
- NOTSET (0)

### Example: Enable Debug for Specific Module

```yaml
loggers:
  cloudApi:
    level: DEBUG
    handlers: [console, file, error_file]
    propagate: no
```

### Example: Console-Only Logging

```yaml
root:
  level: INFO
  handlers: [console]  # Remove file handlers
```

## Dependencies

Added `pyyaml` to `requirements.txt` - install with:
```bash
pip install -r requirements.txt
```
