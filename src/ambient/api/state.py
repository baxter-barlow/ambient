"""Device state machine and global application state."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
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
	from ambient.sensor.radar import RadarSensor
	from ambient.storage.writer import HDF5Writer, ParquetWriter
	from ambient.vitals.extractor import VitalsExtractor

logger = logging.getLogger(__name__)


class DeviceStateMachine:
	"""Manages radar device lifecycle and state transitions."""

	VALID_TRANSITIONS = {
		DeviceState.DISCONNECTED: {DeviceState.CONNECTING},
		DeviceState.CONNECTING: {DeviceState.CONFIGURING, DeviceState.ERROR, DeviceState.DISCONNECTED},
		DeviceState.CONFIGURING: {DeviceState.STREAMING, DeviceState.ERROR, DeviceState.DISCONNECTED},
		DeviceState.STREAMING: {DeviceState.DISCONNECTED, DeviceState.ERROR},
		DeviceState.ERROR: {DeviceState.DISCONNECTED},
	}

	def __init__(self):
		self._state = DeviceState.DISCONNECTED
		self._lock = Lock()
		self._sensor: RadarSensor | None = None
		self._pipeline: ProcessingPipeline | None = None
		self._extractor: VitalsExtractor | None = None
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
	def extractor(self) -> VitalsExtractor | None:
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

	def on_state_change(self, callback: Callable[[DeviceState], None]):
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

	async def connect(self, cli_port: str, data_port: str, config_name: str | None = None) -> bool:
		"""Connect to radar sensor."""
		if not self._transition(DeviceState.CONNECTING):
			return False

		try:
			from ambient.processing.pipeline import ProcessingPipeline
			from ambient.sensor.config import SerialConfig
			from ambient.sensor.radar import RadarSensor
			from ambient.vitals.extractor import VitalsExtractor

			self._cli_port = cli_port
			self._data_port = data_port
			self._config_name = config_name
			self._error = None

			serial_config = SerialConfig(cli_port=cli_port, data_port=data_port)
			self._sensor = RadarSensor(serial_config)
			self._sensor.connect()

			self._pipeline = ProcessingPipeline()
			self._extractor = VitalsExtractor()

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
				from ambient.sensor.config import create_vital_signs_config
				self._sensor.configure(create_vital_signs_config())

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

	def record_frame(self):
		"""Record frame timing for rate calculation."""
		self._frame_count += 1
		self._frame_times.append(time.time())

	def record_drop(self):
		"""Record dropped frame."""
		self._dropped_frames += 1


class RecordingManager:
	"""Manages recording sessions."""

	def __init__(self, data_dir: Path = Path("data")):
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

	def write_frame(self, frame):
		"""Write frame to recording."""
		if self._writer and hasattr(self._writer, "write_frame"):
			self._writer.write_frame(frame)
			self._frame_count += 1

	def write_vitals(self, vitals):
		"""Write vitals to recording."""
		if self._writer:
			self._writer.write_vitals(vitals)


class AppState:
	"""Global application state container."""

	def __init__(self):
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
