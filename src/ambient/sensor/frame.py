"""Radar frame parsing and data structures."""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
import structlog

logger = structlog.get_logger(__name__)

MAGIC_WORD = bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07])
HEADER_SIZE = 40

# TLV types
TLV_DETECTED_POINTS = 1
TLV_RANGE_PROFILE = 2
TLV_NOISE_PROFILE = 3
TLV_AZIMUTH_STATIC_HEATMAP = 4
TLV_RANGE_DOPPLER_HEATMAP = 5
TLV_STATS = 6
TLV_DETECTED_POINTS_SIDE_INFO = 7


@dataclass(frozen=True)
class FrameHeader:
	magic: bytes
	version: int
	packet_length: int
	platform: int
	frame_number: int
	time_cpu_cycles: int
	num_detected_obj: int
	num_tlvs: int
	subframe_number: int

	@classmethod
	def from_bytes(cls, data: bytes) -> FrameHeader:
		if len(data) < HEADER_SIZE:
			raise ValueError(f"Header requires {HEADER_SIZE} bytes, got {len(data)}")

		fields = struct.unpack("<8BIIIIIIII", data[:HEADER_SIZE])
		return cls(
			magic=data[:8],
			version=fields[8],
			packet_length=fields[9],
			platform=fields[10],
			frame_number=fields[11],
			time_cpu_cycles=fields[12],
			num_detected_obj=fields[13],
			num_tlvs=fields[14],
			subframe_number=fields[15],
		)

	def validate(self) -> bool:
		return self.magic == MAGIC_WORD and self.packet_length > 0


@dataclass
class DetectedPoint:
	x: float
	y: float
	z: float
	velocity: float
	snr: float = 0.0
	noise: float = 0.0

	@property
	def range(self) -> float:
		return float(np.sqrt(self.x**2 + self.y**2 + self.z**2))

	@property
	def azimuth(self) -> float:
		return float(np.arctan2(self.x, self.y))

	@property
	def elevation(self) -> float:
		return float(np.arctan2(self.z, np.sqrt(self.x**2 + self.y**2)))


@dataclass
class RadarFrame:
	header: FrameHeader
	detected_points: list[DetectedPoint] = field(default_factory=list)
	range_profile: NDArray[np.float32] | None = None
	range_doppler_heatmap: NDArray[np.float32] | None = None
	azimuth_heatmap: NDArray[np.complex64] | None = None
	raw_data: bytes = b""
	timestamp: float = 0.0

	@classmethod
	def from_bytes(cls, data: bytes, timestamp: float = 0.0) -> RadarFrame:
		header = FrameHeader.from_bytes(data)
		frame = cls(header=header, raw_data=data, timestamp=timestamp)

		offset = HEADER_SIZE
		for _ in range(header.num_tlvs):
			if offset + 8 > len(data):
				logger.warning("truncated_tlv", offset=offset)
				break

			tlv_type, tlv_length = struct.unpack("<II", data[offset:offset + 8])
			tlv_data = data[offset + 8:offset + 8 + tlv_length]
			offset += 8 + tlv_length
			frame._parse_tlv(tlv_type, tlv_data)

		return frame

	def _parse_tlv(self, tlv_type: int, data: bytes) -> None:
		if tlv_type == TLV_DETECTED_POINTS:
			self._parse_detected_points(data)
		elif tlv_type == TLV_RANGE_PROFILE:
			self._parse_range_profile(data)
		elif tlv_type == TLV_RANGE_DOPPLER_HEATMAP:
			self._parse_range_doppler(data)

	def _parse_detected_points(self, data: bytes) -> None:
		# 16 bytes without SNR, 24 with
		point_size = 24 if len(data) % 24 == 0 and len(data) % 16 != 0 else 16
		num_points = len(data) // point_size

		for i in range(num_points):
			off = i * point_size
			if point_size == 16:
				x, y, z, vel = struct.unpack("<ffff", data[off:off + 16])
				snr, noise = 0.0, 0.0
			else:
				x, y, z, vel, snr, noise = struct.unpack("<ffffff", data[off:off + 24])

			self.detected_points.append(
				DetectedPoint(x=x, y=y, z=z, velocity=vel, snr=snr, noise=noise)
			)

	def _parse_range_profile(self, data: bytes) -> None:
		self.range_profile = np.frombuffer(data, dtype=np.uint16).astype(np.float32)

	def _parse_range_doppler(self, data: bytes) -> None:
		self.range_doppler_heatmap = np.frombuffer(data, dtype=np.uint16).astype(np.float32)


class FrameBuffer:
	"""Accumulates serial data and extracts complete frames."""

	def __init__(self, max_size: int = 65536) -> None:
		self._buffer = bytearray()
		self._max_size = max_size

	def append(self, data: bytes) -> None:
		self._buffer.extend(data)
		if len(self._buffer) > self._max_size:
			idx = self._buffer.rfind(MAGIC_WORD)
			if idx > 0:
				self._buffer = self._buffer[idx:]

	def extract_frame(self) -> RadarFrame | None:
		idx = self._buffer.find(MAGIC_WORD)
		if idx < 0:
			return None

		if idx > 0:
			self._buffer = self._buffer[idx:]

		if len(self._buffer) < HEADER_SIZE:
			return None

		try:
			header = FrameHeader.from_bytes(bytes(self._buffer[:HEADER_SIZE]))
		except Exception:
			self._buffer = self._buffer[8:]
			return None

		if len(self._buffer) < header.packet_length:
			return None

		frame_data = bytes(self._buffer[:header.packet_length])
		self._buffer = self._buffer[header.packet_length:]
		return RadarFrame.from_bytes(frame_data, timestamp=time.time())

	def clear(self) -> None:
		self._buffer.clear()

	def __len__(self) -> int:
		return len(self._buffer)
