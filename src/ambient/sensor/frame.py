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

# Standard TLV types
TLV_DETECTED_POINTS = 1
TLV_RANGE_PROFILE = 2
TLV_NOISE_PROFILE = 3
TLV_AZIMUTH_STATIC_HEATMAP = 4
TLV_RANGE_DOPPLER = 5
TLV_STATS = 6
TLV_DETECTED_POINTS_SIDE_INFO = 7     # SNR and noise per point
TLV_AZIMUTH_ELEVATION_HEATMAP = 8
TLV_TEMPERATURE_STATS = 9
TLV_POINT_CLOUD_2D = 20
TLV_VITAL_SIGNS = 0x410  # 1040 decimal - Vital Signs demo output

# Tracking TLV types (People Tracking demo)
TLV_TRACKED_OBJECTS = 250             # 3D tracked objects with velocity
TLV_TARGET_LIST_2D = 251              # 2D target list
TLV_TARGET_INDEX = 252                # Point-to-track association
TLV_COMPRESSED_POINTS = 253           # Compressed spherical point cloud
TLV_PRESENCE_INDICATION = 254         # Presence detection result

# Gesture TLV types
TLV_GESTURE_FEATURES = 1010
TLV_GESTURE_OUTPUT = 1020
TLV_GESTURE_CLASSIFIER = 1021

# Chirp custom TLV types (https://github.com/baxter-barlow/chirp)
TLV_CHIRP_COMPLEX_RANGE_FFT = 0x0500  # Full I/Q for all range bins
TLV_CHIRP_TARGET_IQ = 0x0510          # I/Q for selected target bins
TLV_CHIRP_PHASE_OUTPUT = 0x0520       # Phase + magnitude for bins
TLV_CHIRP_PRESENCE = 0x0540           # Presence detection result
TLV_CHIRP_MOTION_STATUS = 0x0550      # Motion detection result
TLV_CHIRP_TARGET_INFO = 0x0560        # Target selection metadata

# Vital signs waveform size (number of samples per waveform)
VITAL_SIGNS_WAVEFORM_SIZE = 20
VITAL_SIGNS_TI_WAVEFORM_SIZE = 15  # TI multi-patient format uses 15 samples


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
	"""Vital signs data from TI Vital Signs demo firmware (TLV type 0x410/1040).

	This TLV is present when using the Vital Signs with People Tracking
	firmware. Supports both single-patient and multi-patient formats.

	Multi-patient format (TI 136-byte format):
	- 2H: patient_id, range_bin
	- 33f: breathing_deviation, heart_rate, breathing_rate,
	       heart_waveform[15], breath_waveform[15]

	Single-patient format (192-byte format):
	- 2H: range_bin, reserved
	- 6f: scalars (deviations, rates, confidences)
	- 20f: breath_waveform, 20f: heart_waveform
	- f: unwrapped_phase
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
	patient_id: int = 0                # Patient ID for multi-patient mode

	# Presence detection thresholds (from TI documentation)
	BREATHING_DEVIATION_PRESENT = 0.02  # >= 0.02: patient present & breathing
	BREATHING_DEVIATION_HOLDING = 0.0   # > 0 but < 0.02: holding breath
	# == 0: no patient detected

	@property
	def patient_status(self) -> str:
		"""Get patient status based on breathing deviation (TI algorithm).

		Returns:
			'present': Patient detected and breathing normally
			'holding_breath': Patient detected but holding breath
			'not_detected': No patient in range
		"""
		if self.breathing_deviation == 0:
			return "not_detected"
		elif self.breathing_deviation >= self.BREATHING_DEVIATION_PRESENT:
			return "present"
		else:
			return "holding_breath"

	@property
	def is_patient_present(self) -> bool:
		"""Check if patient is detected (regardless of breathing status)."""
		return self.breathing_deviation > 0

	@classmethod
	def from_bytes(cls, data: bytes) -> VitalSignsTLV | None:
		"""Parse vital signs TLV from raw bytes.

		Supports two formats:

		1. TI Multi-Patient Format (136 bytes):
		   - uint16: patient_id
		   - uint16: range_bin
		   - float32: breathing_deviation
		   - float32: heart_rate
		   - float32: breathing_rate
		   - float32[15]: heart_waveform
		   - float32[15]: breath_waveform
		   Total: 4 + 3*4 + 15*4 + 15*4 = 136 bytes

		2. Legacy Single-Patient Format (192 bytes):
		   - uint16: range_bin_index
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
		   Total: 4 + 6*4 + 20*4 + 20*4 + 4 = 192 bytes
		"""
		if len(data) < 136:
			return None

		try:
			# Detect format based on size and heuristics
			# TI multi-patient format is exactly 136 bytes
			# Legacy format is typically 192 bytes
			if len(data) == 136:
				return cls._parse_ti_multipatient_format(data)
			elif len(data) >= 192:
				return cls._parse_legacy_format(data)
			else:
				# Try to parse as shortened legacy format
				return cls._parse_legacy_format(data)

		except (struct.error, ValueError):
			return None

	@classmethod
	def _parse_ti_multipatient_format(cls, data: bytes) -> VitalSignsTLV | None:
		"""Parse TI multi-patient vital signs format (136 bytes).

		Structure:
			Offset 0:   patient_id (uint16)
			Offset 2:   range_bin (uint16)
			Offset 4:   breathing_deviation (float32)
			Offset 8:   heart_rate (float32)
			Offset 12:  breathing_rate (float32)
			Offset 16:  heart_waveform[15] (15 × float32 = 60 bytes)
			Offset 76:  breath_waveform[15] (15 × float32 = 60 bytes)
		"""
		# Parse header: patient_id + range_bin
		patient_id, range_bin = struct.unpack("<HH", data[0:4])

		# Parse vitals data (33 floats starting at offset 4)
		vitals_data = struct.unpack("<33f", data[4:136])

		breathing_deviation = vitals_data[0]
		heart_rate = vitals_data[1]
		breathing_rate = vitals_data[2]
		heart_waveform = np.array(vitals_data[3:18], dtype=np.float32)    # indices 3-17
		breath_waveform = np.array(vitals_data[18:33], dtype=np.float32)  # indices 18-32

		# Compute confidence from breathing deviation
		# TI uses breathing deviation as primary quality indicator
		if breathing_deviation >= cls.BREATHING_DEVIATION_PRESENT:
			breathing_confidence = min(1.0, breathing_deviation * 10)  # Scale to 0-1
			heart_confidence = min(1.0, breathing_deviation * 10)
		elif breathing_deviation > 0:
			breathing_confidence = 0.3  # Holding breath
			heart_confidence = 0.5
		else:
			breathing_confidence = 0.0
			heart_confidence = 0.0

		return cls(
			patient_id=patient_id,
			range_bin_index=range_bin,
			breathing_deviation=breathing_deviation,
			heart_deviation=0.0,  # Not provided in this format
			breathing_rate=breathing_rate,
			heart_rate=heart_rate,
			breathing_confidence=breathing_confidence,
			heart_confidence=heart_confidence,
			breathing_waveform=breath_waveform,
			heart_waveform=heart_waveform,
			unwrapped_phase=0.0,  # Not provided in this format
		)

	@classmethod
	def _parse_legacy_format(cls, data: bytes) -> VitalSignsTLV | None:
		"""Parse legacy single-patient format (192 bytes or variable)."""
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
		# 192 bytes = 4 header + 24 scalars + 80 breath + 80 heart + 4 phase
		waveform_size = VITAL_SIGNS_WAVEFORM_SIZE
		if len(data) >= 192:
			waveform_size = 20
		else:
			# Shorter waveforms for smaller format
			waveform_size = min(10, (len(data) - 28) // 8)

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
			patient_id=0,
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


# =============================================================================
# Tracking TLV Types (People Tracking Demo)
# =============================================================================


@dataclass
class TrackedObject:
	"""3D tracked object from People Tracking demo (TLV 250).

	Contains position, velocity, and acceleration for each tracked target.
	Track IDs are persistent across frames until the target is lost.
	"""
	track_id: int
	x: float           # X position (meters)
	y: float           # Y position (meters)
	z: float           # Z position (meters)
	vx: float          # X velocity (m/s)
	vy: float          # Y velocity (m/s)
	vz: float          # Z velocity (m/s)
	ax: float          # X acceleration (m/s²)
	ay: float          # Y acceleration (m/s²)
	az: float          # Z acceleration (m/s²)

	@property
	def range(self) -> float:
		"""Distance from radar."""
		return np.sqrt(self.x**2 + self.y**2 + self.z**2)

	@property
	def speed(self) -> float:
		"""Magnitude of velocity vector."""
		return np.sqrt(self.vx**2 + self.vy**2 + self.vz**2)

	@classmethod
	def from_bytes(cls, data: bytes, offset: int = 0) -> TrackedObject | None:
		"""Parse single tracked object from raw bytes.

		Format (40 bytes per object):
		- uint32: track_id
		- float32: x, y, z (position in meters)
		- float32: vx, vy, vz (velocity in m/s)
		- float32: ax, ay, az (acceleration in m/s²)
		"""
		if len(data) < offset + 40:
			return None
		try:
			values = struct.unpack("<I9f", data[offset:offset + 40])
			return cls(
				track_id=values[0],
				x=values[1], y=values[2], z=values[3],
				vx=values[4], vy=values[5], vz=values[6],
				ax=values[7], ay=values[8], az=values[9],
			)
		except struct.error:
			return None


@dataclass
class TrackedObjectList:
	"""Container for tracked objects from TLV 250."""
	objects: list[TrackedObject]
	num_objects: int

	@classmethod
	def from_bytes(cls, data: bytes) -> TrackedObjectList | None:
		"""Parse tracked objects TLV from raw bytes."""
		if len(data) < 4:
			return None
		try:
			# First 4 bytes may be header with object count
			# Object size is 40 bytes
			object_size = 40
			num_objects = len(data) // object_size

			objects = []
			for i in range(num_objects):
				obj = TrackedObject.from_bytes(data, i * object_size)
				if obj:
					objects.append(obj)

			return cls(objects=objects, num_objects=len(objects))
		except struct.error:
			return None


@dataclass
class TargetIndex:
	"""Point-to-track association from TLV 252.

	Maps each detected point to a tracked object ID.
	"""
	indices: list[int]  # Track ID for each detected point (-1 if unassigned)

	@classmethod
	def from_bytes(cls, data: bytes, num_points: int) -> TargetIndex | None:
		"""Parse target index TLV from raw bytes."""
		if len(data) < num_points:
			return None
		try:
			# Each point has a 1-byte track index (255 = unassigned)
			indices = []
			for i in range(min(num_points, len(data))):
				idx = data[i]
				indices.append(-1 if idx == 255 else idx)
			return cls(indices=indices)
		except (struct.error, IndexError):
			return None


@dataclass
class CompressedPoint:
	"""Compressed point in spherical coordinates from TLV 253.

	Points are stored in a compressed format using 8 bytes per point:
	- elevation: int8 scaled
	- azimuth: int8 scaled
	- doppler: int16 scaled
	- range: uint16 scaled
	- snr: uint16 scaled
	"""
	elevation: float   # Elevation angle (degrees)
	azimuth: float     # Azimuth angle (degrees)
	doppler: float     # Doppler velocity (m/s)
	range_m: float     # Range (meters)
	snr: float         # SNR (dB)

	# Scaling factors from TI documentation
	ELEVATION_UNIT = 180.0 / 128.0  # degrees per unit
	AZIMUTH_UNIT = 180.0 / 128.0    # degrees per unit
	DOPPLER_UNIT = 0.01             # m/s per unit
	RANGE_UNIT = 0.01               # meters per unit
	SNR_UNIT = 0.1                  # dB per unit

	@classmethod
	def from_bytes(cls, data: bytes, offset: int = 0) -> CompressedPoint | None:
		"""Parse single compressed point (8 bytes)."""
		if len(data) < offset + 8:
			return None
		try:
			elev_raw, azim_raw, doppler_raw, range_raw, snr_raw = struct.unpack(
				"<bbhHH", data[offset:offset + 8]
			)
			return cls(
				elevation=elev_raw * cls.ELEVATION_UNIT,
				azimuth=azim_raw * cls.AZIMUTH_UNIT,
				doppler=doppler_raw * cls.DOPPLER_UNIT,
				range_m=range_raw * cls.RANGE_UNIT,
				snr=snr_raw * cls.SNR_UNIT,
			)
		except struct.error:
			return None

	def to_cartesian(self) -> tuple[float, float, float]:
		"""Convert spherical coordinates to Cartesian (x, y, z)."""
		elev_rad = np.radians(self.elevation)
		azim_rad = np.radians(self.azimuth)
		r = self.range_m

		x = r * np.cos(elev_rad) * np.sin(azim_rad)
		y = r * np.cos(elev_rad) * np.cos(azim_rad)
		z = r * np.sin(elev_rad)
		return (x, y, z)


@dataclass
class CompressedPointCloud:
	"""Container for compressed point cloud from TLV 253."""
	points: list[CompressedPoint]

	@classmethod
	def from_bytes(cls, data: bytes) -> CompressedPointCloud | None:
		"""Parse compressed point cloud TLV from raw bytes."""
		point_size = 8
		num_points = len(data) // point_size
		points = []

		for i in range(num_points):
			pt = CompressedPoint.from_bytes(data, i * point_size)
			if pt:
				points.append(pt)

		return cls(points=points)


@dataclass
class PresenceIndicationTLV:
	"""Presence indication from TLV 254.

	Simple presence detection result indicating if a target is detected.
	"""
	presence_detected: bool
	num_occupants: int = 0
	power_metric: float = 0.0

	@classmethod
	def from_bytes(cls, data: bytes) -> PresenceIndicationTLV | None:
		"""Parse presence indication TLV from raw bytes."""
		if len(data) < 4:
			return None
		try:
			# Format varies by firmware version
			# Common format: uint32 presence flag
			presence_flag = struct.unpack("<I", data[0:4])[0]
			num_occupants = 0
			power_metric = 0.0

			# Extended format with occupant count and power
			if len(data) >= 12:
				num_occupants, power_raw = struct.unpack("<If", data[4:12])
				power_metric = power_raw

			return cls(
				presence_detected=presence_flag > 0,
				num_occupants=num_occupants,
				power_metric=power_metric,
			)
		except struct.error:
			return None


@dataclass
class PointSideInfo:
	"""Side information for a detected point from TLV 7.

	Contains SNR and noise floor for each detected point.
	"""
	snr: float         # SNR in dB
	noise: float       # Noise floor

	@classmethod
	def from_bytes(cls, data: bytes, offset: int = 0) -> PointSideInfo | None:
		"""Parse single point side info (4 bytes)."""
		if len(data) < offset + 4:
			return None
		try:
			snr_raw, noise_raw = struct.unpack("<HH", data[offset:offset + 4])
			# Convert from Q8.8 fixed point to float
			return cls(
				snr=snr_raw * 0.1,  # Typically 0.1 dB per unit
				noise=float(noise_raw),
			)
		except struct.error:
			return None


@dataclass
class PointsSideInfo:
	"""Container for point side info from TLV 7."""
	info: list[PointSideInfo]

	@classmethod
	def from_bytes(cls, data: bytes) -> PointsSideInfo | None:
		"""Parse points side info TLV from raw bytes."""
		info_size = 4
		num_points = len(data) // info_size
		info = []

		for i in range(num_points):
			si = PointSideInfo.from_bytes(data, i * info_size)
			if si:
				info.append(si)

		return cls(info=info)


@dataclass
class TemperatureStats:
	"""Temperature statistics from TLV 9."""
	temp_report: int      # Temperature report ID
	time_stamp: int       # Timestamp
	tmp_rx0_sens: float   # RX0 sensor temperature (°C)
	tmp_rx1_sens: float   # RX1 sensor temperature (°C)
	tmp_rx2_sens: float   # RX2 sensor temperature (°C)
	tmp_rx3_sens: float   # RX3 sensor temperature (°C)
	tmp_tx0_sens: float   # TX0 sensor temperature (°C)
	tmp_tx1_sens: float   # TX1 sensor temperature (°C)
	tmp_tx2_sens: float   # TX2 sensor temperature (°C)
	tmp_pm_sens: float    # PM sensor temperature (°C)
	tmp_dig0_sens: float  # Digital0 sensor temperature (°C)
	tmp_dig1_sens: float  # Digital1 sensor temperature (°C)

	@classmethod
	def from_bytes(cls, data: bytes) -> TemperatureStats | None:
		"""Parse temperature stats TLV from raw bytes."""
		if len(data) < 48:
			return None
		try:
			values = struct.unpack("<II10f", data[0:48])
			return cls(
				temp_report=values[0],
				time_stamp=values[1],
				tmp_rx0_sens=values[2],
				tmp_rx1_sens=values[3],
				tmp_rx2_sens=values[4],
				tmp_rx3_sens=values[5],
				tmp_tx0_sens=values[6],
				tmp_tx1_sens=values[7],
				tmp_tx2_sens=values[8],
				tmp_pm_sens=values[9],
				tmp_dig0_sens=values[10],
				tmp_dig1_sens=values[11],
			)
		except struct.error:
			return None

	@property
	def max_temperature(self) -> float:
		"""Get maximum sensor temperature."""
		temps = [
			self.tmp_rx0_sens, self.tmp_rx1_sens, self.tmp_rx2_sens, self.tmp_rx3_sens,
			self.tmp_tx0_sens, self.tmp_tx1_sens, self.tmp_tx2_sens,
			self.tmp_pm_sens, self.tmp_dig0_sens, self.tmp_dig1_sens,
		]
		return max(temps)


@dataclass
class AzimuthHeatmap:
	"""Azimuth static heatmap from TLV 4."""
	data: NDArray[np.float32]
	num_range_bins: int
	num_angle_bins: int

	@classmethod
	def from_bytes(cls, data: bytes, num_range_bins: int = 256) -> AzimuthHeatmap | None:
		"""Parse azimuth heatmap TLV from raw bytes."""
		if len(data) < 4:
			return None
		try:
			# Each value is uint16, convert to dB
			num_values = len(data) // 2
			values = struct.unpack(f"<{num_values}H", data)
			arr = np.array(values, dtype=np.float32)
			arr_db = 20 * np.log10(arr + 1)

			# Try to reshape to (range_bins, angle_bins)
			num_angle_bins = num_values // num_range_bins
			if num_range_bins * num_angle_bins == num_values:
				arr_db = arr_db.reshape((num_range_bins, num_angle_bins))
			else:
				# Fallback: use square if possible
				side = int(np.sqrt(num_values))
				if side * side == num_values:
					num_range_bins = side
					num_angle_bins = side
					arr_db = arr_db.reshape((side, side))

			return cls(
				data=arr_db,
				num_range_bins=num_range_bins,
				num_angle_bins=num_angle_bins,
			)
		except struct.error:
			return None


@dataclass
class AzimuthElevationHeatmap:
	"""Azimuth-elevation heatmap from TLV 8."""
	data: NDArray[np.float32]
	num_azimuth_bins: int
	num_elevation_bins: int

	@classmethod
	def from_bytes(cls, data: bytes) -> AzimuthElevationHeatmap | None:
		"""Parse azimuth-elevation heatmap TLV from raw bytes."""
		if len(data) < 4:
			return None
		try:
			# Each value is uint16, convert to dB
			num_values = len(data) // 2
			values = struct.unpack(f"<{num_values}H", data)
			arr = np.array(values, dtype=np.float32)
			arr_db = 20 * np.log10(arr + 1)

			# Try to reshape to square matrix
			side = int(np.sqrt(num_values))
			if side * side == num_values:
				arr_db = arr_db.reshape((side, side))
				return cls(
					data=arr_db,
					num_azimuth_bins=side,
					num_elevation_bins=side,
				)
			return cls(
				data=arr_db.reshape((1, -1)),
				num_azimuth_bins=num_values,
				num_elevation_bins=1,
			)
		except struct.error:
			return None


@dataclass
class GestureFeatures:
	"""Gesture features from TLV 1010."""
	features: NDArray[np.float32]
	num_features: int

	@classmethod
	def from_bytes(cls, data: bytes) -> GestureFeatures | None:
		"""Parse gesture features TLV from raw bytes."""
		if len(data) < 4:
			return None
		try:
			num_features = len(data) // 4
			features = np.array(
				struct.unpack(f"<{num_features}f", data),
				dtype=np.float32
			)
			return cls(features=features, num_features=num_features)
		except struct.error:
			return None


@dataclass
class GestureOutput:
	"""Gesture classification output from TLV 1020."""
	gesture_id: int
	confidence: float
	gesture_name: str = ""

	GESTURE_NAMES = {
		0: "none",
		1: "swipe_left",
		2: "swipe_right",
		3: "swipe_up",
		4: "swipe_down",
		5: "spin_cw",
		6: "spin_ccw",
		7: "push",
		8: "pull",
	}

	@classmethod
	def from_bytes(cls, data: bytes) -> GestureOutput | None:
		"""Parse gesture output TLV from raw bytes."""
		if len(data) < 8:
			return None
		try:
			gesture_id, confidence = struct.unpack("<If", data[0:8])
			gesture_name = cls.GESTURE_NAMES.get(gesture_id, f"unknown_{gesture_id}")
			return cls(
				gesture_id=gesture_id,
				confidence=confidence,
				gesture_name=gesture_name,
			)
		except struct.error:
			return None


# =============================================================================
# Standard Data Types
# =============================================================================


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

	# Tracking TLVs (People Tracking demo)
	tracked_objects: TrackedObjectList | None = None
	target_index: TargetIndex | None = None
	compressed_points: CompressedPointCloud | None = None
	presence_indication: PresenceIndicationTLV | None = None

	# Additional TLVs
	points_side_info: PointsSideInfo | None = None
	temperature_stats: TemperatureStats | None = None
	azimuth_heatmap: AzimuthHeatmap | None = None
	azimuth_elevation_heatmap: AzimuthElevationHeatmap | None = None

	# Gesture TLVs
	gesture_features: GestureFeatures | None = None
	gesture_output: GestureOutput | None = None

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

			# Standard TLVs
			if tlv_type == TLV_DETECTED_POINTS:
				frame.detected_points = _parse_points(tlv_data)
			elif tlv_type == TLV_RANGE_PROFILE:
				frame.range_profile = _parse_range_profile(tlv_data)
			elif tlv_type == TLV_RANGE_DOPPLER:
				frame.range_doppler_heatmap = _parse_range_doppler(tlv_data)
			elif tlv_type == TLV_VITAL_SIGNS:
				frame.vital_signs = VitalSignsTLV.from_bytes(tlv_data)
			elif tlv_type == TLV_DETECTED_POINTS_SIDE_INFO:
				frame.points_side_info = PointsSideInfo.from_bytes(tlv_data)
			elif tlv_type == TLV_TEMPERATURE_STATS:
				frame.temperature_stats = TemperatureStats.from_bytes(tlv_data)
			elif tlv_type == TLV_AZIMUTH_STATIC_HEATMAP:
				frame.azimuth_heatmap = AzimuthHeatmap.from_bytes(tlv_data)
			elif tlv_type == TLV_AZIMUTH_ELEVATION_HEATMAP:
				frame.azimuth_elevation_heatmap = AzimuthElevationHeatmap.from_bytes(tlv_data)

			# Tracking TLVs
			elif tlv_type == TLV_TRACKED_OBJECTS:
				frame.tracked_objects = TrackedObjectList.from_bytes(tlv_data)
			elif tlv_type == TLV_TARGET_INDEX:
				num_points = len(frame.detected_points)
				frame.target_index = TargetIndex.from_bytes(tlv_data, num_points)
			elif tlv_type == TLV_COMPRESSED_POINTS:
				frame.compressed_points = CompressedPointCloud.from_bytes(tlv_data)
			elif tlv_type == TLV_PRESENCE_INDICATION:
				frame.presence_indication = PresenceIndicationTLV.from_bytes(tlv_data)

			# Gesture TLVs
			elif tlv_type == TLV_GESTURE_FEATURES:
				frame.gesture_features = GestureFeatures.from_bytes(tlv_data)
			elif tlv_type == TLV_GESTURE_OUTPUT:
				frame.gesture_output = GestureOutput.from_bytes(tlv_data)

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

		# Apply side info to detected points if available
		if frame.points_side_info and frame.detected_points:
			for i, pt in enumerate(frame.detected_points):
				if i < len(frame.points_side_info.info):
					pt.snr = frame.points_side_info.info[i].snr
					pt.noise = frame.points_side_info.info[i].noise

		return frame


class FrameBuffer:
	"""Accumulates serial data and extracts complete frames."""

	def __init__(self, max_size: int = 65536):
		self._buffer = bytearray()
		self._max_size = max_size

	def append(self, data: bytes) -> None:
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
		"""Parse frame using RadarFrame.from_bytes() to avoid duplication."""
		return RadarFrame.from_bytes(data)

	def clear(self) -> None:
		self._buffer.clear()

	def __len__(self) -> int:
		return len(self._buffer)
