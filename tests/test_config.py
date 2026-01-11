"""Tests for configuration module."""

import json
import os
import tempfile
from pathlib import Path

from ambient.config import (
	APIConfig,
	AppConfig,
	ChirpModeConfig,
	PathsConfig,
	PerformanceConfig,
	SensorConfig,
	VitalsConfig,
	configure_logging,
	get_config,
)


class TestSensorConfig:
	def test_defaults(self):
		config = SensorConfig()
		# Empty ports trigger auto-detection
		assert config.cli_port == ""
		assert config.data_port == ""
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

	def test_from_file(self, tmp_path):
		test_data_dir = tmp_path / "ambient_data"
		config_data = {
			"sensor": {"cli_port": "/dev/custom0", "auto_reconnect": True},
			"api": {"port": 8888, "log_level": "WARNING"},
			"paths": {"data_dir": str(test_data_dir)},
		}

		config_file = tmp_path / "config.json"
		config_file.write_text(json.dumps(config_data))

		config = AppConfig.from_file(config_file)
		assert config.sensor.cli_port == "/dev/custom0"
		assert config.sensor.auto_reconnect is True
		assert config.api.port == 8888
		assert config.api.log_level == "WARNING"
		assert config.paths.data_dir == test_data_dir

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


class TestChirpModeConfig:
	def test_defaults(self):
		config = ChirpModeConfig()
		assert config.enabled is True
		assert config.target_range_min_m == 0.2
		assert config.target_range_max_m == 5.0
		assert config.target_bins == 5
		assert config.target_threshold == 4
		assert config.output_mode == 5
		assert config.motion_output is True
		assert config.target_info_output is True
		assert config.detection_timeout_s == 0.2

	def test_validation_passes_for_defaults(self):
		config = ChirpModeConfig()
		errors = config.validate()
		assert errors == []

	def test_validation_fails_for_invalid_range_min(self):
		config = ChirpModeConfig(target_range_min_m=0.05)
		errors = config.validate()
		assert any("target_range_min_m" in e for e in errors)

	def test_validation_fails_for_invalid_range_max(self):
		config = ChirpModeConfig(target_range_max_m=15.0)
		errors = config.validate()
		assert any("target_range_max_m" in e for e in errors)

	def test_validation_fails_for_inverted_range(self):
		config = ChirpModeConfig(target_range_min_m=3.0, target_range_max_m=1.0)
		errors = config.validate()
		assert any("must be <" in e for e in errors)

	def test_validation_fails_for_invalid_bins(self):
		config = ChirpModeConfig(target_bins=0)
		errors = config.validate()
		assert any("target_bins" in e for e in errors)

	def test_validation_fails_for_invalid_output_mode(self):
		config = ChirpModeConfig(output_mode=6)
		errors = config.validate()
		assert any("output_mode" in e for e in errors)

	def test_to_commands(self):
		config = ChirpModeConfig(
			target_range_min_m=0.3,
			target_range_max_m=3.0,
			target_bins=4,
			target_threshold=3,
			output_mode=2,
			motion_output=True,
			target_info_output=False,
		)
		commands = config.to_commands()
		assert len(commands) == 2
		assert "chirp target 0.3 3.0 4 3" in commands[0]
		assert "chirp mode 2 1 0" in commands[1]


class TestPerformanceConfig:
	def test_defaults(self):
		config = PerformanceConfig()
		assert config.enabled is False
		assert config.log_interval_frames == 100
		assert config.sample_rate == 1.0


class TestAppConfigValidation:
	def test_default_config_validates(self):
		config = AppConfig()
		errors = config.validate()
		assert errors == []

	def test_validation_fails_for_invalid_sensor_baud(self):
		config = AppConfig()
		config.sensor.cli_baud = 0
		errors = config.validate()
		assert any("cli_baud" in e for e in errors)

	def test_validation_fails_for_invalid_vitals_sample_rate(self):
		config = AppConfig()
		config.vitals.sample_rate_hz = 0
		errors = config.validate()
		assert any("sample_rate_hz" in e for e in errors)

	def test_validation_fails_for_invalid_hr_freq_range(self):
		config = AppConfig()
		config.vitals.hr_freq_min_hz = 3.0
		config.vitals.hr_freq_max_hz = 0.8
		errors = config.validate()
		assert any("hr_freq_min_hz" in e for e in errors)

	def test_validation_fails_for_invalid_rr_freq_range(self):
		config = AppConfig()
		config.vitals.rr_freq_min_hz = 1.0
		config.vitals.rr_freq_max_hz = 0.5
		errors = config.validate()
		assert any("rr_freq_min_hz" in e for e in errors)

	def test_validation_includes_chirp_errors(self):
		config = AppConfig()
		config.chirp.target_range_min_m = 0.01  # Invalid
		errors = config.validate()
		assert any("target_range_min_m" in e for e in errors)

	def test_validation_fails_for_invalid_perf_log_interval(self):
		config = AppConfig()
		config.performance.log_interval_frames = 0
		errors = config.validate()
		assert any("log_interval_frames" in e for e in errors)


class TestAppConfigChirpEnv:
	def test_chirp_enabled_from_env(self, monkeypatch):
		monkeypatch.setenv("AMBIENT_CHIRP_ENABLED", "false")
		config = AppConfig.from_env()
		assert config.chirp.enabled is False

	def test_chirp_range_from_env(self, monkeypatch):
		monkeypatch.setenv("AMBIENT_CHIRP_RANGE_MIN", "0.5")
		monkeypatch.setenv("AMBIENT_CHIRP_RANGE_MAX", "4.0")
		config = AppConfig.from_env()
		assert config.chirp.target_range_min_m == 0.5
		assert config.chirp.target_range_max_m == 4.0

	def test_chirp_output_mode_from_env(self, monkeypatch):
		monkeypatch.setenv("AMBIENT_CHIRP_OUTPUT_MODE", "1")
		config = AppConfig.from_env()
		assert config.chirp.output_mode == 1

	def test_from_file_with_chirp(self):
		config_data = {
			"chirp": {
				"enabled": False,
				"target_range_min_m": 0.3,
				"target_range_max_m": 3.0,
				"output_mode": 2,
			},
		}

		with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
			json.dump(config_data, f)
			f.flush()

			config = AppConfig.from_file(f.name)
			assert config.chirp.enabled is False
			assert config.chirp.target_range_min_m == 0.3
			assert config.chirp.target_range_max_m == 3.0
			assert config.chirp.output_mode == 2

		os.unlink(f.name)


class TestConfigPropagation:
	"""Tests for config propagation to runtime components."""

	def test_streaming_config_uses_app_config(self, monkeypatch):
		"""Verify streaming_config in tasks.py is populated from AppConfig."""
		# Clear cached config
		import ambient.config
		ambient.config._config = None

		# Set env vars before importing tasks
		monkeypatch.setenv("AMBIENT_STREAM_MAX_HEATMAP", "32")
		monkeypatch.setenv("AMBIENT_STREAM_MAX_WAVEFORM", "100")
		monkeypatch.setenv("AMBIENT_STREAM_VITALS_HZ", "2.0")

		# Reimport to pick up new config
		import importlib

		import ambient.api.tasks as tasks_module
		importlib.reload(tasks_module)

		config = tasks_module.streaming_config
		assert config.max_heatmap_size == 32
		assert config.max_waveform_samples == 100
		assert config.vitals_interval_hz == 2.0

		# Cleanup
		ambient.config._config = None
		importlib.reload(tasks_module)

	def test_connection_manager_configure(self):
		"""Verify ConnectionManager.configure updates config values."""
		from ambient.api.ws.manager import ConnectionManager

		manager = ConnectionManager()
		assert manager.config.max_queue_size == 100  # default

		manager.configure(
			max_queue_size=50,
			drop_policy="newest",
			max_payload_kb=25,
		)

		assert manager.config.max_queue_size == 50
		assert manager.config.drop_policy == "newest"
		assert manager.config.max_payload_kb == 25

	def test_streaming_config_from_env_values(self, monkeypatch):
		"""Verify StreamingConfig respects env vars."""
		import ambient.config
		ambient.config._config = None

		monkeypatch.setenv("AMBIENT_STREAM_DROP_POLICY", "none")
		monkeypatch.setenv("AMBIENT_STREAM_INCLUDE_RD", "false")
		monkeypatch.setenv("AMBIENT_STREAM_INCLUDE_WAVEFORMS", "false")

		config = AppConfig.from_env()
		assert config.streaming.drop_policy == "none"
		assert config.streaming.include_range_doppler is False
		assert config.streaming.include_waveforms is False

		ambient.config._config = None
