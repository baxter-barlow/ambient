"""Heart rate estimation from radar phase data."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
import structlog

logger = structlog.get_logger(__name__)


class HeartRateEstimator:
	"""FFT-based heart rate estimation (0.8-3.0 Hz band)."""

	def __init__(
		self,
		sample_rate_hz: float = 20.0,
		freq_min_hz: float = 0.8,
		freq_max_hz: float = 3.0,
		fft_padding_factor: int = 4,
	) -> None:
		self.sample_rate_hz = sample_rate_hz
		self.freq_min_hz = freq_min_hz
		self.freq_max_hz = freq_max_hz
		self.fft_padding_factor = fft_padding_factor
		self._last_hr: float | None = None
		self._hr_history: list[float] = []

	def estimate(self, signal: NDArray[np.float32]) -> tuple[float | None, float]:
		"""Returns (heart_rate_bpm, confidence)."""
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

		heart_rate_bpm = peak_freq * 60.0

		mean_mag = np.mean(band_magnitude)
		confidence = min(1.0, (peak_mag / mean_mag - 1) / 5.0) if mean_mag > 0 else 0.0

		# penalize large jumps
		if self._last_hr is not None and abs(heart_rate_bpm - self._last_hr) > 20:
			confidence *= 0.5

		self._last_hr = heart_rate_bpm
		self._hr_history.append(heart_rate_bpm)
		if len(self._hr_history) > 10:
			self._hr_history = self._hr_history[-10:]

		return heart_rate_bpm, confidence

	def estimate_with_autocorr(self, signal: NDArray[np.float32]) -> tuple[float | None, float]:
		"""Alternative autocorrelation-based estimation."""
		if len(signal) < 40:
			return None, 0.0

		autocorr = np.correlate(signal, signal, mode="full")
		autocorr = autocorr[len(autocorr) // 2:]
		autocorr = autocorr / autocorr[0]

		min_lag = int(self.sample_rate_hz / self.freq_max_hz)
		max_lag = int(self.sample_rate_hz / self.freq_min_hz)

		search = autocorr[min_lag:min(max_lag, len(autocorr))]
		if len(search) == 0:
			return None, 0.0

		peak_idx = np.argmax(search) + min_lag
		if peak_idx > 0:
			freq = self.sample_rate_hz / peak_idx
			return freq * 60.0, float(autocorr[peak_idx])
		return None, 0.0

	def get_smoothed_hr(self, window: int = 5) -> float | None:
		if len(self._hr_history) < window:
			return None
		return float(np.median(self._hr_history[-window:]))

	def reset(self) -> None:
		self._last_hr = None
		self._hr_history.clear()
