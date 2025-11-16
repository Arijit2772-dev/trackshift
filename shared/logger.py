"""
Logging Utility for Smart File Transfer System
Provides centralized logging configuration and utilities
"""

import logging
import logging.handlers
import sys
from pathlib import Path


class SFTSLogger:
    """Centralized logger for SFTS components"""

    _initialized = False
    _loggers = {}

    @classmethod
    def setup(cls, log_level="INFO", log_file=None, log_format=None, max_size_mb=10, backup_count=3):
        """
        Setup logging configuration (call once at application start)

        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file (None = console only)
            log_format: Log message format string
            max_size_mb: Maximum log file size in MB before rotation
            backup_count: Number of backup log files to keep
        """
        if cls._initialized:
            return

        # Default format if not provided
        if log_format is None:
            log_format = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"

        # Convert string log level to logging constant
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)

        # Create root logger
        root_logger = logging.getLogger("sfts")
        root_logger.setLevel(numeric_level)

        # Remove existing handlers
        root_logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

        # Console handler (always add)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler (if log file specified)
        if log_file:
            try:
                # Create log directory if it doesn't exist
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)

                # Rotating file handler (rotates when file reaches max_size_mb)
                max_bytes = max_size_mb * 1024 * 1024
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
                file_handler.setLevel(numeric_level)
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)

                root_logger.info(f"Logging to file: {log_file}")
            except Exception as e:
                root_logger.warning(f"Could not setup file logging: {e}")

        cls._initialized = True
        root_logger.info(f"Logging initialized at {log_level} level")

    @classmethod
    def get_logger(cls, name):
        """
        Get a logger instance for a specific component

        Args:
            name: Logger name (typically module name or component name)

        Returns:
            Logger instance

        Example:
            >>> logger = SFTSLogger.get_logger("sender")
            >>> logger.info("Starting file transfer")
        """
        if not cls._initialized:
            # Auto-initialize with defaults if not already setup
            cls.setup()

        # Create child logger under sfts namespace
        logger_name = f"sfts.{name}"

        if logger_name not in cls._loggers:
            cls._loggers[logger_name] = logging.getLogger(logger_name)

        return cls._loggers[logger_name]


def setup_logging_from_config(config):
    """
    Setup logging using configuration object

    Args:
        config: Config instance with logging settings
    """
    SFTSLogger.setup(
        log_level=config.log_level,
        log_file=config.log_file,
        log_format=config.log_format,
        max_size_mb=config.get("logging.max_size_mb", 10),
        backup_count=config.get("logging.backup_count", 3)
    )


def get_logger(name):
    """
    Convenience function to get a logger

    Args:
        name: Logger name

    Returns:
        Logger instance

    Example:
        >>> from shared.logger import get_logger
        >>> logger = get_logger("my_component")
        >>> logger.info("Hello!")
    """
    return SFTSLogger.get_logger(name)


if __name__ == "__main__":
    # Test logger
    SFTSLogger.setup(log_level="DEBUG", log_file="test.log")

    logger1 = get_logger("sender")
    logger2 = get_logger("receiver")

    logger1.debug("This is a debug message")
    logger1.info("This is an info message")
    logger1.warning("This is a warning message")
    logger1.error("This is an error message")

    logger2.info("Message from receiver component")

    print("\nCheck test.log file for output!")
