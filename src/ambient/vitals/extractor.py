"""Vital signs extraction from radar phase data."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import structlog
from numpy.typing import NDArray

from ambient.vitals.filters import BandpassFilter, PhaseUnwrapper
from ambient.vitals.heart_rate import HeartRateEstimator
from ambient.vitals.respiratory import RespiratoryRateEstimator

if TYPE_CHECKING:
	from ambient.processing.pipeline import ProcessedFrame
	from ambient.sensor.frame import ChirpPhaseOutput, RadarFrame, VitalSignsTLV

logger = structlog.get_logger(__name__)


@dataclass
class VitalSigns:
	heart_rate_bpm: float | None = None
	heart_rate_confidence: float = 0.0
	heart_rate_waveform: NDArray[np.float32] | None = None
	respiratory_rate_bpm: float | None = None
	respiratory_rate_confidence: float = 0.0
	respiratory_waveform: NDArray[np.float32] | None = None
	phase_signal: NDArray[np.float32] | None = None
	signal_quality: float = 0.0
	motion_detected: bool = False
	timestamp: float = 0.0
	source: str = "estimated"  # "firmware", "estimated", or "chirp"
	unwrapped_phase: float | None = None
	# Enhanced quality metrics
	hr_snr_db: float = 0.0
	rr_snr_db: float = 0.0
	phase_stability: float = 0.0  # Lower = more stable

	def is_valid(self, min_confidence: float = 0.5) -> bool:
		hr_ok = (
			self.heart_rate_bpm is not None
			and 30 <= self.heart_rate_bpm <= 200
			and self.heart_rate_confidence >= min_confidence
		)
		rr_ok = (
			self.respiratory_rate_bpm is not None
			and 4 <= self.respiratory_rate_bpm <= 40
			and self.respiratory_rate_confidence >= min_confidence
		)
		return hr_ok and rr_ok

	def quality_summary(self) -> str:
		"""Human-readable quality assessment."""
		if self.signal_quality >= 0.8:
			level = "excellent"
		elif self.signal_quality >= 0.6:
			level = "good"
		elif self.signal_quality >= 0.4:
			level = "fair"
		else:
			level = "poor"
		return f"{level} ({self.signal_quality:.0%})"

	@classmethod
	def from_firmware(cls, vital_signs_tlv, timestamp: float = 0.0) -> VitalSigns:
		"""Create VitalSigns from firmware-provided VitalSignsTLV data."""
		return cls(
			heart_rate_bpm=vital_signs_tlv.heart_rate,
			heart_rate_confidence=vital_signs_tlv.heart_confidence,
			heart_rate_waveform=vital_signs_tlv.heart_waveform,
			respiratory_rate_bpm=vital_signs_tlv.breathing_rate,
			respiratory_rate_confidence=vital_signs_tlv.breathing_confidence,
			respiratory_waveform=vital_signs_tlv.breathing_waveform,
			signal_quality=(vital_signs_tlv.heart_confidence + vital_signs_tlv.breathing_confidence) / 2,
			motion_detected=False,
			timestamp=timestamp,
			source="firmware",
			unwrapped_phase=vital_signs_tlv.unwrapped_phase,
		)


@dataclass
class VitalsConfig:
	sample_rate_hz: float = 20.0
	window_seconds: float = 10.0
	hr_freq_min_hz: float = 0.8   # ~48 BPM
	hr_freq_max_hz: float = 3.0   # ~180 BPM
	hr_filter_order: int = 4
	rr_freq_min_hz: float = 0.1   # ~6 BPM
	rr_freq_max_hz: float = 0.6   # ~36 BPM
	rr_filter_order: int = 4
	min_snr_db: float = 10.0
	motion_threshold: float = 0.5
	motion_skip_estimation: bool = True  # Skip HR/RR estimation during motion


class VitalsExtractor:
	"""Extract heart rate and respiratory rate from radar phase."""

	def __init__(self, config: VitalsConfig | None = None) -> None:
		self.config = config or VitalsConfig()
		self._buffer_size = int(self.config.window_seconds * self.config.sample_rate_hz)
		self._phase_buffer: list[float] = []
		self._timestamp_buffer: list[float] = []

		self._hr_estimator = HeartRateEstimator(
			sample_rate_hz=self.config.sample_rate_hz,
			freq_min_hz=self.config.hr_freq_min_hz,
			freq_max_hz=self.config.hr_freq_max_hz,
		)
		self._rr_estimator = RespiratoryRateEstimator(
			sample_rate_hz=self.config.sample_rate_hz,
			freq_min_hz=self.config.rr_freq_min_hz,
			freq_max_hz=self.config.rr_freq_max_hz,
		)
		self._hr_filter = BandpassFilter(
			sample_rate_hz=self.config.sample_rate_hz,
			low_freq_hz=self.config.hr_freq_min_hz,
			high_freq_hz=self.config.hr_freq_max_hz,
			order=self.config.hr_filter_order,
		)
		self._rr_filter = BandpassFilter(
			sample_rate_hz=self.config.sample_rate_hz,
			low_freq_hz=self.config.rr_freq_min_hz,
			high_freq_hz=self.config.rr_freq_max_hz,
			order=self.config.rr_filter_order,
		)
		logger.info("vitals_extractor_init", sample_rate=self.config.sample_rate_hz)

	def process(self, phase_data: NDArray[np.float32] | float | None, timestamp: float = 0.0) -> VitalSigns:
		result = VitalSigns(timestamp=timestamp)

		if phase_data is None:
			return result

		phase = float(phase_data.mean()) if isinstance(phase_data, np.ndarray) else float(phase_data)

		self._phase_buffer.append(phase)
		self._timestamp_buffer.append(timestamp)

		if len(self._phase_buffer) > self._buffer_size:
			self._phase_buffer = self._phase_buffer[-self._buffer_size:]
			self._timestamp_buffer = self._timestamp_buffer[-self._buffer_size:]

		min_samples = int(self.config.sample_rate_hz * 5)
		if len(self._phase_buffer) < min_samples:
			return result

		phase_signal = np.array(self._phase_buffer, dtype=np.float32)
		result.phase_signal = phase_signal

		# Calculate phase stability (variance of phase deltas)
		phase_deltas = np.diff(phase_signal)
		result.phase_stability = float(np.std(phase_deltas))

		motion_metric = result.phase_stability
		result.motion_detected = bool(motion_metric > self.config.motion_threshold)
		if result.motion_detected:
			return result

		hr_filtered = self._hr_filter.process(phase_signal)
		result.heart_rate_waveform = hr_filtered

		rr_filtered = self._rr_filter.process(phase_signal)
		result.respiratory_waveform = rr_filtered

		# Use enhanced estimation with quality metrics
		hr_result = self._hr_estimator.estimate_with_quality(hr_filtered)
		result.heart_rate_bpm = hr_result.rate_bpm
		result.heart_rate_confidence = hr_result.confidence
		result.hr_snr_db = hr_result.snr_db

		rr, rr_conf = self._rr_estimator.estimate(rr_filtered)
		result.respiratory_rate_bpm = rr
		result.respiratory_rate_confidence = rr_conf

		# Combine confidences with SNR weighting for overall quality
		base_quality = (hr_result.confidence + rr_conf) / 2
		# Boost quality if SNR is good
		snr_bonus = min(0.1, hr_result.snr_db / 100) if hr_result.snr_db > 0 else 0
		result.signal_quality = min(1.0, base_quality + snr_bonus)
		return result

	def process_frame(self, frame: ProcessedFrame) -> VitalSigns:
		return self.process(frame.phase_data, frame.timestamp)

	def reset(self) -> None:
		self._phase_buffer.clear()
		self._timestamp_buffer.clear()
		self._hr_estimator.reset()
		self._rr_estimator.reset()
		self._hr_filter.reset()
		self._rr_filter.reset()
		logger.info("vitals_extractor_reset")

	@property
	def buffer_fullness(self) -> float:
		return len(self._phase_buffer) / self._buffer_size


class ChirpVitalsProcessor:
	"""Vital signs extraction from chirp firmware PHASE_OUTPUT TLV.

	This processor is designed for use with chirp firmware's PHASE output
	mode (TLV 0x0520), which provides pre-computed phase and magnitude
	for selected target bins.

	Example:
		processor = ChirpVitalsProcessor()
		for frame in frame_stream:
			if frame.chirp_phase:
				vitals = processor.process_chirp_phase(frame.chirp_phase)
				if vitals.is_valid():
					print(f"HR: {vitals.heart_rate_bpm:.1f} BPM")
	"""

	def __init__(self, config: VitalsConfig | None = None) -> None:
		self.config = config or VitalsConfig()
		self._buffer_size = int(self.config.window_seconds * self.config.sample_rate_hz)

		# Phase tracking
		self._unwrapper = PhaseUnwrapper()
		self._phase_buffer: list[float] = []
		self._timestamp_buffer: list[float] = []
		self._magnitude_buffer: list[float] = []

		# Rate estimators
		self._hr_estimator = HeartRateEstimator(
			sample_rate_hz=self.config.sample_rate_hz,
			freq_min_hz=self.config.hr_freq_min_hz,
			freq_max_hz=self.config.hr_freq_max_hz,
		)
		self._rr_estimator = RespiratoryRateEstimator(
			sample_rate_hz=self.config.sample_rate_hz,
			freq_min_hz=self.config.rr_freq_min_hz,
			freq_max_hz=self.config.rr_freq_max_hz,
		)

		# Bandpass filters
		self._hr_filter = BandpassFilter(
			sample_rate_hz=self.config.sample_rate_hz,
			low_freq_hz=self.config.hr_freq_min_hz,
			high_freq_hz=self.config.hr_freq_max_hz,
			order=self.config.hr_filter_order,
		)
		self._rr_filter = BandpassFilter(
			sample_rate_hz=self.config.sample_rate_hz,
			low_freq_hz=self.config.rr_freq_min_hz,
			high_freq_hz=self.config.rr_freq_max_hz,
			order=self.config.rr_filter_order,
		)
		logger.info(
			"chirp_vitals_processor_init",
			sample_rate=self.config.sample_rate_hz,
			window_seconds=self.config.window_seconds,
		)

	def process_chirp_phase(
		self, phase_output: ChirpPhaseOutput, timestamp: float | None = None
	) -> VitalSigns:
		"""Process a chirp PHASE_OUTPUT TLV and extract vital signs.

		Args:
			phase_output: Parsed ChirpPhaseOutput from frame
			timestamp: Optional timestamp (uses phase_output.timestamp_us if not provided)

		Returns:
			VitalSigns with extracted heart rate and respiratory rate
		"""
		if timestamp is None:
			timestamp = phase_output.timestamp_us / 1_000_000.0

		result = VitalSigns(timestamp=timestamp, source="chirp")

		# Get phase from center bin
		phase = phase_output.get_center_phase()
		if phase is None:
			return result

		# Check for motion - require majority of valid bins to report motion
		valid_bins = [b for b in phase_output.bins if b.is_valid]
		motion_count = sum(1 for b in valid_bins if b.has_motion)
		has_motion = motion_count > len(valid_bins) // 2 if valid_bins else False
		result.motion_detected = has_motion

		# Skip estimation during motion (configurable)
		if has_motion and self.config.motion_skip_estimation:
			return result

		# Compute average magnitude for signal quality
		if valid_bins:
			avg_magnitude = sum(b.magnitude for b in valid_bins) / len(valid_bins)
			self._magnitude_buffer.append(avg_magnitude)
			if len(self._magnitude_buffer) > self._buffer_size:
				self._magnitude_buffer = self._magnitude_buffer[-self._buffer_size:]

		# Unwrap phase and buffer
		unwrapped = self._unwrapper.unwrap_sample(phase)
		result.unwrapped_phase = unwrapped

		self._phase_buffer.append(unwrapped)
		self._timestamp_buffer.append(timestamp)

		if len(self._phase_buffer) > self._buffer_size:
			self._phase_buffer = self._phase_buffer[-self._buffer_size:]
			self._timestamp_buffer = self._timestamp_buffer[-self._buffer_size:]

		# Need minimum samples
		min_samples = int(self.config.sample_rate_hz * 5)
		if len(self._phase_buffer) < min_samples:
			return result

		# Extract phase signal
		phase_signal = np.array(self._phase_buffer, dtype=np.float32)
		result.phase_signal = phase_signal

		# Filter for heart rate and respiratory bands
		hr_filtered = self._hr_filter.process(phase_signal)
		result.heart_rate_waveform = hr_filtered

		rr_filtered = self._rr_filter.process(phase_signal)
		result.respiratory_waveform = rr_filtered

		# Calculate phase stability (variance of phase deltas)
		phase_deltas = np.diff(phase_signal)
		result.phase_stability = float(np.std(phase_deltas))

		# Use enhanced estimation with quality metrics
		hr_result = self._hr_estimator.estimate_with_quality(hr_filtered)
		result.heart_rate_bpm = hr_result.rate_bpm
		result.heart_rate_confidence = hr_result.confidence
		result.hr_snr_db = hr_result.snr_db

		rr_result = self._rr_estimator.estimate_with_quality(rr_filtered)
		result.respiratory_rate_bpm = rr_result.rate_bpm
		result.respiratory_rate_confidence = rr_result.confidence
		result.rr_snr_db = rr_result.snr_db

		# Combine confidences with SNR weighting for overall quality
		base_quality = (hr_result.confidence + rr_result.confidence) / 2
		# Boost quality if SNR is good
		snr_bonus = min(0.1, hr_result.snr_db / 100) if hr_result.snr_db > 0 else 0
		# Soft penalty for high phase instability (motion)
		stability_penalty = max(0, (result.phase_stability - self.config.motion_threshold) * 0.5)
		result.signal_quality = max(0, min(1.0, base_quality + snr_bonus - stability_penalty))
		return result

	def process_frame(self, frame: RadarFrame) -> VitalSigns | None:
		"""Process a RadarFrame containing chirp TLVs.

		Args:
			frame: RadarFrame with parsed chirp TLVs

		Returns:
			VitalSigns if chirp_phase is present, None otherwise
		"""
		if frame.chirp_phase is None:
			return None
		return self.process_chirp_phase(frame.chirp_phase, frame.timestamp)

	def reset(self) -> None:
		"""Reset processor state."""
		self._phase_buffer.clear()
		self._timestamp_buffer.clear()
		self._magnitude_buffer.clear()
		self._unwrapper.reset()
		self._hr_estimator.reset()
		self._rr_estimator.reset()
		self._hr_filter.reset()
		self._rr_filter.reset()
		logger.info("chirp_vitals_processor_reset")

	@property
	def buffer_fullness(self) -> float:
		"""Fraction of buffer filled (0.0 to 1.0)."""
		return len(self._phase_buffer) / self._buffer_size

	@property
	def is_ready(self) -> bool:
		"""True when enough samples collected for estimation."""
		min_samples = int(self.config.sample_rate_hz * 5)
		return len(self._phase_buffer) >= min_samples

	def update_sample_rate(self, new_rate_hz: float) -> None:
		"""Update sample rate and reinitialize components.

		This clears buffers and recreates filters/estimators with the new rate.
		"""
		if abs(new_rate_hz - self.config.sample_rate_hz) < 0.01:
			return  # No significant change

		old_rate = self.config.sample_rate_hz
		self.config.sample_rate_hz = new_rate_hz
		self._buffer_size = int(self.config.window_seconds * new_rate_hz)

		# Recreate estimators with new sample rate
		self._hr_estimator = HeartRateEstimator(
			sample_rate_hz=new_rate_hz,
			freq_min_hz=self.config.hr_freq_min_hz,
			freq_max_hz=self.config.hr_freq_max_hz,
		)
		self._rr_estimator = RespiratoryRateEstimator(
			sample_rate_hz=new_rate_hz,
			freq_min_hz=self.config.rr_freq_min_hz,
			freq_max_hz=self.config.rr_freq_max_hz,
		)

		# Recreate filters with new sample rate
		self._hr_filter = BandpassFilter(
			sample_rate_hz=new_rate_hz,
			low_freq_hz=self.config.hr_freq_min_hz,
			high_freq_hz=self.config.hr_freq_max_hz,
			order=self.config.hr_filter_order,
		)
		self._rr_filter = BandpassFilter(
			sample_rate_hz=new_rate_hz,
			low_freq_hz=self.config.rr_freq_min_hz,
			high_freq_hz=self.config.rr_freq_max_hz,
			order=self.config.rr_filter_order,
		)

		# Clear buffers (old data collected at different rate)
		self._phase_buffer.clear()
		self._timestamp_buffer.clear()
		self._magnitude_buffer.clear()
		self._unwrapper.reset()

		logger.info(
			"chirp_vitals_sample_rate_updated",
			old_rate=old_rate,
			new_rate=new_rate_hz,
		)


# =============================================================================
# Multi-Patient Vital Signs Support (TI Algorithm)
# =============================================================================


@dataclass
class PatientVitals:
	"""Vital signs data for a single patient with history tracking.

	Implements TI's multi-patient vital signs tracking algorithm with:
	- Waveform history for visualization (150 samples)
	- 10-sample median filter for heart rate smoothing
	- Patient status detection based on breathing deviation
	"""
	patient_id: int
	range_bin: int = 0

	# Current values
	heart_rate_bpm: float | None = None
	breathing_rate_bpm: float | None = None
	breathing_deviation: float = 0.0

	# Status: 'present', 'holding_breath', 'not_detected'
	status: str = "not_detected"

	# Waveform history for plotting (deques for efficient appending)
	heart_waveform: deque = field(default_factory=lambda: deque(maxlen=150))
	breath_waveform: deque = field(default_factory=lambda: deque(maxlen=150))

	# Heart rate median filter history (TI uses 10-sample median)
	_hr_history: deque = field(default_factory=lambda: deque(maxlen=10))

	# Breathing deviation threshold (from TI documentation)
	BREATHING_DEVIATION_PRESENT = 0.02

	def update_from_tlv(self, tlv: VitalSignsTLV) -> None:
		"""Update patient data from parsed Vital Signs TLV.

		Implements TI's status detection and median filtering algorithm.

		Args:
			tlv: Parsed VitalSignsTLV from frame
		"""
		self.range_bin = tlv.range_bin_index
		self.breathing_deviation = tlv.breathing_deviation

		# Extend waveforms with new samples
		self.heart_waveform.extend(tlv.heart_waveform.tolist())
		self.breath_waveform.extend(tlv.breathing_waveform.tolist())

		# Update status based on breathing deviation (TI algorithm)
		if tlv.breathing_deviation == 0:
			self.status = "not_detected"
			self.heart_rate_bpm = None
			self.breathing_rate_bpm = None
		elif tlv.breathing_deviation >= self.BREATHING_DEVIATION_PRESENT:
			self.status = "present"
			self.breathing_rate_bpm = tlv.breathing_rate if tlv.breathing_rate > 0 else None

			# Median filter for heart rate (TI uses 10-sample window)
			if tlv.heart_rate > 0:
				self._hr_history.append(tlv.heart_rate)
				self.heart_rate_bpm = self._compute_median(list(self._hr_history))
		else:
			self.status = "holding_breath"
			self.breathing_rate_bpm = None
			# Still update heart rate during breath hold
			if tlv.heart_rate > 0:
				self._hr_history.append(tlv.heart_rate)
				self.heart_rate_bpm = self._compute_median(list(self._hr_history))

	@staticmethod
	def _compute_median(values: list[float]) -> float:
		"""Compute median of values."""
		if not values:
			return 0.0
		sorted_vals = sorted(values)
		n = len(sorted_vals)
		if n % 2 == 0:
			return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
		return sorted_vals[n // 2]

	def to_dict(self) -> dict:
		"""Convert to dictionary for JSON serialization."""
		return {
			"patient_id": self.patient_id,
			"status": self.status,
			"heart_rate_bpm": self.heart_rate_bpm,
			"breathing_rate_bpm": self.breathing_rate_bpm,
			"breathing_deviation": self.breathing_deviation,
			"range_bin": self.range_bin,
			"heart_waveform": list(self.heart_waveform)[-15:],  # Last 15 samples
			"breath_waveform": list(self.breath_waveform)[-15:],
		}

	def reset(self) -> None:
		"""Reset patient state."""
		self.range_bin = 0
		self.heart_rate_bpm = None
		self.breathing_rate_bpm = None
		self.breathing_deviation = 0.0
		self.status = "not_detected"
		self.heart_waveform.clear()
		self.breath_waveform.clear()
		self._hr_history.clear()


class MultiPatientVitalsManager:
	"""Manages vital signs for multiple patients (TI algorithm).

	TI's visualizer supports up to 2 patients simultaneously.
	This manager handles:
	- Patient slot allocation and tracking
	- Status updates from Vital Signs TLV (1040)
	- Aggregated vitals output for WebSocket broadcast

	Example:
		manager = MultiPatientVitalsManager(max_patients=2)

		for frame in frame_stream:
			if frame.vital_signs:
				manager.update(frame.vital_signs)

		# Get all patient vitals for broadcast
		all_vitals = manager.get_all_vitals()
	"""

	MAX_PATIENTS = 2  # TI supports up to 2 patients

	def __init__(self, max_patients: int = 2) -> None:
		"""Initialize multi-patient manager.

		Args:
			max_patients: Maximum number of patients to track (1-2)
		"""
		self.max_patients = min(max_patients, self.MAX_PATIENTS)
		self.patients: dict[int, PatientVitals] = {}

		# Initialize patient slots
		for i in range(self.max_patients):
			self.patients[i] = PatientVitals(patient_id=i)

		logger.info(
			"multi_patient_manager_init",
			max_patients=self.max_patients,
		)

	def configure(self, max_patients: int) -> None:
		"""Configure from trackingCfg command.

		Args:
			max_patients: Number of patients to track (from config)
		"""
		new_max = min(max_patients, self.MAX_PATIENTS)

		# Add new patient slots if needed
		for i in range(self.max_patients, new_max):
			if i not in self.patients:
				self.patients[i] = PatientVitals(patient_id=i)

		# Remove excess slots
		for i in list(self.patients.keys()):
			if i >= new_max:
				del self.patients[i]

		self.max_patients = new_max
		logger.info(
			"multi_patient_manager_configured",
			max_patients=self.max_patients,
		)

	def update(self, tlv: VitalSignsTLV) -> None:
		"""Update patient data from vital signs TLV.

		Args:
			tlv: Parsed VitalSignsTLV from frame
		"""
		patient_id = tlv.patient_id

		if patient_id >= self.max_patients:
			logger.warning(
				"invalid_patient_id",
				patient_id=patient_id,
				max_patients=self.max_patients,
			)
			return

		if patient_id not in self.patients:
			self.patients[patient_id] = PatientVitals(patient_id=patient_id)

		self.patients[patient_id].update_from_tlv(tlv)

	def get_patient(self, patient_id: int) -> PatientVitals | None:
		"""Get vitals for a specific patient.

		Args:
			patient_id: Patient ID (0 or 1)

		Returns:
			PatientVitals or None if not found
		"""
		return self.patients.get(patient_id)

	def get_all_vitals(self) -> list[dict]:
		"""Get vitals data for all patients (for WebSocket broadcast).

		Returns:
			List of patient vitals dictionaries
		"""
		result = []
		for i in range(self.max_patients):
			if i in self.patients:
				result.append(self.patients[i].to_dict())
		return result

	def get_primary_vitals(self) -> VitalSigns | None:
		"""Get vitals from the first detected patient.

		This is useful for single-patient mode or backwards compatibility.

		Returns:
			VitalSigns from first patient with status != 'not_detected'
		"""
		for i in range(self.max_patients):
			patient = self.patients.get(i)
			if patient and patient.status != "not_detected":
				return VitalSigns(
					heart_rate_bpm=patient.heart_rate_bpm,
					heart_rate_confidence=0.8 if patient.status == "present" else 0.5,
					heart_rate_waveform=np.array(list(patient.heart_waveform), dtype=np.float32),
					respiratory_rate_bpm=patient.breathing_rate_bpm,
					respiratory_rate_confidence=0.8 if patient.status == "present" else 0.0,
					respiratory_waveform=np.array(list(patient.breath_waveform), dtype=np.float32),
					signal_quality=0.8 if patient.status == "present" else 0.3,
					motion_detected=False,
					source="firmware",
				)
		return None

	def reset(self) -> None:
		"""Reset all patient states."""
		for patient in self.patients.values():
			patient.reset()
		logger.info("multi_patient_manager_reset")

	@property
	def active_patient_count(self) -> int:
		"""Number of currently detected patients."""
		return sum(
			1 for p in self.patients.values()
			if p.status != "not_detected"
		)
