"""Tests for configuration module."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from ambient.config import (
    APIConfig,
    AppConfig,
    PathsConfig,
    SensorConfig,
    VitalsConfig,
    configure_logging,
    get_config,
)


class TestSensorConfig:
    def test_defaults(self):
        config = SensorConfig()
        assert config.cli_port == "/dev/ttyUSB0"
        assert config.data_port == "/dev/ttyUSB1"
        assert config.cli_baud == 115200
        assert config.data_baud == 921600
        assert config.auto_reconnect is False


class TestAPIConfig:
    def test_defaults(self):
        config = APIConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.log_level == "INFO"


class TestPathsConfig:
    def test_defaults(self):
        config = PathsConfig()
        assert config.data_dir == Path("data")
        assert config.config_dir == Path("configs")
        assert config.log_dir == Path("logs")


class TestVitalsConfig:
    def test_defaults(self):
        config = VitalsConfig()
        assert config.sample_rate_hz == 20.0
        assert config.window_seconds == 10.0
        assert config.hr_freq_min_hz == 0.8
        assert config.hr_freq_max_hz == 3.0


class TestAppConfig:
    def test_defaults(self):
        config = AppConfig()
        assert isinstance(config.sensor, SensorConfig)
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.paths, PathsConfig)
        assert isinstance(config.vitals, VitalsConfig)

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("AMBIENT_CLI_PORT", "/dev/ttyACM0")
        monkeypatch.setenv("AMBIENT_API_PORT", "9000")
        monkeypatch.setenv("AMBIENT_LOG_LEVEL", "DEBUG")

        config = AppConfig.from_env()
        assert config.sensor.cli_port == "/dev/ttyACM0"
        assert config.api.port == 9000
        assert config.api.log_level == "DEBUG"

    def test_from_file(self):
        config_data = {
            "sensor": {"cli_port": "/dev/custom0", "auto_reconnect": True},
            "api": {"port": 8888, "log_level": "WARNING"},
            "paths": {"data_dir": "/tmp/ambient"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            f.flush()

            config = AppConfig.from_file(f.name)
            assert config.sensor.cli_port == "/dev/custom0"
            assert config.sensor.auto_reconnect is True
            assert config.api.port == 8888
            assert config.api.log_level == "WARNING"
            assert config.paths.data_dir == Path("/tmp/ambient")

        os.unlink(f.name)

    def test_ensure_dirs(self, tmp_path):
        config = AppConfig()
        config.paths.data_dir = tmp_path / "data"
        config.paths.log_dir = tmp_path / "logs"

        config.ensure_dirs()

        assert config.paths.data_dir.exists()
        assert config.paths.log_dir.exists()


class TestConfigureLogging:
    def test_configure_logging_info(self):
        # Should not raise
        configure_logging("INFO")

    def test_configure_logging_debug(self):
        configure_logging("DEBUG")

    def test_configure_logging_warning(self):
        configure_logging("WARNING")


class TestGetConfig:
    def test_returns_config(self):
        config = get_config()
        assert isinstance(config, AppConfig)

    def test_singleton(self):
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2
