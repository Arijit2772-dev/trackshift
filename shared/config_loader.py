"""
Configuration Loader for Smart File Transfer System
Loads and provides access to configuration settings from config.yaml
"""

import yaml
import os
from pathlib import Path


class Config:
    """Configuration manager for SFTS"""

    def __init__(self, config_path=None):
        """
        Initialize configuration loader

        Args:
            config_path: Path to config.yaml file. If None, searches parent directories.
        """
        if config_path is None:
            # Search for config.yaml in current directory and parent directories
            config_path = self._find_config_file()

        self.config_path = config_path
        self.config = self._load_config()

    def _find_config_file(self):
        """
        Search for config.yaml starting from current directory up to project root

        Returns:
            Path to config.yaml file
        """
        current = Path.cwd()

        # Search up to 3 levels up
        for _ in range(3):
            config_file = current / "config.yaml"
            if config_file.exists():
                return str(config_file)

            # Check parent directory
            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent

        # If not found, use default path relative to this file
        default_path = Path(__file__).parent.parent / "config.yaml"
        if default_path.exists():
            return str(default_path)

        # If still not found, raise error
        raise FileNotFoundError(
            "config.yaml not found. Please create it in the project root directory."
        )

    def _load_config(self):
        """
        Load configuration from YAML file

        Returns:
            Dictionary containing configuration settings
        """
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing configuration file: {e}")

    def get(self, key_path, default=None):
        """
        Get configuration value using dot notation

        Args:
            key_path: Dot-separated path to config value (e.g., "network.port")
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            >>> config = Config()
            >>> port = config.get("network.port")
            >>> chunk_size = config.get("transfer.chunk_size_mb", default=1)
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    # Convenience properties for commonly used settings

    @property
    def port(self):
        """Get network port"""
        return self.get("network.port", 5001)

    @property
    def receiver_host(self):
        """Get receiver host"""
        return self.get("network.receiver_host", "0.0.0.0")

    @property
    def timeout(self):
        """Get network timeout"""
        timeout = self.get("network.timeout", 30)
        return None if timeout == 0 else timeout

    @property
    def buffer_size(self):
        """Get socket buffer size"""
        return self.get("network.buffer_size", 4096)

    @property
    def chunk_size(self):
        """Get chunk size in bytes"""
        chunk_size_mb = self.get("transfer.chunk_size_mb", 1)
        return chunk_size_mb * 1024 * 1024

    @property
    def max_retries(self):
        """Get maximum retry attempts"""
        return self.get("transfer.max_retries", 3)

    @property
    def enable_resume(self):
        """Check if resume is enabled"""
        return self.get("transfer.enable_resume", True)

    @property
    def state_file(self):
        """Get transfer state file path"""
        return self.get("transfer.state_file", "transfer_state.json")

    @property
    def compression_level(self):
        """Get compression level (0-9)"""
        return self.get("compression.level", 6)

    @property
    def compression_enabled(self):
        """Check if compression is enabled"""
        return self.get("compression.enabled", True)

    @property
    def key_file(self):
        """Get encryption key file path"""
        return self.get("security.key_file", "secret.key")

    @property
    def encryption_enabled(self):
        """Check if encryption is enabled"""
        return self.get("security.enabled", True)

    @property
    def log_level(self):
        """Get logging level"""
        return self.get("logging.level", "INFO")

    @property
    def log_file(self):
        """Get log file path"""
        return self.get("logging.file", "sfts.log")

    @property
    def log_format(self):
        """Get log format string"""
        return self.get("logging.format",
                       "%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    @property
    def priority_enabled(self):
        """Check if priority system is enabled"""
        return self.get("priority.enabled", True)

    @property
    def default_priority(self):
        """Get default priority level"""
        return self.get("priority.default", 3)

    @property
    def priority_levels(self):
        """Get priority level names"""
        return self.get("priority.levels", {1: "CRITICAL", 2: "HIGH", 3: "NORMAL", 4: "LOW"})

    @property
    def show_progress(self):
        """Check if progress display is enabled"""
        return self.get("monitoring.show_progress", True)

    def __repr__(self):
        """String representation"""
        return f"Config(path='{self.config_path}')"


# Global configuration instance
_config_instance = None

def get_config(config_path=None):
    """
    Get global configuration instance (singleton pattern)

    Args:
        config_path: Path to config file (only used on first call)

    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance


if __name__ == "__main__":
    # Test configuration loader
    try:
        config = Config()
        print(f"Configuration loaded from: {config.config_path}")
        print(f"Port: {config.port}")
        print(f"Chunk size: {config.chunk_size} bytes")
        print(f"Max retries: {config.max_retries}")
        print(f"Priority enabled: {config.priority_enabled}")
        print(f"Log level: {config.log_level}")
    except Exception as e:
        print(f"Error: {e}")
