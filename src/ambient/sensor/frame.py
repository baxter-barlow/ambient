"""Radar frame parsing and data structures."""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
	pass

MAGIC_WORD = bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07])
HEADER_SIZE = 40

TLV_DETECTED_POINTS = 1
TLV_RANGE_PROFILE = 2
TLV_NOISE_PROFILE = 3
TLV_RANGE_DOPPLER = 5
TLV_STATS = 6


def _parse_points(data: bytes) -> list:
	"""Parse detected points from TLV data."""
	points = []
	point_size = 24 if len(data) % 24 == 0 and len(data) % 16 != 0 else 16
	num_points = len(data) // point_size

	for i in range(num_points):
		off = i * point_size
		if point_size == 16:
			x, y, z, vel = struct.unpack("<ffff", data[off:off + 16])
			snr, noise = 0.0, 0.0
		else:
			x, y, z, vel, snr, noise = struct.unpack("<ffffff", data[off:off + 24])
		points.append(DetectedPoint(x=x, y=y, z=z, velocity=vel, snr=snr, noise=noise))

	return points


def _parse_range_profile(data: bytes) -> NDArray[np.float32]:
	"""Parse range profile from TLV data and convert to dB."""
	num_bins = len(data) // 2
	values = struct.unpack(f"<{num_bins}H", data)
	arr = np.array(values, dtype=np.float32)
	# Convert magnitude to dB scale (TI sends raw magnitude values)
	return 20 * np.log10(arr + 1)


def _parse_range_doppler(data: bytes) -> NDArray[np.float32] | None:
	"""Parse range-doppler heatmap from TLV data and convert to dB."""
	num_values = len(data) // 2
	if num_values == 0:
		return None
	values = struct.unpack(f"<{num_values}H", data)
	arr = np.array(values, dtype=np.float32)
	# Convert to dB scale
	arr_db = 20 * np.log10(arr + 1)
	side = int(np.sqrt(num_values))
	if side * side == num_values:
		return arr_db.reshape((side, side))
	return arr_db.reshape((-1, 256)) if num_values % 256 == 0 else None


@dataclass
class DetectedPoint:
	"""Single detected point from radar."""
	x: float
	y: float
	z: float
	velocity: float
	snr: float = 0.0
	noise: float = 0.0

	@property
	def range(self) -> float:
		return np.sqrt(self.x**2 + self.y**2 + self.z**2)

	@property
	def azimuth(self) -> float:
		return np.arctan2(self.x, self.y)

	@property
	def elevation(self) -> float:
		r_xy = np.sqrt(self.x**2 + self.y**2)
		return np.arctan2(self.z, r_xy) if r_xy > 0 else 0.0


@dataclass
class FrameHeader:
	"""Radar frame header."""
	version: int
	packet_length: int
	platform: int
	frame_number: int
	time_cpu_cycles: int
	num_detected_obj: int
	num_tlvs: int
	subframe_number: int = 0
	_raw_data: bytes = field(default=b"", repr=False)

	@classmethod
	def from_bytes(cls, data: bytes) -> FrameHeader:
		"""Parse header from raw bytes."""
		if len(data) < HEADER_SIZE:
			raise ValueError(f"Data too short: {len(data)} < {HEADER_SIZE}")
		fields = struct.unpack("<8BIIIIIIII", data[:40])
		return cls(
			version=fields[8],
			packet_length=fields[9],
			platform=fields[10],
			frame_number=fields[11],
			time_cpu_cycles=fields[12],
			num_detected_obj=fields[13],
			num_tlvs=fields[14],
			subframe_number=fields[15] if len(fields) > 15 else 0,
			_raw_data=data[:8],
		)

	def validate(self) -> bool:
		"""Check if the header has valid magic word."""
		return self._raw_data[:8] == MAGIC_WORD


@dataclass
class RadarFrame:
	"""Complete radar frame with header and parsed data."""
	header: FrameHeader | None = None
	detected_points: list[DetectedPoint] = field(default_factory=list)
	range_profile: NDArray[np.float32] | None = None
	range_doppler_heatmap: NDArray[np.float32] | None = None
	timestamp: float = field(default_factory=time.time)
	raw_data: bytes = b""

	@classmethod
	def from_bytes(cls, data: bytes, timestamp: float | None = None) -> RadarFrame:
		"""Parse a complete frame from raw bytes."""
		if len(data) < HEADER_SIZE:
			raise ValueError(f"Data too short: {len(data)} < {HEADER_SIZE}")

		header = FrameHeader.from_bytes(data)
		frame = cls(
			header=header,
			raw_data=data,
			timestamp=timestamp if timestamp is not None else time.time(),
		)

		# Parse TLVs
		offset = HEADER_SIZE
		for _ in range(header.num_tlvs):
			if offset + 8 > len(data):
				break
			tlv_type, tlv_length = struct.unpack("<II", data[offset:offset + 8])
			tlv_data = data[offset + 8:offset + 8 + tlv_length]
			offset += 8 + tlv_length

			if tlv_type == TLV_DETECTED_POINTS:
				frame.detected_points = _parse_points(tlv_data)
			elif tlv_type == TLV_RANGE_PROFILE:
				frame.range_profile = _parse_range_profile(tlv_data)
			elif tlv_type == TLV_RANGE_DOPPLER:
				frame.range_doppler_heatmap = _parse_range_doppler(tlv_data)

		return frame


class FrameBuffer:
	"""Accumulates serial data and extracts complete frames."""

	def __init__(self, max_size: int = 65536):
		self._buffer = bytearray()
		self._max_size = max_size

	def append(self, data: bytes):
		"""Add data to buffer."""
		self._buffer.extend(data)
		if len(self._buffer) > self._max_size:
			idx = self._buffer.rfind(MAGIC_WORD)
			if idx > 0:
				self._buffer = self._buffer[idx:]
			else:
				self._buffer = self._buffer[-1024:]

	def extract_frame(self) -> RadarFrame | None:
		"""Extract and parse a complete frame, or return None."""
		idx = self._buffer.find(MAGIC_WORD)
		if idx == -1:
			if len(self._buffer) > 32:
				self._buffer = self._buffer[-16:]
			return None

		if idx > 0:
			self._buffer = self._buffer[idx:]

		if len(self._buffer) < HEADER_SIZE:
			return None

		header = self._parse_header(bytes(self._buffer[:HEADER_SIZE]))
		if header.packet_length > self._max_size or header.packet_length < HEADER_SIZE:
			self._buffer = self._buffer[8:]
			return None

		if len(self._buffer) < header.packet_length:
			return None

		frame_data = bytes(self._buffer[:header.packet_length])
		self._buffer = self._buffer[header.packet_length:]

		return self._parse_frame(header, frame_data)

	def _parse_header(self, data: bytes) -> FrameHeader:
		fields = struct.unpack("<8BIIIIIIII", data[:40])
		return FrameHeader(
			version=fields[8],
			packet_length=fields[9],
			platform=fields[10],
			frame_number=fields[11],
			time_cpu_cycles=fields[12],
			num_detected_obj=fields[13],
			num_tlvs=fields[14],
			subframe_number=fields[15] if len(fields) > 15 else 0,
		)

	def _parse_frame(self, header: FrameHeader, data: bytes) -> RadarFrame:
		frame = RadarFrame(header=header, raw_data=data, timestamp=time.time())

		offset = HEADER_SIZE
		for _ in range(header.num_tlvs):
			if offset + 8 > len(data):
				break

			tlv_type, tlv_length = struct.unpack("<II", data[offset:offset + 8])
			tlv_data = data[offset + 8:offset + 8 + tlv_length]
			offset += 8 + tlv_length

			if tlv_type == TLV_DETECTED_POINTS:
				frame.detected_points = self._parse_points(tlv_data)
			elif tlv_type == TLV_RANGE_PROFILE:
				frame.range_profile = self._parse_range_profile(tlv_data)
			elif tlv_type == TLV_RANGE_DOPPLER:
				frame.range_doppler_heatmap = self._parse_range_doppler(tlv_data, header)

		return frame

	def _parse_points(self, data: bytes) -> list[DetectedPoint]:
		points = []
		point_size = 24 if len(data) % 24 == 0 and len(data) % 16 != 0 else 16
		num_points = len(data) // point_size

		for i in range(num_points):
			off = i * point_size
			if point_size == 16:
				x, y, z, vel = struct.unpack("<ffff", data[off:off + 16])
				snr, noise = 0.0, 0.0
			else:
				x, y, z, vel, snr, noise = struct.unpack("<ffffff", data[off:off + 24])
			points.append(DetectedPoint(x=x, y=y, z=z, velocity=vel, snr=snr, noise=noise))

		return points

	def _parse_range_profile(self, data: bytes) -> NDArray[np.float32]:
		num_bins = len(data) // 2
		values = struct.unpack(f"<{num_bins}H", data)
		arr = np.array(values, dtype=np.float32)
		# Convert magnitude to dB scale (TI sends raw magnitude values)
		return 20 * np.log10(arr + 1)

	def _parse_range_doppler(self, data: bytes, header: FrameHeader) -> NDArray[np.float32] | None:
		num_values = len(data) // 2
		if num_values == 0:
			return None
		values = struct.unpack(f"<{num_values}H", data)
		arr = np.array(values, dtype=np.float32)
		# Convert to dB scale
		arr_db = 20 * np.log10(arr + 1)
		side = int(np.sqrt(num_values))
		if side * side == num_values:
			return arr_db.reshape((side, side))
		return arr_db.reshape((-1, 256)) if num_values % 256 == 0 else None

	def clear(self):
		self._buffer.clear()

	def __len__(self) -> int:
		return len(self._buffer)
