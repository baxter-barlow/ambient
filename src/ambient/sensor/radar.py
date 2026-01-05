"""Radar sensor interface for IWR6843AOPEVM."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Thread, Event
from typing import Callable, Iterator

import serial
import serial.tools.list_ports

from .config import ChirpConfig, SerialConfig, load_config_file, create_vital_signs_config
from .frame import FrameBuffer, RadarFrame

logger = logging.getLogger(__name__)


class RadarSensor:
	"""Interface for IWR6843AOPEVM mmWave radar.

	Handles serial communication, configuration, and frame streaming.
	Use as context manager for automatic cleanup.
	"""

	def __init__(self, config: SerialConfig | None = None):
		self._config = config or SerialConfig()
		self._cli: serial.Serial | None = None
		self._data: serial.Serial | None = None
		self._buffer = FrameBuffer()
		self._running = False
		self._stream_thread: Thread | None = None
		self._stop_event = Event()
		self._callbacks: list[Callable[[RadarFrame], None]] = []

	@property
	def is_connected(self) -> bool:
		return self._cli is not None and self._cli.is_open

	@property
	def is_running(self) -> bool:
		return self._running

	@staticmethod
	def find_ports() -> dict[str, str]:
		"""Find radar serial ports. Returns {'cli': ..., 'data': ...}."""
		ports = list(serial.tools.list_ports.comports())

		# Look for XDS or ACM devices (TI evaluation boards)
		ti_ports = [p for p in ports if "XDS" in (p.description or "") or "ACM" in p.device]
		if len(ti_ports) >= 2:
			ti_ports.sort(key=lambda p: p.device)
			return {"cli": ti_ports[0].device, "data": ti_ports[1].device}

		# Fallback to ttyUSB devices
		usb_ports = [p for p in ports if "ttyUSB" in p.device]
		if len(usb_ports) >= 2:
			usb_ports.sort(key=lambda p: p.device)
			return {"cli": usb_ports[0].device, "data": usb_ports[1].device}

		return {}

	def connect(self):
		"""Open serial connections to the radar."""
		if self.is_connected:
			return

		# Auto-detect ports if not specified
		cli_port = self._config.cli_port
		data_port = self._config.data_port

		if not cli_port or not data_port or cli_port == data_port:
			ports = self.find_ports()
			if not ports:
				raise RuntimeError(
					"Could not find radar ports. Check:\n"
					"  1. USB cable is connected\n"
					"  2. User is in 'dialout' group\n"
					"  3. Device is powered on"
				)
			cli_port = ports["cli"]
			data_port = ports["data"]

		logger.info(f"Connecting: CLI={cli_port}, Data={data_port}")

		self._cli = serial.Serial(cli_port, self._config.cli_baud, timeout=self._config.timeout)
		self._data = serial.Serial(data_port, self._config.data_baud, timeout=0.1)

		time.sleep(0.1)
		self._flush()

	def disconnect(self):
		"""Close serial connections."""
		self.stop()
		if self._cli and self._cli.is_open:
			self._cli.close()
		if self._data and self._data.is_open:
			self._data.close()
		self._cli = None
		self._data = None
		logger.info("Disconnected")

	def _flush(self):
		if self._cli:
			self._cli.reset_input_buffer()
			self._cli.reset_output_buffer()
		if self._data:
			self._data.reset_input_buffer()

	def send_command(self, cmd: str, timeout: float = 0.1) -> str:
		"""Send a CLI command and return response."""
		if not self._cli:
			raise RuntimeError("Not connected")

		self._cli.reset_input_buffer()
		self._cli.write(f"{cmd}\n".encode())
		time.sleep(timeout)

		return self._cli.read(self._cli.in_waiting).decode("utf-8", errors="ignore")

	def configure(self, config: str | Path | ChirpConfig | list[str]):
		"""Send configuration to the radar."""
		if isinstance(config, ChirpConfig):
			commands = config.to_commands()
		elif isinstance(config, list):
			commands = config
		elif isinstance(config, (str, Path)):
			commands = load_config_file(config)
		else:
			raise TypeError(f"Invalid config type: {type(config)}")

		logger.info(f"Sending {len(commands)} configuration commands")

		for cmd in commands:
			response = self.send_command(cmd)
			if "Error" in response:
				logger.error(f"Config error: {cmd} -> {response}")
			time.sleep(0.02)

	def start(self):
		"""Start the sensor (send sensorStart command)."""
		if not self.is_connected:
			raise RuntimeError("Not connected")
		self.send_command("sensorStart")
		self._running = True
		self._buffer.clear()
		logger.info("Sensor started")

	def stop(self):
		"""Stop the sensor."""
		self._running = False
		self._stop_event.set()

		if self._stream_thread and self._stream_thread.is_alive():
			self._stream_thread.join(timeout=2.0)
		self._stream_thread = None
		self._stop_event.clear()

		if self.is_connected:
			try:
				self.send_command("sensorStop")
			except Exception:
				pass
		logger.info("Sensor stopped")

	def read_frame(self, timeout: float = 1.0) -> RadarFrame | None:
		"""Read a single frame. Returns None if no frame available."""
		if not self._data:
			return None

		start = time.time()
		while time.time() - start < timeout:
			available = self._data.in_waiting
			if available:
				self._buffer.append(self._data.read(available))

			frame = self._buffer.extract_frame()
			if frame:
				return frame

			time.sleep(0.005)

		return None

	def stream(
		self, max_frames: int | None = None, duration: float | None = None
	) -> Iterator[RadarFrame]:
		"""Generator that yields frames."""
		if not self.is_connected:
			raise RuntimeError("Not connected")

		start = time.time()
		count = 0

		while self._running:
			frame = self.read_frame(timeout=0.1)
			if frame:
				yield frame
				count += 1

				if max_frames and count >= max_frames:
					break

			if duration and (time.time() - start) >= duration:
				break

	def stream_async(
		self,
		callback: Callable[[RadarFrame], None],
		max_frames: int | None = None,
	):
		"""Start streaming in a background thread."""
		if self._stream_thread and self._stream_thread.is_alive():
			raise RuntimeError("Already streaming")

		self._callbacks = [callback] if callback else []
		self._stop_event.clear()

		def run():
			count = 0
			while not self._stop_event.is_set() and self._running:
				frame = self.read_frame(timeout=0.1)
				if frame:
					for cb in self._callbacks:
						try:
							cb(frame)
						except Exception as e:
							logger.error(f"Callback error: {e}")

					count += 1
					if max_frames and count >= max_frames:
						break

		self._stream_thread = Thread(target=run, daemon=True)
		self._stream_thread.start()

	def get_version(self) -> str:
		"""Query sensor firmware version."""
		return self.send_command("version", timeout=0.3)

	def query_status(self) -> str:
		"""Query sensor status."""
		return self.send_command("sensorStop", timeout=0.2)

	def __enter__(self):
		self.connect()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.stop()
		self.disconnect()
