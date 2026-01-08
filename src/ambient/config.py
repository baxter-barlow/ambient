"""Centralized configuration for ambient SDK.

All configuration can be set via environment variables or config file.
Environment variables take precedence over config file values.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog


@dataclass
class SensorConfig:
    """Sensor connection configuration."""

    cli_port: str = "/dev/ttyUSB0"
    data_port: str = "/dev/ttyUSB1"
    cli_baud: int = 115200
    data_baud: int = 921600
    timeout: float = 1.0
    auto_reconnect: bool = False
    max_reconnect_attempts: int = 3
    reconnect_delay: float = 1.0


@dataclass
class APIConfig:
    """API server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    log_level: str = "INFO"


@dataclass
class PathsConfig:
    """File paths configuration."""

    data_dir: Path = field(default_factory=lambda: Path("data"))
    config_dir: Path = field(default_factory=lambda: Path("configs"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))


@dataclass
class VitalsConfig:
    """Vital signs extraction configuration."""

    sample_rate_hz: float = 20.0
    window_seconds: float = 10.0
    hr_freq_min_hz: float = 0.8
    hr_freq_max_hz: float = 3.0
    rr_freq_min_hz: float = 0.1
    rr_freq_max_hz: float = 0.6
    motion_threshold: float = 0.5


@dataclass
class AppConfig:
    """Complete application configuration."""

    sensor: SensorConfig = field(default_factory=SensorConfig)
    api: APIConfig = field(default_factory=APIConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    vitals: VitalsConfig = field(default_factory=VitalsConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables."""
        config = cls()

        # Sensor config
        config.sensor.cli_port = os.environ.get("AMBIENT_CLI_PORT", config.sensor.cli_port)
        config.sensor.data_port = os.environ.get("AMBIENT_DATA_PORT", config.sensor.data_port)
        config.sensor.auto_reconnect = os.environ.get("AMBIENT_AUTO_RECONNECT", "").lower() == "true"

        # API config
        config.api.host = os.environ.get("AMBIENT_API_HOST", config.api.host)
        config.api.port = int(os.environ.get("AMBIENT_API_PORT", config.api.port))
        config.api.log_level = os.environ.get("AMBIENT_LOG_LEVEL", config.api.log_level)

        # Paths config
        if data_dir := os.environ.get("AMBIENT_DATA_DIR"):
            config.paths.data_dir = Path(data_dir)
        if config_dir := os.environ.get("AMBIENT_CONFIG_DIR"):
            config.paths.config_dir = Path(config_dir)
        if log_dir := os.environ.get("AMBIENT_LOG_DIR"):
            config.paths.log_dir = Path(log_dir)

        return config

    @classmethod
    def from_file(cls, path: str | Path) -> "AppConfig":
        """Load configuration from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """Create config from dictionary."""
        config = cls()

        if "sensor" in data:
            for key, value in data["sensor"].items():
                if hasattr(config.sensor, key):
                    setattr(config.sensor, key, value)

        if "api" in data:
            for key, value in data["api"].items():
                if hasattr(config.api, key):
                    setattr(config.api, key, value)

        if "paths" in data:
            for key, value in data["paths"].items():
                if hasattr(config.paths, key):
                    setattr(config.paths, key, Path(value))

        if "vitals" in data:
            for key, value in data["vitals"].items():
                if hasattr(config.vitals, key):
                    setattr(config.vitals, key, value)

        return config

    def ensure_dirs(self) -> None:
        """Create all configured directories if they don't exist."""
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.log_dir.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config


def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=log_level,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("serial").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
