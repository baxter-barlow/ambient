"""Respiratory rate estimation from radar phase data."""

from __future__ import annotations

import numpy as np
import structlog
from numpy.typing import NDArray
from scipy import signal as sp_signal

logger = structlog.get_logger(__name__)


class RespiratoryRateEstimator:
	"""FFT-based respiratory rate estimation (0.1-0.6 Hz band)."""

	def __init__(
		self,
		sample_rate_hz: float = 20.0,
		freq_min_hz: float = 0.1,
		freq_max_hz: float = 0.6,
		fft_padding_factor: int = 4,
	) -> None:
		self.sample_rate_hz = sample_rate_hz
		self.freq_min_hz = freq_min_hz
		self.freq_max_hz = freq_max_hz
		self.fft_padding_factor = fft_padding_factor
		self._last_rr: float | None = None
		self._rr_history: list[float] = []

	def estimate(self, signal: NDArray[np.float32]) -> tuple[float | None, float]:
		"""Returns (respiratory_rate_bpm, confidence)."""
		if len(signal) < 20:
			return None, 0.0

		n_fft = len(signal) * self.fft_padding_factor
		fft_result = np.fft.rfft(signal, n=n_fft)
		freqs = np.fft.rfftfreq(n_fft, 1.0 / self.sample_rate_hz)
		magnitude = np.abs(fft_result)

		freq_mask = (freqs >= self.freq_min_hz) & (freqs <= self.freq_max_hz)
		band_freqs = freqs[freq_mask]
		band_magnitude = magnitude[freq_mask]

		if len(band_magnitude) == 0:
			return None, 0.0

		peak_idx = np.argmax(band_magnitude)
		peak_freq = band_freqs[peak_idx]
		peak_mag = band_magnitude[peak_idx]

		rr_bpm = peak_freq * 60.0

		mean_mag = np.mean(band_magnitude)
		confidence = min(1.0, (peak_mag / mean_mag - 1) / 3.0) if mean_mag > 0 else 0.0

		if self._last_rr is not None and abs(rr_bpm - self._last_rr) > 10:
			confidence *= 0.5

		self._last_rr = rr_bpm
		self._rr_history.append(rr_bpm)
		if len(self._rr_history) > 10:
			self._rr_history = self._rr_history[-10:]

		return rr_bpm, confidence

	def estimate_with_peak_counting(self, signal: NDArray[np.float32]) -> tuple[float | None, float]:
		"""Alternative peak-counting method."""
		if len(signal) < 40:
			return None, 0.0

		min_distance = int(self.sample_rate_hz / self.freq_max_hz)
		peaks, _ = sp_signal.find_peaks(signal, distance=min_distance, prominence=np.std(signal) * 0.5)

		if len(peaks) < 2:
			return None, 0.0

		intervals = np.diff(peaks) / self.sample_rate_hz
		mean_interval = np.mean(intervals)

		if mean_interval <= 0:
			return None, 0.0

		rr_bpm = 60.0 / mean_interval
		cv = np.std(intervals) / mean_interval if len(intervals) > 1 else 0.7
		confidence = max(0.0, 1.0 - cv)

		return rr_bpm, confidence

	def get_smoothed_rr(self, window: int = 5) -> float | None:
		if len(self._rr_history) < window:
			return None
		return float(np.median(self._rr_history[-window:]))

	def reset(self) -> None:
		self._last_rr = None
		self._rr_history.clear()
