"""Vital signs extraction from radar phase data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import structlog
from numpy.typing import NDArray

from ambient.vitals.filters import BandpassFilter
from ambient.vitals.heart_rate import HeartRateEstimator
from ambient.vitals.respiratory import RespiratoryRateEstimator

if TYPE_CHECKING:
	from ambient.processing.pipeline import ProcessedFrame

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

		motion_metric = np.std(np.diff(phase_signal))
		result.motion_detected = bool(motion_metric > self.config.motion_threshold)
		if result.motion_detected:
			return result

		hr_filtered = self._hr_filter.process(phase_signal)
		result.heart_rate_waveform = hr_filtered

		rr_filtered = self._rr_filter.process(phase_signal)
		result.respiratory_waveform = rr_filtered

		hr, hr_conf = self._hr_estimator.estimate(hr_filtered)
		result.heart_rate_bpm = hr
		result.heart_rate_confidence = hr_conf

		rr, rr_conf = self._rr_estimator.estimate(rr_filtered)
		result.respiratory_rate_bpm = rr
		result.respiratory_rate_confidence = rr_conf

		result.signal_quality = (hr_conf + rr_conf) / 2
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
