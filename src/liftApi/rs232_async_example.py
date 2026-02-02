#!/usr/bin/env python
"""
Example usage of Rs232HandlerAsync for async polling of lift data.

This module demonstrates how to use the Rs232HandlerAsync wrapper to
implement periodic polling of the lift system using asyncio.
"""

import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from liftApi.rs232_handler import Rs232HandlerAsync
from lib.logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def example_single_poll():
    """
    Example 1: Execute a single poll cycle.
    
    This demonstrates how to manually trigger a single poll operation.
    Useful for testing or when you need on-demand polling.
    """
    logger.info("Example 1: Single poll execution")
    
    # Create the async handler
    rs_async = Rs232HandlerAsync()
    
    try:
        # Execute a single poll (poll_type='0' reads one file package)
        response, name, err_code = await rs_async.poll_lift(poll_type='0')
        
        logger.info(f"Poll completed: {name}")
        logger.info(f"Response: {response}")
        logger.info(f"Error code: {err_code}")
        
        return response, err_code
        
    except Exception as e:
        logger.error(f"Error during poll: {e}", exc_info=True)
        return None, "EXCEPTION"


async def example_automatic_polling():
    """
    Example 2: Start automatic polling that runs every 10 seconds.
    
    This demonstrates the automatic polling mode where the system
    continuously polls the lift at regular intervals.
    """
    logger.info("Example 2: Automatic polling every 10 seconds")
    
    # Create the async handler
    rs_async = Rs232HandlerAsync()
    
    try:
        # Start automatic polling (poll_type='0' for incremental file reading)
        await rs_async.start_polling(poll_type='0')
        logger.info("Polling started. Press Ctrl+C to stop...")
        
        # Keep running until interrupted
        # In a real application, this would run until the application shuts down
        while rs_async.is_polling():
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Interrupt received, stopping polling...")
    except Exception as e:
        logger.error(f"Error during polling: {e}", exc_info=True)
    finally:
        # Always stop polling gracefully
        await rs_async.stop_polling()
        logger.info("Polling stopped")


async def example_full_poll_cycle():
    """
    Example 3: Execute a full poll cycle reading all file packages.
    
    This demonstrates poll_type='1' which reads all file packages
    in a single poll cycle.
    """
    logger.info("Example 3: Full poll cycle (all file packages)")
    
    rs_async = Rs232HandlerAsync()
    
    try:
        # Execute a full poll (poll_type='1' reads all file packages)
        response, name, err_code = await rs_async.poll_lift(poll_type='1')
        
        logger.info(f"Full poll completed: {name}")
        logger.info(f"Response: {response}")
        logger.info(f"Error code: {err_code}")
        
        return response, err_code
        
    except Exception as e:
        logger.error(f"Error during full poll: {e}", exc_info=True)
        return None, "EXCEPTION"


async def example_with_custom_interval():
    """
    Example 4: Automatic polling with custom interval.
    
    This shows how to customize the polling interval (default is 10 seconds).
    """
    logger.info("Example 4: Custom polling interval (5 seconds)")
    
    rs_async = Rs232HandlerAsync()
    
    # Customize the polling interval
    rs_async.poll_interval = 5  # 5 seconds instead of default 10
    
    try:
        await rs_async.start_polling(poll_type='0')
        logger.info("Polling started with 5-second interval...")
        
        # Run for 30 seconds
        await asyncio.sleep(30)
        
    except Exception as e:
        logger.error(f"Error during polling: {e}", exc_info=True)
    finally:
        await rs_async.stop_polling()
        logger.info("Polling stopped")


async def example_concurrent_operations():
    """
    Example 5: Multiple concurrent poll requests are handled safely.
    
    This demonstrates that the async wrapper ensures only one poll
    executes at a time, even when multiple requests are made concurrently.
    """
    logger.info("Example 5: Concurrent poll requests (serialized automatically)")
    
    rs_async = Rs232HandlerAsync()
    
    try:
        # Launch multiple polls concurrently
        # They will be automatically serialized by the internal lock
        tasks = [
            rs_async.poll_lift(poll_type='0'),
            rs_async.poll_lift(poll_type='0'),
            rs_async.poll_lift(poll_type='1')
        ]
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        for i, (response, name, err_code) in enumerate(results):
            logger.info(f"Poll {i+1} completed: {err_code}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error during concurrent polls: {e}", exc_info=True)
        return None


async def example_startup_scenario():
    """
    Example 6: Typical startup scenario for a long-running application.
    
    This demonstrates how to integrate the async polling into your
    application's startup sequence.
    """
    logger.info("Example 6: Application startup with automatic polling")
    
    # Create the async handler
    rs_async = Rs232HandlerAsync()
    
    try:
        # 1. Execute an initial poll to get current state
        logger.info("Executing initial poll...")
        response, name, err_code = await rs_async.poll_lift(poll_type='1')
        
        if err_code == rs_async.rs232_handler.rs232Codes.NO_ERR.name:
            logger.info("Initial poll successful, starting automatic polling...")
            
            # 2. Start automatic polling
            await rs_async.start_polling(poll_type='0')
            
            # 3. Application runs here (simulated with sleep)
            logger.info("Application running... (simulating 60 seconds)")
            await asyncio.sleep(60)
            
        else:
            logger.error(f"Initial poll failed: {err_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        return False
    finally:
        # 4. Clean shutdown
        logger.info("Shutting down...")
        await rs_async.stop_polling()
        logger.info("Application stopped")
    
    return True


async def main():
    """
    Main entry point - runs one of the examples.
    
    Uncomment the example you want to run.
    """
    logger.info("Rs232HandlerAsync Usage Examples")
    logger.info("=" * 50)
    
    # Choose which example to run:
    
    # Example 1: Single poll
    # await example_single_poll()
    
    # Example 2: Automatic polling (runs indefinitely)
    # await example_automatic_polling()
    
    # Example 3: Full poll cycle
    # await example_full_poll_cycle()
    
    # Example 4: Custom interval
    # await example_with_custom_interval()
    
    # Example 5: Concurrent operations
    # await example_concurrent_operations()
    
    # Example 6: Startup scenario (recommended)
    await example_startup_scenario()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
