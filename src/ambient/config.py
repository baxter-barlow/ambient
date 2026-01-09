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
class PerformanceConfig:
	"""Performance profiling configuration."""

	enabled: bool = False  # Enable performance instrumentation
	log_interval_frames: int = 100  # Log stats every N frames
	sample_rate: float = 1.0  # Sample rate for profiling (1.0 = every frame)


@dataclass
class StreamingConfig:
	"""WebSocket streaming and broadcast configuration."""

	max_queue_size: int = 100  # Max messages in queue before dropping
	drop_policy: str = "oldest"  # oldest, newest, or none
	max_heatmap_size: int = 64  # Max rows/cols for range_doppler
	max_waveform_samples: int = 200  # Max samples for waveforms
	max_phase_signal_samples: int = 200  # Max samples for phase_signal
	vitals_interval_hz: float = 1.0  # Vitals broadcast rate
	include_range_doppler: bool = True  # Include range_doppler in frames
	include_waveforms: bool = True  # Include waveforms in vitals
	max_payload_kb: int = 50  # Warn if payload exceeds this

	def validate(self) -> list[str]:
		"""Validate configuration values. Returns list of error messages."""
		errors = []

		if self.max_queue_size < 1 or self.max_queue_size > 10000:
			errors.append(f"max_queue_size ({self.max_queue_size}) must be between 1 and 10000")
		if self.drop_policy not in ("oldest", "newest", "none"):
			errors.append(f"drop_policy ({self.drop_policy}) must be 'oldest', 'newest', or 'none'")
		if self.max_heatmap_size < 8 or self.max_heatmap_size > 256:
			errors.append(f"max_heatmap_size ({self.max_heatmap_size}) must be between 8 and 256")
		if self.max_waveform_samples < 10 or self.max_waveform_samples > 1000:
			errors.append(f"max_waveform_samples ({self.max_waveform_samples}) must be between 10 and 1000")
		if self.vitals_interval_hz < 0.1 or self.vitals_interval_hz > 10.0:
			errors.append(f"vitals_interval_hz ({self.vitals_interval_hz}) must be between 0.1 and 10.0")
		if self.max_payload_kb < 1 or self.max_payload_kb > 1000:
			errors.append(f"max_payload_kb ({self.max_payload_kb}) must be between 1 and 1000")

		return errors


@dataclass
class ChirpModeConfig:
	"""Chirp firmware mode configuration."""

	enabled: bool = True  # Auto-detect and enable chirp mode
	target_range_min_m: float = 0.2  # Minimum detection range
	target_range_max_m: float = 5.0  # Maximum detection range
	target_bins: int = 5  # Number of range bins to track
	target_threshold: int = 4  # Detection threshold
	output_mode: int = 5  # 3=PHASE, 5=PHASE_IQ (phase + I/Q range profile)
	motion_output: bool = True  # Include motion detection
	target_info_output: bool = True  # Include target info
	detection_timeout_s: float = 0.2  # Timeout for chirp detection command

	def validate(self) -> list[str]:
		"""Validate configuration values. Returns list of error messages."""
		errors = []

		if self.target_range_min_m < 0.1:
			errors.append(f"target_range_min_m ({self.target_range_min_m}) must be >= 0.1")
		if self.target_range_max_m > 10.0:
			errors.append(f"target_range_max_m ({self.target_range_max_m}) must be <= 10.0")
		if self.target_range_min_m >= self.target_range_max_m:
			errors.append(
				f"target_range_min_m ({self.target_range_min_m}) must be < "
				f"target_range_max_m ({self.target_range_max_m})"
			)
		if self.target_bins < 1 or self.target_bins > 20:
			errors.append(f"target_bins ({self.target_bins}) must be between 1 and 20")
		if self.target_threshold < 1 or self.target_threshold > 10:
			errors.append(f"target_threshold ({self.target_threshold}) must be between 1 and 10")
		if self.output_mode not in (1, 2, 3, 5):
			errors.append(f"output_mode ({self.output_mode}) must be 1, 2, 3, or 5")
		if self.detection_timeout_s < 0.05 or self.detection_timeout_s > 2.0:
			errors.append(f"detection_timeout_s ({self.detection_timeout_s}) must be between 0.05 and 2.0")

		return errors

	def to_commands(self) -> list[str]:
		"""Generate chirp CLI commands from this configuration."""
		commands = [
			f"chirp target {self.target_range_min_m} {self.target_range_max_m} "
			f"{self.target_bins} {self.target_threshold}",
			f"chirp mode {self.output_mode} {1 if self.motion_output else 0} "
			f"{1 if self.target_info_output else 0}",
		]
		return commands


@dataclass
class AppConfig:
	"""Complete application configuration."""

	sensor: SensorConfig = field(default_factory=SensorConfig)
	api: APIConfig = field(default_factory=APIConfig)
	paths: PathsConfig = field(default_factory=PathsConfig)
	vitals: VitalsConfig = field(default_factory=VitalsConfig)
	performance: PerformanceConfig = field(default_factory=PerformanceConfig)
	chirp: ChirpModeConfig = field(default_factory=ChirpModeConfig)
	streaming: StreamingConfig = field(default_factory=StreamingConfig)

	@classmethod
	def from_env(cls) -> AppConfig:
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

		# Performance config
		config.performance.enabled = os.environ.get("AMBIENT_PERF_ENABLED", "").lower() == "true"
		if log_interval := os.environ.get("AMBIENT_PERF_LOG_INTERVAL"):
			config.performance.log_interval_frames = int(log_interval)

		# Chirp mode config
		chirp_enabled = os.environ.get("AMBIENT_CHIRP_ENABLED", "").lower()
		if chirp_enabled:
			config.chirp.enabled = chirp_enabled == "true"
		if range_min := os.environ.get("AMBIENT_CHIRP_RANGE_MIN"):
			config.chirp.target_range_min_m = float(range_min)
		if range_max := os.environ.get("AMBIENT_CHIRP_RANGE_MAX"):
			config.chirp.target_range_max_m = float(range_max)
		if output_mode := os.environ.get("AMBIENT_CHIRP_OUTPUT_MODE"):
			config.chirp.output_mode = int(output_mode)

		# Streaming config
		if max_queue := os.environ.get("AMBIENT_STREAM_MAX_QUEUE"):
			config.streaming.max_queue_size = int(max_queue)
		if drop_policy := os.environ.get("AMBIENT_STREAM_DROP_POLICY"):
			config.streaming.drop_policy = drop_policy
		if max_heatmap := os.environ.get("AMBIENT_STREAM_MAX_HEATMAP"):
			config.streaming.max_heatmap_size = int(max_heatmap)
		if max_waveform := os.environ.get("AMBIENT_STREAM_MAX_WAVEFORM"):
			config.streaming.max_waveform_samples = int(max_waveform)
		if vitals_hz := os.environ.get("AMBIENT_STREAM_VITALS_HZ"):
			config.streaming.vitals_interval_hz = float(vitals_hz)
		include_rd = os.environ.get("AMBIENT_STREAM_INCLUDE_RD", "").lower()
		if include_rd:
			config.streaming.include_range_doppler = include_rd == "true"
		include_wf = os.environ.get("AMBIENT_STREAM_INCLUDE_WAVEFORMS", "").lower()
		if include_wf:
			config.streaming.include_waveforms = include_wf == "true"

		return config

	@classmethod
	def from_file(cls, path: str | Path) -> AppConfig:
		"""Load configuration from JSON file."""
		with open(path) as f:
			data = json.load(f)
		return cls._from_dict(data)

	@classmethod
	def _from_dict(cls, data: dict[str, Any]) -> AppConfig:
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

		if "chirp" in data:
			for key, value in data["chirp"].items():
				if hasattr(config.chirp, key):
					setattr(config.chirp, key, value)

		if "performance" in data:
			for key, value in data["performance"].items():
				if hasattr(config.performance, key):
					setattr(config.performance, key, value)

		if "streaming" in data:
			for key, value in data["streaming"].items():
				if hasattr(config.streaming, key):
					setattr(config.streaming, key, value)

		return config

	def ensure_dirs(self) -> None:
		"""Create all configured directories if they don't exist."""
		self.paths.data_dir.mkdir(parents=True, exist_ok=True)
		self.paths.log_dir.mkdir(parents=True, exist_ok=True)

	def validate(self) -> list[str]:
		"""Validate all configuration values. Returns list of error messages."""
		errors = []

		# Validate sensor config
		if self.sensor.cli_baud <= 0:
			errors.append(f"sensor.cli_baud ({self.sensor.cli_baud}) must be positive")
		if self.sensor.data_baud <= 0:
			errors.append(f"sensor.data_baud ({self.sensor.data_baud}) must be positive")
		if self.sensor.timeout <= 0:
			errors.append(f"sensor.timeout ({self.sensor.timeout}) must be positive")

		# Validate vitals config
		if self.vitals.sample_rate_hz <= 0:
			errors.append(f"vitals.sample_rate_hz ({self.vitals.sample_rate_hz}) must be positive")
		if self.vitals.window_seconds <= 0:
			errors.append(f"vitals.window_seconds ({self.vitals.window_seconds}) must be positive")
		if self.vitals.hr_freq_min_hz >= self.vitals.hr_freq_max_hz:
			errors.append(
				f"vitals.hr_freq_min_hz ({self.vitals.hr_freq_min_hz}) must be < "
				f"hr_freq_max_hz ({self.vitals.hr_freq_max_hz})"
			)
		if self.vitals.rr_freq_min_hz >= self.vitals.rr_freq_max_hz:
			errors.append(
				f"vitals.rr_freq_min_hz ({self.vitals.rr_freq_min_hz}) must be < "
				f"rr_freq_max_hz ({self.vitals.rr_freq_max_hz})"
			)

		# Validate chirp config
		errors.extend(self.chirp.validate())

		# Validate streaming config
		errors.extend(self.streaming.validate())

		# Validate performance config
		if self.performance.log_interval_frames < 1:
			errors.append(
				f"performance.log_interval_frames ({self.performance.log_interval_frames}) must be >= 1"
			)

		return errors


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
