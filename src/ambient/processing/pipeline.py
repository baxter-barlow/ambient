"""Signal processing pipeline for radar data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import structlog
from numpy.typing import NDArray

from ambient.processing.clutter import ClutterRemoval
from ambient.processing.fft import RangeDopplerProcessor

if TYPE_CHECKING:
	from ambient.sensor.frame import RadarFrame

logger = structlog.get_logger(__name__)


@dataclass
class ProcessedFrame:
	frame_number: int
	timestamp: float
	range_doppler_map: NDArray[np.float32] | None = None
	range_profile: NDArray[np.float32] | None = None
	phase_data: NDArray[np.float32] | None = None
	target_range_bin: int | None = None
	detected_ranges: list[float] = field(default_factory=list)
	detected_velocities: list[float] = field(default_factory=list)
	snr_db: float = 0.0
	noise_floor: float = 0.0


@dataclass
class PipelineConfig:
	range_fft_size: int = 256
	doppler_fft_size: int = 64
	window: str = "hann"
	clutter_removal: str = "mti"
	clutter_alpha: float = 0.1
	target_detection: bool = True
	cfar_guard_cells: int = 4
	cfar_training_cells: int = 8
	cfar_threshold_db: float = 15.0
	phase_extraction: bool = True
	target_range_min_m: float = 0.3
	target_range_max_m: float = 2.0


class ProcessingPipeline:
	"""Radar signal processing: FFT, clutter removal, target detection."""

	def __init__(self, config: PipelineConfig | None = None) -> None:
		self.config = config or PipelineConfig()

		self._range_doppler = RangeDopplerProcessor(
			range_fft_size=self.config.range_fft_size,
			doppler_fft_size=self.config.doppler_fft_size,
			window=self.config.window,
		)
		self._clutter = ClutterRemoval(
			method=self.config.clutter_removal,
			alpha=self.config.clutter_alpha,
		)
		self._target_bin: int | None = None
		self._phase_history: list[float] = []

		logger.info("pipeline_init")

	def process(self, frame: RadarFrame) -> ProcessedFrame:
		result = ProcessedFrame(
			frame_number=frame.header.frame_number if frame.header else 0,
			timestamp=frame.timestamp,
		)

		if frame.range_profile is not None:
			result.range_profile = frame.range_profile
			filtered = self._clutter.process(frame.range_profile)

			if self.config.target_detection:
				targets = self._detect_targets(filtered)
				result.detected_ranges = targets

			if self.config.phase_extraction and targets:
				result.phase_data = self._extract_phase(frame.range_profile, targets[0])
				result.target_range_bin = self._target_bin

		if frame.range_doppler_heatmap is not None:
			result.range_doppler_map = frame.range_doppler_heatmap

		if frame.detected_points:
			result.detected_ranges = [p.range for p in frame.detected_points]
			result.detected_velocities = [p.velocity for p in frame.detected_points]

		return result

	def _detect_targets(self, range_profile: NDArray) -> list[float]:
		threshold = np.mean(np.abs(range_profile)) + 3 * np.std(np.abs(range_profile))
		peaks = np.where(np.abs(range_profile) > threshold)[0]

		range_res = 0.044  # approximate
		targets = [bin_idx * range_res for bin_idx in peaks]
		return [r for r in targets if self.config.target_range_min_m <= r <= self.config.target_range_max_m]

	def _extract_phase(self, range_profile: NDArray, target_range: float) -> NDArray:
		"""Extract displacement signal from range profile.

		Note: The TI out-of-box demo sends magnitude-only data, not complex I/Q.
		For vital signs, we use the magnitude variation at the target bin as a
		proxy for chest displacement. True phase extraction requires raw ADC data.
		"""
		range_res = 0.044
		bin_idx = int(target_range / range_res)
		bin_idx = max(0, min(bin_idx, len(range_profile) - 1))
		self._target_bin = bin_idx

		if np.iscomplexobj(range_profile):
			# True phase from complex data (if available)
			phase = np.angle(range_profile[bin_idx])
		else:
			# Use magnitude variation as displacement proxy (normalized)
			# Subtract mean to center around zero like phase would be
			magnitude = float(range_profile[bin_idx])
			self._phase_history.append(magnitude)
			if len(self._phase_history) > 200:
				self._phase_history = self._phase_history[-200:]
			mean_mag = np.mean(self._phase_history)
			# Scale to roughly -pi to pi range for compatibility
			phase = (magnitude - mean_mag) * 0.1

		return np.array([phase])

	def reset(self) -> None:
		self._range_doppler.reset()
		self._clutter.reset()
		self._target_bin = None
		self._phase_history.clear()
		logger.info("pipeline_reset")

	def update_config(self, **kwargs) -> None:
		for key, value in kwargs.items():
			if hasattr(self.config, key):
				setattr(self.config, key, value)

		if any(k in kwargs for k in ["clutter_removal", "clutter_alpha"]):
			self._clutter = ClutterRemoval(
				method=self.config.clutter_removal,
				alpha=self.config.clutter_alpha,
			)
		logger.info("pipeline_config_updated", **kwargs)


class PhaseUnwrapper:
	"""Unwrap phase discontinuities for continuous tracking."""

	def __init__(self) -> None:
		self._last_phase: float | None = None
		self._offset = 0.0

	def process(self, phase: float) -> float:
		if self._last_phase is None:
			self._last_phase = phase
			return phase

		diff = phase - self._last_phase
		if diff > np.pi:
			self._offset -= 2 * np.pi
		elif diff < -np.pi:
			self._offset += 2 * np.pi

		self._last_phase = phase
		return phase + self._offset

	def reset(self) -> None:
		self._last_phase = None
		self._offset = 0.0
