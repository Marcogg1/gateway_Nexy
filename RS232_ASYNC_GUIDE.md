# Rs232HandlerAsync - Async Polling Wrapper Documentation

## Overview

`Rs232HandlerAsync` is an asynchronous wrapper around the `Rs232Handler` class that provides periodic polling functionality for the lift system. It implements non-blocking, async-based polling with automatic scheduling and thread-safety guarantees.

## Key Features

- **Asynchronous Polling**: Non-blocking polls using Python's `asyncio` library
- **Automatic Scheduling**: Polls execute every 10 seconds (configurable)
- **Single Thread Guarantee**: Uses `asyncio.Lock` to ensure only one poll executes at a time
- **Graceful Shutdown**: Clean start/stop mechanisms with proper resource cleanup
- **Error Resilience**: Continues polling even if individual polls fail
- **Flexible Poll Types**: Supports both incremental and full file package polling

## Architecture

```
┌─────────────────────────────────┐
│   Rs232HandlerAsync             │
│                                 │
│  ┌─────────────────────────┐   │
│  │  _polling_loop()        │   │  ← Background task
│  │  (runs every 10s)       │   │
│  └─────────────────────────┘   │
│            ↓                    │
│  ┌─────────────────────────┐   │
│  │  poll_lift()            │   │  ← Single poll cycle
│  │  (with asyncio.Lock)    │   │
│  └─────────────────────────┘   │
│            ↓                    │
└──────────│──────────────────────┘
           │
           ↓
┌─────────────────────────────────┐
│   Rs232Handler                  │  ← Original synchronous handler
│   (runs in thread pool)         │
└─────────────────────────────────┘
```

## Usage

### Basic Import

```python
from liftApi.rs232_handler import Rs232HandlerAsync
import asyncio
```

### Example 1: Single Poll Execution

Execute a single poll cycle manually:

```python
async def single_poll_example():
    rs_async = Rs232HandlerAsync()
    
    # Execute one poll (poll_type='0' for incremental file reading)
    response, name, err_code = await rs_async.poll_lift(poll_type='0')
    
    print(f"Poll completed: {err_code}")
    print(f"Response: {response}")
```

### Example 2: Automatic Polling (Recommended)

Start automatic polling that runs every 10 seconds:

```python
async def automatic_polling_example():
    rs_async = Rs232HandlerAsync()
    
    try:
        # Start automatic polling
        await rs_async.start_polling(poll_type='0')
        
        # Your application logic here
        while rs_async.is_polling():
            await asyncio.sleep(1)
            # Do other work...
            
    finally:
        # Always stop polling gracefully
        await rs_async.stop_polling()
```

### Example 3: Application Startup Pattern

Typical pattern for integrating into your application:

```python
async def main():
    rs_async = Rs232HandlerAsync()
    
    try:
        # 1. Execute initial poll to get current state
        response, name, err_code = await rs_async.poll_lift(poll_type='1')
        
        if err_code == "NO_ERR":
            # 2. Start automatic polling
            await rs_async.start_polling(poll_type='0')
            
            # 3. Run your application
            # ... application logic ...
            
    finally:
        # 4. Clean shutdown
        await rs_async.stop_polling()

if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### Class: Rs232HandlerAsync

#### Constructor

```python
Rs232HandlerAsync(rs232_handler: Rs232Handler | None = None)
```

**Parameters:**
- `rs232_handler` (optional): Existing Rs232Handler instance. If None, creates a new one.

**Attributes:**
- `poll_interval`: Polling interval in seconds (default: 10)
- `rs232_handler`: The underlying Rs232Handler instance

#### Methods

##### async poll_lift(poll_type: str = '0') -> tuple[Any, str, str]

Execute a single poll cycle.

**Parameters:**
- `poll_type`: 
  - `'0'`: Read one file package per poll (incremental)
  - `'1'`: Read all file packages in one poll (full)

**Returns:**
- Tuple of `(response, name, error_code)`

**Example:**
```python
response, name, err_code = await rs_async.poll_lift(poll_type='0')
```

**Thread Safety:** This method uses an internal lock to ensure only one poll executes at a time, even when called concurrently.

##### async start_polling(poll_type: str = '0') -> None

Start automatic background polling.

**Parameters:**
- `poll_type`: Same as `poll_lift()`

**Behavior:**
- Creates a background task that polls every `poll_interval` seconds
- If polling is already running, logs a warning and returns
- Non-blocking: returns immediately after starting the background task

**Example:**
```python
await rs_async.start_polling(poll_type='0')
print("Polling is now running in the background")
```

##### async stop_polling() -> None

Stop the automatic polling loop.

**Behavior:**
- Cancels the background polling task
- Waits for any in-progress poll to complete
- Safe to call even if polling is not running

**Example:**
```python
await rs_async.stop_polling()
print("Polling stopped")
```

##### is_polling() -> bool

Check if polling is currently active.

**Returns:**
- `True` if polling is running, `False` otherwise

**Example:**
```python
if rs_async.is_polling():
    print("Polling is active")
```

## Configuration

### Customizing Poll Interval

The default polling interval is 10 seconds. You can customize it:

```python
rs_async = Rs232HandlerAsync()
rs_async.poll_interval = 5  # Poll every 5 seconds

await rs_async.start_polling()
```

### Poll Types Explained

**Poll Type '0' (Incremental):**
- Reads one file package per poll cycle
- Cycles through all file packages over multiple polls
- More efficient for continuous monitoring
- Recommended for automatic polling

**Poll Type '1' (Full):**
- Reads all file packages in a single poll cycle
- More comprehensive but slower
- Recommended for initial state capture or on-demand updates

## Thread Safety

The async wrapper guarantees that **only one poll executes at a time**, even if multiple concurrent requests are made. This is implemented using `asyncio.Lock`:

```python
# These three polls will execute sequentially, not concurrently
tasks = [
    rs_async.poll_lift('0'),
    rs_async.poll_lift('0'),
    rs_async.poll_lift('1')
]
results = await asyncio.gather(*tasks)
```

## Error Handling

### Handling Poll Errors

Individual poll failures don't stop the polling loop:

```python
async def handle_poll_errors():
    rs_async = Rs232HandlerAsync()
    
    response, name, err_code = await rs_async.poll_lift('0')
    
    if err_code != "NO_ERR":
        if err_code == "NO_UPDATED_PARAMS":
            print("No new data to report")
        elif err_code == "PARTIAL_ERR":
            print("Poll completed with some errors")
        else:
            print(f"Poll failed: {err_code}")
```

### Automatic Error Recovery

When using automatic polling, the wrapper continues polling even after errors:

```python
# Even if some polls fail, the loop continues
await rs_async.start_polling()
# Polling will continue automatically despite individual failures
```

## Testing

### Running Unit Tests

The test suite is located in `utest/test_rs232_handler.py`:

```bash
# Install required dependencies
pip install pytest-asyncio

# Run all async tests
pytest utest/test_rs232_handler.py::TestRs232HandlerAsync -v

# Run specific test
pytest utest/test_rs232_handler.py::TestRs232HandlerAsync::test_poll_lift_single_execution -v
```

### Test Coverage

The test suite includes:

1. **test_poll_lift_single_execution**: Verifies single poll execution
2. **test_poll_lift_with_poll_type_1**: Tests full file package polling
3. **test_poll_lift_single_thread_guarantee**: Ensures serial execution
4. **test_start_polling_initiates_background_task**: Validates background polling
5. **test_polling_interval_timing**: Verifies 10-second intervals
6. **test_stop_polling_when_not_running**: Edge case handling
7. **test_start_polling_when_already_running**: Prevents duplicate tasks
8. **test_poll_lift_error_handling**: Error propagation
9. **test_polling_loop_continues_after_error**: Error resilience
10. **test_concurrent_poll_lift_calls_are_serialized**: Thread safety

## Integration with Existing Code

### Migrating from Synchronous to Async

**Before (Synchronous):**
```python
from liftApi.rs232_handler import Rs232Handler

rs_handler = Rs232Handler()
response, name, err_code = rs_handler.poll_lift(['0'])
```

**After (Asynchronous):**
```python
from liftApi.rs232_handler import Rs232HandlerAsync
import asyncio

async def main():
    rs_async = Rs232HandlerAsync()
    response, name, err_code = await rs_async.poll_lift('0')

asyncio.run(main())
```

### Using Existing Rs232Handler Instance

If you already have an Rs232Handler instance:

```python
from liftApi.rs232_handler import Rs232Handler, Rs232HandlerAsync

# Your existing handler
rs_handler = Rs232Handler()

# Wrap it with async functionality
rs_async = Rs232HandlerAsync(rs232_handler=rs_handler)

# Now use async methods
await rs_async.start_polling()
```

## Performance Considerations

1. **Thread Pool Execution**: Synchronous `poll_lift` runs in a thread pool to avoid blocking the event loop
2. **Lock Overhead**: Minimal overhead from asyncio.Lock (microseconds)
3. **Memory**: Each Rs232HandlerAsync instance maintains one background task when polling
4. **CPU**: Polling runs in separate thread pool, doesn't block main async loop

## Troubleshooting

### Issue: Polling doesn't start

**Check:**
```python
# Verify polling started
await rs_async.start_polling()
assert rs_async.is_polling() == True
```

### Issue: Polls taking too long

**Solution:** Check the underlying Rs232Handler configuration:
```python
# Reduce serial timeout if needed
rs_async.rs232_handler.serial_timeout = 0.3  # Default is 0.5
```

### Issue: Too many errors

**Solution:** Use full poll initially:
```python
# Start with full poll to establish baseline
await rs_async.poll_lift(poll_type='1')
# Then use incremental polling
await rs_async.start_polling(poll_type='0')
```

## Best Practices

1. **Always Stop Polling**: Use try/finally to ensure cleanup
   ```python
   try:
       await rs_async.start_polling()
       # ... application code ...
   finally:
       await rs_async.stop_polling()
   ```

2. **Check Poll Status**: Verify polling state before operations
   ```python
   if not rs_async.is_polling():
       await rs_async.start_polling()
   ```

3. **Handle Errors Gracefully**: Don't let poll errors crash your app
   ```python
   response, name, err_code = await rs_async.poll_lift()
   if err_code != "NO_ERR":
       logger.warning(f"Poll error: {err_code}")
       # Continue with degraded functionality
   ```

4. **Use Incremental Polling**: For continuous operation, use poll_type='0'
   ```python
   # More efficient for continuous monitoring
   await rs_async.start_polling(poll_type='0')
   ```

5. **Log Poll Results**: Monitor polling health
   ```python
   response, name, err_code = await rs_async.poll_lift()
   logger.info(f"Poll result: {err_code}, params: {response}")
   ```

## See Also

- Original Rs232Handler class: [src/liftApi/rs232_handler.py](../src/liftApi/rs232_handler.py)
- Usage examples: [src/liftApi/rs232_async_example.py](../src/liftApi/rs232_async_example.py)
- Unit tests: [utest/test_rs232_handler.py](../utest/test_rs232_handler.py)

## Support

For issues or questions:
1. Check the logs for error details
2. Review the test suite for usage patterns
3. Examine rs232_async_example.py for complete examples
