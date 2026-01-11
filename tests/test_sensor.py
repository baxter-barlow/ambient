"""Tests for sensor module."""

import numpy as np
import pytest

from ambient.sensor.config import SerialConfig
from ambient.sensor.frame import DetectedPoint, FrameBuffer, FrameHeader, RadarFrame
from ambient.sensor.radar import RadarSensor, SensorDisconnectedError


class TestFrameHeader:
	def test_from_bytes(self, sample_frame_bytes):
		header = FrameHeader.from_bytes(sample_frame_bytes)
		assert header.frame_number == 1
		assert header.num_detected_obj == 3
		assert header.num_tlvs == 1

	def test_validate(self, sample_frame_bytes):
		header = FrameHeader.from_bytes(sample_frame_bytes)
		assert header.validate()

	def test_invalid_magic(self):
		bad = b"\x00" * 40
		header = FrameHeader.from_bytes(bad)
		assert not header.validate()


class TestDetectedPoint:
	def test_range_calculation(self):
		pt = DetectedPoint(x=3.0, y=4.0, z=0.0, velocity=0.0)
		assert abs(pt.range - 5.0) < 0.001

	def test_azimuth(self):
		pt = DetectedPoint(x=1.0, y=1.0, z=0.0, velocity=0.0)
		assert abs(pt.azimuth - np.pi / 4) < 0.01


class TestRadarFrame:
	def test_from_bytes(self, sample_frame_bytes):
		frame = RadarFrame.from_bytes(sample_frame_bytes, timestamp=1.0)
		assert frame.header.frame_number == 1
		assert len(frame.detected_points) == 3
		assert frame.timestamp == 1.0

	def test_detected_points_parsed(self, sample_frame_bytes):
		frame = RadarFrame.from_bytes(sample_frame_bytes)
		assert frame.detected_points[0].x == pytest.approx(1.0)
		assert frame.detected_points[1].x == pytest.approx(2.0)


class TestFrameBuffer:
	def test_extract_frame(self, sample_frame_bytes):
		buf = FrameBuffer()
		buf.append(sample_frame_bytes)
		frame = buf.extract_frame()
		assert frame is not None
		assert frame.header.frame_number == 1

	def test_extracted_frame_header_validates(self, sample_frame_bytes):
		"""Test that frames extracted by FrameBuffer have valid headers."""
		buf = FrameBuffer()
		buf.append(sample_frame_bytes)
		frame = buf.extract_frame()
		assert frame is not None
		assert frame.header is not None
		# Header should validate since _raw_data contains magic word
		assert frame.header.validate() is True

	def test_handles_partial_data(self, sample_frame_bytes):
		buf = FrameBuffer()
		buf.append(sample_frame_bytes[:20])
		assert buf.extract_frame() is None
		buf.append(sample_frame_bytes[20:])
		assert buf.extract_frame() is not None

	def test_skips_garbage(self, sample_frame_bytes):
		buf = FrameBuffer()
		buf.append(b"\xff" * 50 + sample_frame_bytes)
		frame = buf.extract_frame()
		assert frame is not None

	def test_clear(self, sample_frame_bytes):
		buf = FrameBuffer()
		buf.append(sample_frame_bytes)
		buf.clear()
		assert len(buf) == 0


class TestRadarSensorInit:
	def test_default_config(self):
		sensor = RadarSensor()
		# Empty ports trigger auto-detection
		assert sensor._config.cli_port == ""
		assert sensor._config.data_port == ""
		assert not sensor._auto_reconnect

	def test_custom_config(self):
		config = SerialConfig(cli_port="/dev/ttyACM0", data_port="/dev/ttyACM1")
		sensor = RadarSensor(config)
		assert sensor._config.cli_port == "/dev/ttyACM0"

	def test_auto_reconnect_option(self):
		sensor = RadarSensor(auto_reconnect=True)
		assert sensor._auto_reconnect


class TestRadarSensorCallbacks:
	def test_set_callbacks(self):
		sensor = RadarSensor()
		disconnect_called = []
		reconnect_called = []

		sensor.set_callbacks(
			on_disconnect=lambda: disconnect_called.append(True),
			on_reconnect=lambda: reconnect_called.append(True),
		)

		assert sensor._on_disconnect is not None
		assert sensor._on_reconnect is not None

	def test_check_connection_when_disconnected(self):
		sensor = RadarSensor()
		assert not sensor._check_connection()

	def test_last_config_stored(self):
		sensor = RadarSensor()
		# Just check the attribute exists (can't actually configure without hardware)
		assert sensor._last_config is None


class TestSensorDisconnectedError:
	def test_exception_can_be_raised(self):
		with pytest.raises(SensorDisconnectedError):
			raise SensorDisconnectedError("test error")
