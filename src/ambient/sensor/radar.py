"""Radar sensor interface for TI IWR6843AOPEVM."""

from __future__ import annotations

import glob
import threading
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path

import serial
import structlog

from ambient.sensor.config import ChirpConfig, load_config
from ambient.sensor.frame import FrameBuffer, RadarFrame

logger = structlog.get_logger(__name__)


@dataclass
class SerialConfig:
	cli_port: str = "/dev/ttyUSB0"
	data_port: str = "/dev/ttyUSB1"
	cli_baudrate: int = 115200
	data_baudrate: int = 921600
	timeout: float = 1.0


class RadarSensor:
	"""Interface for IWR6843AOPEVM mmWave radar.

	Handles serial communication, configuration, and frame streaming.
	Use as context manager for automatic cleanup.
	"""

	def __init__(
		self,
		cli_port: str = "/dev/ttyUSB0",
		data_port: str = "/dev/ttyUSB1",
		cli_baudrate: int = 115200,
		data_baudrate: int = 921600,
	) -> None:
		self._config = SerialConfig(
			cli_port=cli_port,
			data_port=data_port,
			cli_baudrate=cli_baudrate,
			data_baudrate=data_baudrate,
		)
		self._cli_serial: serial.Serial | None = None
		self._data_serial: serial.Serial | None = None
		self._frame_buffer = FrameBuffer()
		self._is_running = False
		self._streaming = False
		self._read_thread: threading.Thread | None = None
		self._frame_callbacks: list[Callable[[RadarFrame], None]] = []

		logger.info("sensor_init", cli_port=cli_port, data_port=data_port)

	def connect(self) -> None:
		"""Open serial connections."""
		try:
			self._cli_serial = serial.Serial(
				self._config.cli_port,
				self._config.cli_baudrate,
				timeout=self._config.timeout,
			)
			self._data_serial = serial.Serial(
				self._config.data_port,
				self._config.data_baudrate,
				timeout=self._config.timeout,
			)
			self._cli_serial.reset_input_buffer()
			self._data_serial.reset_input_buffer()
			logger.info("connected")
		except serial.SerialException as e:
			logger.error("connection_failed", error=str(e))
			self.disconnect()
			raise ConnectionError(f"Failed to connect: {e}") from e

	def disconnect(self) -> None:
		"""Close serial connections."""
		self.stop()
		if self._cli_serial and self._cli_serial.is_open:
			self._cli_serial.close()
			self._cli_serial = None
		if self._data_serial and self._data_serial.is_open:
			self._data_serial.close()
			self._data_serial = None
		logger.info("disconnected")

	def configure(self, config: str | Path | ChirpConfig | list[str]) -> None:
		"""Send configuration to radar."""
		if not self._cli_serial or not self._cli_serial.is_open:
			raise RuntimeError("Not connected")

		if isinstance(config, (str, Path)):
			commands = load_config(config)
		elif isinstance(config, ChirpConfig):
			commands = config.to_commands()
		else:
			commands = list(config)

		logger.info("configuring", num_commands=len(commands))
		for cmd in commands:
			self._send_command(cmd)
		logger.info("configured")

	def _send_command(self, cmd: str, wait: float = 0.03) -> str:
		"""Send CLI command and return response."""
		if not self._cli_serial:
			raise RuntimeError("CLI serial not connected")

		self._cli_serial.write(f"{cmd}\r\n".encode())
		time.sleep(wait)
		response = self._cli_serial.read(1000).decode("utf-8", errors="replace")

		if "Error" in response:
			logger.warning("command_error", cmd=cmd, response=response.strip())
		return response

	def start(self) -> None:
		"""Start sensor acquisition."""
		if not self._is_running:
			response = self._send_command("sensorStart")
			if "Error" not in response:
				self._is_running = True
				logger.info("sensor_started")
			else:
				raise RuntimeError(f"Failed to start: {response}")

	def stop(self) -> None:
		"""Stop sensor acquisition."""
		self._streaming = False
		if self._read_thread and self._read_thread.is_alive():
			self._read_thread.join(timeout=2.0)
			self._read_thread = None

		if self._is_running and self._cli_serial and self._cli_serial.is_open:
			self._send_command("sensorStop")
			self._is_running = False
			logger.info("sensor_stopped")
		self._frame_buffer.clear()

	def read_frame(self, timeout: float = 1.0) -> RadarFrame | None:
		"""Read single frame from data port."""
		if not self._data_serial:
			raise RuntimeError("Data serial not connected")

		start = time.time()
		while time.time() - start < timeout:
			if self._data_serial.in_waiting > 0:
				data = self._data_serial.read(self._data_serial.in_waiting)
				self._frame_buffer.append(data)

			frame = self._frame_buffer.extract_frame()
			if frame is not None:
				return frame
			time.sleep(0.001)
		return None

	def stream(
		self,
		max_frames: int | None = None,
		duration: float | None = None,
	) -> Generator[RadarFrame, None, None]:
		"""Stream radar frames."""
		start = time.time()
		count = 0

		while True:
			if max_frames is not None and count >= max_frames:
				break
			if duration is not None and time.time() - start >= duration:
				break

			frame = self.read_frame(timeout=0.1)
			if frame is not None:
				count += 1
				yield frame

	def stream_async(
		self,
		callback: Callable[[RadarFrame], None],
		max_frames: int | None = None,
	) -> None:
		"""Start async streaming with callback."""
		self._streaming = True
		self._frame_callbacks.append(callback)

		def read_loop() -> None:
			count = 0
			while self._streaming:
				if max_frames is not None and count >= max_frames:
					break
				frame = self.read_frame(timeout=0.1)
				if frame is not None:
					count += 1
					for cb in self._frame_callbacks:
						try:
							cb(frame)
						except Exception as e:
							logger.error("callback_error", error=str(e))
			self._streaming = False

		self._read_thread = threading.Thread(target=read_loop, daemon=True)
		self._read_thread.start()

	def get_version(self) -> dict[str, str]:
		"""Query device version."""
		response = self._send_command("version", wait=0.5)
		info = {}
		for line in response.split("\n"):
			if ":" in line:
				key, _, value = line.partition(":")
				info[key.strip()] = value.strip()
		return info

	def query_status(self) -> dict[str, str]:
		"""Query demo status."""
		response = self._send_command("queryDemoStatus", wait=0.3)
		status = {}
		for line in response.split("\n"):
			if ":" in line:
				key, _, value = line.partition(":")
				status[key.strip()] = value.strip()
		return status

	@property
	def is_connected(self) -> bool:
		cli_ok = self._cli_serial is not None and self._cli_serial.is_open
		data_ok = self._data_serial is not None and self._data_serial.is_open
		return cli_ok and data_ok

	@property
	def is_running(self) -> bool:
		return self._is_running

	def __enter__(self) -> RadarSensor:
		self.connect()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb) -> None:
		self.stop()
		self.disconnect()


def find_radar_ports() -> tuple[str, str] | None:
	"""Auto-detect radar serial ports. Returns (cli_port, data_port)."""
	usb_ports = sorted(glob.glob("/dev/ttyUSB*"))
	acm_ports = sorted(glob.glob("/dev/ttyACM*"))

	for ports in [usb_ports, acm_ports]:
		if len(ports) >= 2:
			logger.info("ports_found", cli=ports[0], data=ports[1])
			return ports[0], ports[1]
	return None
