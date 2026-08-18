"""
Logging configuration module for GatewayApp.
Loads logging settings from a YAML configuration file.
"""

import logging
import logging.config
import yaml
import os
from pathlib import Path
from typing import Optional, Union, AnyStr

def setup_logging(
    config_path: Optional[Union[str, os.PathLike[str]]] = None,
    default_level: int = logging.INFO
) -> None:
    """
    Setup logging configuration from a YAML file.
    
    Args:
        config_path: Path to the YAML logging configuration file.
                    If None, looks for 'logging_config.yaml' in the project root.
        default_level: Default logging level if config file is not found.
    
    Raises:
        FileNotFoundError: If the config file is not found and no default is suitable.
    """

    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    if config_path is None:
        # Default to logging_config.yaml in project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "logging_config.yaml"
    
    config_file = Path(config_path)
    
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Rewrite relative handler paths against the created log dir —
            # YAML paths like 'logs/x.log' resolve against CWD, which in the
            # prod image has no logs/ dir and kills all file logging.
            for handler in config.get('handlers', {}).values():
                filename = handler.get('filename')
                if filename and not os.path.isabs(filename):
                    handler['filename'] = os.path.join(
                        log_dir, os.path.basename(filename)
                    )

            # Apply the configuration
            logging.config.dictConfig(config)
            
            logger = logging.getLogger(__name__)
            logger.info(f"Logging configured from {config_file}")
            
        except Exception as e:
            # Fallback to basic configuration
            logging.basicConfig(
                level=default_level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            logger = logging.getLogger(__name__)
            logger.error(
                f"Error loading logging configuration from {config_file}: {e}. "
                "File logging is DISABLED — console-only fallback active."
            )
    else:
        # Fallback to basic configuration
        logging.basicConfig(
            level=default_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        logger.warning(f"Logging config file not found at {config_file}")
        logger.warning("Using basic logging configuration")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: The name of the logger (typically __name__ of the module).
    
    Returns:
        A configured logger instance.
    """
    return logging.getLogger(name)


def set_log_level(logger_name: str, level: int) -> None:
    """
    Dynamically change the log level for a specific logger.
    
    Args:
        logger_name: Name of the logger to modify.
        level: New logging level (e.g., logging.DEBUG, logging.INFO).
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.info(f"Log level for '{logger_name}' changed to {logging.getLevelName(level)}")


def reload_logging_config(config_path: Optional[str] = None) -> None:
    """
    Reload the logging configuration from the YAML file.
    Useful for updating log levels without restarting the application.
    
    Args:
        config_path: Path to the YAML logging configuration file.
    """
    # Close and remove existing handlers to avoid duplicate logs
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)
    
    # Reconfigure logging
    setup_logging(config_path)
