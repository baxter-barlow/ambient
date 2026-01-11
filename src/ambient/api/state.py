"""Device state machine and global application state."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from .schemas import (
	AlgorithmParams,
	DeviceState,
	DeviceStatus,
	RecordingStatus,
)

if TYPE_CHECKING:
	from ambient.processing.pipeline import ProcessingPipeline
	from ambient.sensor.frame import RadarFrame
	from ambient.sensor.radar import RadarSensor
	from ambient.storage.writer import HDF5Writer, ParquetWriter
	from ambient.vitals.extractor import ChirpVitalsProcessor, VitalSigns, VitalsExtractor

logger = logging.getLogger(__name__)


# Chirp firmware detection patterns
CHIRP_DETECTION_PATTERNS = [
	r"Chirp Status",
	r"Output mode",
	r"chirp:",
	r"PHASE",
	r"target detection",
]


@dataclass
class ChirpDetectionResult:
	"""Result of chirp firmware detection."""
	is_chirp: bool
	response: str
	matched_pattern: str | None = None
	error: str | None = None


def detect_chirp_firmware(response: str) -> ChirpDetectionResult:
	"""Detect if response indicates chirp firmware.

	Args:
		response: Response string from 'chirp status' command

	Returns:
		ChirpDetectionResult with detection outcome
	"""
	if not response:
		return ChirpDetectionResult(
			is_chirp=False,
			response=response,
			error="Empty response"
		)

	response_lower = response.lower()

	# Check for error responses that indicate standard firmware
	error_patterns = ["error", "unknown command", "invalid", "not found"]
	for pattern in error_patterns:
		if pattern in response_lower:
			return ChirpDetectionResult(
				is_chirp=False,
				response=response,
				error=f"Error response: {pattern}"
			)

	# Check for chirp-specific patterns
	for pattern in CHIRP_DETECTION_PATTERNS:
		if re.search(pattern, response, re.IGNORECASE):
			return ChirpDetectionResult(
				is_chirp=True,
				response=response,
				matched_pattern=pattern
			)

	return ChirpDetectionResult(
		is_chirp=False,
		response=response,
		error="No chirp patterns matched"
	)


class DeviceStateMachine:
	"""Manages radar device lifecycle and state transitions."""

	VALID_TRANSITIONS = {
		DeviceState.DISCONNECTED: {DeviceState.CONNECTING},
		DeviceState.CONNECTING: {DeviceState.CONFIGURING, DeviceState.ERROR, DeviceState.DISCONNECTED},
		DeviceState.CONFIGURING: {DeviceState.STREAMING, DeviceState.ERROR, DeviceState.DISCONNECTED},
		DeviceState.STREAMING: {DeviceState.DISCONNECTED, DeviceState.ERROR},
		DeviceState.ERROR: {DeviceState.DISCONNECTED},
	}

	def __init__(self) -> None:
		self._state = DeviceState.DISCONNECTED
		self._lock = Lock()
		self._sensor: RadarSensor | None = None
		self._pipeline: ProcessingPipeline | None = None
		self._extractor: VitalsExtractor | ChirpVitalsProcessor | None = None
		self._cli_port: str | None = None
		self._data_port: str | None = None
		self._config_name: str | None = None
		self._error: str | None = None
		self._frame_count = 0
		self._dropped_frames = 0
		self._frame_times: deque[float] = deque(maxlen=100)
		self._acquisition_task: asyncio.Task | None = None
		self._stop_event = asyncio.Event()
		self._state_callbacks: list[Callable[[DeviceState], None]] = []

	@property
	def state(self) -> DeviceState:
		return self._state

	@property
	def sensor(self) -> RadarSensor | None:
		return self._sensor

	@property
	def pipeline(self) -> ProcessingPipeline | None:
		return self._pipeline

	@property
	def extractor(self) -> VitalsExtractor | ChirpVitalsProcessor | None:
		return self._extractor

	def _transition(self, new_state: DeviceState) -> bool:
		"""Attempt state transition. Returns True if valid."""
		with self._lock:
			if new_state in self.VALID_TRANSITIONS.get(self._state, set()):
				old_state = self._state
				self._state = new_state
				logger.info(f"State transition: {old_state.value} -> {new_state.value}")
				for cb in self._state_callbacks:
					try:
						cb(new_state)
					except Exception as e:
						logger.error(f"State callback error: {e}")
				return True
			logger.warning(f"Invalid transition: {self._state.value} -> {new_state.value}")
			return False

	def on_state_change(self, callback: Callable[[DeviceState], None]) -> None:
		"""Register callback for state changes."""
		self._state_callbacks.append(callback)

	def get_status(self) -> DeviceStatus:
		"""Get current device status."""
		frame_rate = 0.0
		if len(self._frame_times) >= 2:
			dt = self._frame_times[-1] - self._frame_times[0]
			if dt > 0:
				frame_rate = (len(self._frame_times) - 1) / dt

		return DeviceStatus(
			state=self._state,
			cli_port=self._cli_port,
			data_port=self._data_port,
			frame_rate=round(frame_rate, 1),
			frame_count=self._frame_count,
			dropped_frames=self._dropped_frames,
			buffer_usage=0.0,
			error=self._error,
			config_name=self._config_name,
		)

	async def connect(self, cli_port: str, data_port: str, config_name: str | None = None, chirp_mode: bool = True) -> bool:
		"""Connect to radar sensor.

		Args:
			cli_port: Serial port for CLI
			data_port: Serial port for data
			config_name: Config file name (without .cfg extension)
			chirp_mode: If True, configure chirp firmware for PHASE output
		"""
		if not self._transition(DeviceState.CONNECTING):
			return False

		try:
			from ambient.processing.pipeline import ProcessingPipeline
			from ambient.sensor.config import SerialConfig
			from ambient.sensor.radar import RadarSensor
			from ambient.vitals.extractor import ChirpVitalsProcessor, VitalsExtractor

			self._cli_port = cli_port
			self._data_port = data_port
			self._config_name = config_name
			self._error = None

			serial_config = SerialConfig(cli_port=cli_port, data_port=data_port)
			self._sensor = RadarSensor(serial_config)
			self._sensor.connect()

			self._pipeline = ProcessingPipeline()

			if not self._transition(DeviceState.CONFIGURING):
				raise RuntimeError("Failed to transition to configuring")

			# Load and apply config
			if config_name:
				config_path = Path("configs") / f"{config_name}.cfg"
				if config_path.exists():
					self._sensor.configure(config_path)
				else:
					from ambient.sensor.config import create_vital_signs_config
					self._sensor.configure(create_vital_signs_config())
			else:
				# Default to chirp-compatible config
				config_path = Path("configs") / "vital_signs_chirp.cfg"
				if config_path.exists():
					self._sensor.configure(config_path)
				else:
					from ambient.sensor.config import create_vital_signs_config
					self._sensor.configure(create_vital_signs_config())

			# Configure chirp firmware if enabled
			if chirp_mode:
				from ambient.config import get_config
				chirp_config = get_config().chirp

				if not chirp_config.enabled:
					logger.info("Chirp mode disabled by configuration")
					self._extractor = VitalsExtractor()
				else:
					try:
						# Check if chirp firmware is present
						timeout = chirp_config.detection_timeout_s
						response = self._sensor.send_command("chirp status", timeout=timeout)
						detection = detect_chirp_firmware(response)

						if detection.is_chirp:
							logger.info(
								f"Chirp firmware detected (pattern: {detection.matched_pattern}), "
								"configuring PHASE mode"
							)
							# Apply chirp configuration commands
							for cmd in chirp_config.to_commands():
								self._sensor.send_command(cmd, timeout=timeout)
							# Use ChirpVitalsProcessor for chirp PHASE data
							# Pass vitals config from centralized AppConfig
							from ambient.vitals.extractor import VitalsConfig as ExtractorVitalsConfig
							vitals_cfg = get_config().vitals
							extractor_config = ExtractorVitalsConfig(
								sample_rate_hz=vitals_cfg.sample_rate_hz,
								window_seconds=vitals_cfg.window_seconds,
								hr_freq_min_hz=vitals_cfg.hr_freq_min_hz,
								hr_freq_max_hz=vitals_cfg.hr_freq_max_hz,
								rr_freq_min_hz=vitals_cfg.rr_freq_min_hz,
								rr_freq_max_hz=vitals_cfg.rr_freq_max_hz,
								motion_threshold=vitals_cfg.motion_threshold,
							)
							self._extractor = ChirpVitalsProcessor(config=extractor_config)
						else:
							reason = detection.error or "no chirp patterns matched"
							logger.info(f"Standard firmware detected ({reason})")
							self._extractor = VitalsExtractor()
					except Exception as e:
						logger.warning(f"Chirp detection failed, using standard mode: {e}")
						self._extractor = VitalsExtractor()
			else:
				self._extractor = VitalsExtractor()

			self._sensor.start()

			if not self._transition(DeviceState.STREAMING):
				raise RuntimeError("Failed to transition to streaming")

			self._frame_count = 0
			self._dropped_frames = 0
			self._frame_times.clear()
			return True

		except Exception as e:
			logger.error(f"Connect failed: {e}")
			self._error = str(e)
			self._transition(DeviceState.ERROR)
			return False

	async def disconnect(self) -> bool:
		"""Disconnect from radar sensor."""
		if self._state == DeviceState.DISCONNECTED:
			return True

		self._stop_event.set()
		if self._acquisition_task:
			self._acquisition_task.cancel()
			try:
				await self._acquisition_task
			except asyncio.CancelledError:
				pass
			self._acquisition_task = None

		if self._sensor:
			try:
				self._sensor.stop()
				self._sensor.disconnect()
			except Exception as e:
				logger.error(f"Disconnect error: {e}")
			self._sensor = None

		self._pipeline = None
		self._extractor = None
		self._transition(DeviceState.DISCONNECTED)
		self._stop_event.clear()
		return True

	async def emergency_stop(self) -> bool:
		"""Emergency stop - immediately halt acquisition."""
		logger.warning("Emergency stop triggered")
		return await self.disconnect()

	def record_frame(self) -> None:
		"""Record frame timing for rate calculation."""
		self._frame_count += 1
		self._frame_times.append(time.time())

	def record_drop(self) -> None:
		"""Record dropped frame."""
		self._dropped_frames += 1


class RecordingManager:
	"""Manages recording sessions."""

	def __init__(self, data_dir: Path = Path("data")) -> None:
		self.data_dir = data_dir
		self.data_dir.mkdir(exist_ok=True)
		self._writer: HDF5Writer | ParquetWriter | None = None
		self._recording_id: str | None = None
		self._recording_name: str | None = None
		self._recording_start: float | None = None
		self._frame_count = 0

	@property
	def is_recording(self) -> bool:
		return self._writer is not None

	def get_status(self) -> RecordingStatus:
		duration = 0.0
		if self._recording_start:
			duration = time.time() - self._recording_start
		return RecordingStatus(
			is_recording=self.is_recording,
			recording_id=self._recording_id,
			name=self._recording_name,
			duration=duration,
			frame_count=self._frame_count,
		)

	def start(self, name: str, format: str = "h5") -> str:
		"""Start recording. Returns recording ID."""
		if self.is_recording:
			raise RuntimeError("Already recording")

		from ambient.storage.writer import HDF5Writer, ParquetWriter

		self._recording_id = f"{int(time.time())}_{name}"
		self._recording_name = name
		self._recording_start = time.time()
		self._frame_count = 0

		if format == "h5":
			path = self.data_dir / f"{self._recording_id}.h5"
			from ambient.storage.writer import SessionMetadata
			self._writer = HDF5Writer(path, metadata=SessionMetadata(session_id=self._recording_id))
		else:
			path = self.data_dir / f"{self._recording_id}.parquet"
			self._writer = ParquetWriter(path)

		return self._recording_id

	def stop(self) -> str | None:
		"""Stop recording. Returns recording ID."""
		if not self.is_recording:
			return None

		recording_id = self._recording_id
		if self._writer:
			self._writer.close()
		self._writer = None
		self._recording_id = None
		self._recording_name = None
		self._recording_start = None
		return recording_id

	def write_frame(self, frame: "RadarFrame") -> None:
		"""Write frame to recording."""
		if self._writer and hasattr(self._writer, "write_frame"):
			self._writer.write_frame(frame)
			self._frame_count += 1

	def write_vitals(self, vitals: "VitalSigns") -> None:
		"""Write vitals to recording."""
		if self._writer:
			self._writer.write_vitals(vitals)


class AppState:
	"""Global application state container."""

	def __init__(self) -> None:
		self.device = DeviceStateMachine()
		self.recording = RecordingManager()
		self.algorithm_params = AlgorithmParams()
		self.log_buffer: deque[dict] = deque(maxlen=1000)


# Global singleton
_app_state: AppState | None = None


def get_app_state() -> AppState:
	global _app_state
	if _app_state is None:
		_app_state = AppState()
	return _app_state
