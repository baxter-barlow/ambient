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
TLV_VITAL_SIGNS = 0x410  # 1040 decimal - Vital Signs demo output

# Chirp custom TLV types (https://github.com/baxter-barlow/chirp)
TLV_CHIRP_COMPLEX_RANGE_FFT = 0x0500  # Full I/Q for all range bins
TLV_CHIRP_TARGET_IQ = 0x0510          # I/Q for selected target bins
TLV_CHIRP_PHASE_OUTPUT = 0x0520       # Phase + magnitude for bins
TLV_CHIRP_PRESENCE = 0x0540           # Presence detection result
TLV_CHIRP_MOTION_STATUS = 0x0550      # Motion detection result
TLV_CHIRP_TARGET_INFO = 0x0560        # Target selection metadata

# Vital signs waveform size (number of samples per waveform)
VITAL_SIGNS_WAVEFORM_SIZE = 20


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
class VitalSignsTLV:
	"""Vital signs data from TI Vital Signs demo firmware (TLV type 0x410).

	This TLV is only present when using the Vital Signs with People Tracking
	firmware, not the Out-of-Box demo.
	"""
	range_bin_index: int               # Range bin where person is detected
	breathing_deviation: float         # Chest displacement in mm
	heart_deviation: float             # Heart displacement in mm
	breathing_rate: float              # Breaths per minute
	heart_rate: float                  # Beats per minute
	breathing_confidence: float        # 0.0 to 1.0
	heart_confidence: float            # 0.0 to 1.0
	breathing_waveform: NDArray[np.float32]  # Filtered breathing signal
	heart_waveform: NDArray[np.float32]      # Filtered heart signal
	unwrapped_phase: float             # Current unwrapped phase value (radians)

	@classmethod
	def from_bytes(cls, data: bytes) -> VitalSignsTLV | None:
		"""Parse vital signs TLV from raw bytes.

		TLV format (based on TI Vital Signs Lab documentation):
		- uint16: rangeBinIndex
		- uint16: reserved
		- float32: breathDeviation
		- float32: heartDeviation
		- float32: breathRate
		- float32: heartRate
		- float32: breathConfidence
		- float32: heartConfidence
		- float32[20]: breathWaveform
		- float32[20]: heartWaveform
		- float32: unwrappedPhasePeak

		Total: 4 + 6*4 + 20*4 + 20*4 + 4 = 192 bytes minimum
		Some SDK versions may have different layouts (136 bytes common).
		"""
		# Minimum size check - support both 136-byte and 192-byte formats
		if len(data) < 136:
			return None

		try:
			# Parse header: range bin index + reserved
			range_bin_index, _ = struct.unpack("<HH", data[0:4])

			# Parse scalar values (6 floats)
			scalars = struct.unpack("<6f", data[4:28])
			breathing_deviation = scalars[0]
			heart_deviation = scalars[1]
			breathing_rate = scalars[2]
			heart_rate = scalars[3]
			breathing_confidence = scalars[4]
			heart_confidence = scalars[5]

			# Parse waveforms - size depends on TLV length
			# 136 bytes = 4 header + 24 scalars + 40 breath + 40 heart + 28 extras
			# 192 bytes = 4 header + 24 scalars + 80 breath + 80 heart + 4 phase
			waveform_size = VITAL_SIGNS_WAVEFORM_SIZE
			if len(data) >= 192:
				# Full 20-sample waveforms
				waveform_size = 20
			else:
				# Shorter waveforms for 136-byte format (10 samples each)
				waveform_size = 10

			breath_start = 28
			breath_end = breath_start + waveform_size * 4
			breathing_waveform = np.array(
				struct.unpack(f"<{waveform_size}f", data[breath_start:breath_end]),
				dtype=np.float32
			)

			heart_start = breath_end
			heart_end = heart_start + waveform_size * 4
			heart_waveform = np.array(
				struct.unpack(f"<{waveform_size}f", data[heart_start:heart_end]),
				dtype=np.float32
			)

			# Parse unwrapped phase if present
			unwrapped_phase = 0.0
			if len(data) >= heart_end + 4:
				unwrapped_phase = struct.unpack("<f", data[heart_end:heart_end + 4])[0]

			return cls(
				range_bin_index=range_bin_index,
				breathing_deviation=breathing_deviation,
				heart_deviation=heart_deviation,
				breathing_rate=breathing_rate,
				heart_rate=heart_rate,
				breathing_confidence=breathing_confidence,
				heart_confidence=heart_confidence,
				breathing_waveform=breathing_waveform,
				heart_waveform=heart_waveform,
				unwrapped_phase=unwrapped_phase,
			)
		except (struct.error, ValueError):
			return None


@dataclass
class ChirpPhaseBin:
	"""Single bin from chirp PHASE_OUTPUT TLV."""
	bin_index: int
	phase: float          # Radians (-π to +π)
	magnitude: int        # Raw magnitude
	has_motion: bool
	is_valid: bool


@dataclass
class ChirpPhaseOutput:
	"""Chirp PHASE_OUTPUT TLV (0x0520) - Primary output for vital signs.

	Phase and magnitude for selected target bins. Use phase data for
	vital signs extraction (respiratory and heart rate).
	"""
	num_bins: int
	center_bin: int
	timestamp_us: int
	bins: list[ChirpPhaseBin]

	@classmethod
	def from_bytes(cls, data: bytes) -> ChirpPhaseOutput | None:
		"""Parse PHASE_OUTPUT TLV from raw bytes."""
		if len(data) < 8:
			return None
		try:
			num_bins, center_bin, timestamp_us = struct.unpack("<HHI", data[0:8])
			bins = []
			for i in range(num_bins):
				offset = 8 + i * 8
				if offset + 8 > len(data):
					break
				bin_idx, phase_raw, magnitude, flags = struct.unpack(
					"<HhHH", data[offset:offset + 8]
				)
				# Convert fixed-point phase to radians
				phase = (phase_raw / 32768.0) * np.pi
				bins.append(ChirpPhaseBin(
					bin_index=bin_idx,
					phase=phase,
					magnitude=magnitude,
					has_motion=bool(flags & 1),
					is_valid=bool(flags & 2),
				))
			return cls(
				num_bins=num_bins,
				center_bin=center_bin,
				timestamp_us=timestamp_us,
				bins=bins,
			)
		except struct.error:
			return None

	def get_center_phase(self) -> float | None:
		"""Get phase of center bin if valid.

		Returns the phase from the center bin if found and valid.
		Falls back to the first valid bin if center bin not found.
		Returns None if no valid bins exist.
		"""
		# First try to find the center bin
		for b in self.bins:
			if b.bin_index == self.center_bin and b.is_valid:
				return b.phase
		# Fall back to first valid bin
		for b in self.bins:
			if b.is_valid:
				return b.phase
		return None


@dataclass
class ChirpTargetIQ:
	"""Chirp TARGET_IQ TLV (0x0510) - I/Q for selected target bins."""
	num_bins: int
	center_bin: int
	timestamp_us: int
	iq_data: NDArray[np.complex64]  # Complex I/Q values
	bin_indices: list[int]

	@classmethod
	def from_bytes(cls, data: bytes) -> ChirpTargetIQ | None:
		"""Parse TARGET_IQ TLV from raw bytes."""
		if len(data) < 8:
			return None
		try:
			num_bins, center_bin, timestamp_us = struct.unpack("<HHI", data[0:8])
			iq_values = []
			bin_indices = []
			for i in range(num_bins):
				offset = 8 + i * 8
				if offset + 8 > len(data):
					break
				bin_idx, imag, real, _ = struct.unpack("<HhhH", data[offset:offset + 8])
				iq_values.append(complex(real, imag))
				bin_indices.append(bin_idx)
			return cls(
				num_bins=num_bins,
				center_bin=center_bin,
				timestamp_us=timestamp_us,
				iq_data=np.array(iq_values, dtype=np.complex64),
				bin_indices=bin_indices,
			)
		except struct.error:
			return None


@dataclass
class ChirpPresence:
	"""Chirp PRESENCE TLV (0x0540) - Presence detection result."""
	presence: int        # 0=absent, 1=present, 2=motion
	confidence: int      # 0-100%
	range_m: float       # Range in meters
	target_bin: int

	@property
	def is_present(self) -> bool:
		return self.presence > 0

	@property
	def has_motion(self) -> bool:
		return self.presence == 2

	@classmethod
	def from_bytes(cls, data: bytes) -> ChirpPresence | None:
		"""Parse PRESENCE TLV from raw bytes."""
		if len(data) < 8:
			return None
		try:
			presence, confidence, range_q8, target_bin, _ = struct.unpack(
				"<BBHHH", data[0:8]
			)
			return cls(
				presence=presence,
				confidence=confidence,
				range_m=range_q8 / 256.0,
				target_bin=target_bin,
			)
		except struct.error:
			return None


@dataclass
class ChirpMotionStatus:
	"""Chirp MOTION_STATUS TLV (0x0550) - Motion detection result."""
	motion_detected: bool
	motion_level: int      # 0-255 intensity
	motion_bin_count: int
	peak_motion_bin: int
	peak_motion_delta: int

	@classmethod
	def from_bytes(cls, data: bytes) -> ChirpMotionStatus | None:
		"""Parse MOTION_STATUS TLV from raw bytes."""
		if len(data) < 8:
			return None
		try:
			detected, level, bin_count, peak_bin, peak_delta = struct.unpack(
				"<BBHHH", data[0:8]
			)
			return cls(
				motion_detected=bool(detected),
				motion_level=level,
				motion_bin_count=bin_count,
				peak_motion_bin=peak_bin,
				peak_motion_delta=peak_delta,
			)
		except struct.error:
			return None


@dataclass
class ChirpTargetInfo:
	"""Chirp TARGET_INFO TLV (0x0560) - Target selection metadata."""
	primary_bin: int
	primary_magnitude: int
	range_m: float
	confidence: int
	num_targets: int
	secondary_bin: int

	@classmethod
	def from_bytes(cls, data: bytes) -> ChirpTargetInfo | None:
		"""Parse TARGET_INFO TLV from raw bytes."""
		if len(data) < 12:
			return None
		try:
			(primary_bin, primary_mag, range_q8,
				confidence, num_targets, secondary_bin, _reserved) = struct.unpack("<HHHBBHH", data[0:12])
			return cls(
				primary_bin=primary_bin,
				primary_magnitude=primary_mag,
				range_m=range_q8 / 256.0,
				confidence=confidence,
				num_targets=num_targets,
				secondary_bin=secondary_bin,
			)
		except struct.error:
			return None


@dataclass
class ChirpComplexRangeFFT:
	"""Chirp COMPLEX_RANGE_FFT TLV (0x0500) - Full I/Q for all range bins."""
	num_range_bins: int
	chirp_index: int
	rx_antenna: int
	iq_data: NDArray[np.complex64]

	@classmethod
	def from_bytes(cls, data: bytes) -> ChirpComplexRangeFFT | None:
		"""Parse COMPLEX_RANGE_FFT TLV from raw bytes."""
		if len(data) < 8:
			return None
		try:
			num_bins, chirp_idx, rx_ant, _ = struct.unpack("<HHHH", data[0:8])
			# Parse I/Q pairs (imag first, then real per TI convention)
			iq_values = []
			for i in range(num_bins):
				offset = 8 + i * 4
				if offset + 4 > len(data):
					break
				imag, real = struct.unpack("<hh", data[offset:offset + 4])
				iq_values.append(complex(real, imag))
			return cls(
				num_range_bins=num_bins,
				chirp_index=chirp_idx,
				rx_antenna=rx_ant,
				iq_data=np.array(iq_values, dtype=np.complex64),
			)
		except struct.error:
			return None


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
	vital_signs: VitalSignsTLV | None = None  # Present only with vital signs firmware
	timestamp: float = field(default_factory=time.time)
	raw_data: bytes = b""
	# Chirp custom TLVs
	chirp_complex_fft: ChirpComplexRangeFFT | None = None
	chirp_target_iq: ChirpTargetIQ | None = None
	chirp_phase: ChirpPhaseOutput | None = None
	chirp_presence: ChirpPresence | None = None
	chirp_motion: ChirpMotionStatus | None = None
	chirp_target_info: ChirpTargetInfo | None = None

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
			elif tlv_type == TLV_VITAL_SIGNS:
				frame.vital_signs = VitalSignsTLV.from_bytes(tlv_data)
			# Chirp custom TLVs
			elif tlv_type == TLV_CHIRP_COMPLEX_RANGE_FFT:
				frame.chirp_complex_fft = ChirpComplexRangeFFT.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_TARGET_IQ:
				frame.chirp_target_iq = ChirpTargetIQ.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_PHASE_OUTPUT:
				frame.chirp_phase = ChirpPhaseOutput.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_PRESENCE:
				frame.chirp_presence = ChirpPresence.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_MOTION_STATUS:
				frame.chirp_motion = ChirpMotionStatus.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_TARGET_INFO:
				frame.chirp_target_info = ChirpTargetInfo.from_bytes(tlv_data)

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
			_raw_data=data[:8],  # Store magic word for validation
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
			elif tlv_type == TLV_VITAL_SIGNS:
				frame.vital_signs = VitalSignsTLV.from_bytes(tlv_data)
			# Chirp custom TLVs
			elif tlv_type == TLV_CHIRP_COMPLEX_RANGE_FFT:
				frame.chirp_complex_fft = ChirpComplexRangeFFT.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_TARGET_IQ:
				frame.chirp_target_iq = ChirpTargetIQ.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_PHASE_OUTPUT:
				frame.chirp_phase = ChirpPhaseOutput.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_PRESENCE:
				frame.chirp_presence = ChirpPresence.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_MOTION_STATUS:
				frame.chirp_motion = ChirpMotionStatus.from_bytes(tlv_data)
			elif tlv_type == TLV_CHIRP_TARGET_INFO:
				frame.chirp_target_info = ChirpTargetInfo.from_bytes(tlv_data)

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
