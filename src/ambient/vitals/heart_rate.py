"""Heart rate estimation from radar phase data."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog
from numpy.typing import NDArray

logger = structlog.get_logger(__name__)


@dataclass
class EstimationResult:
	"""Result from rate estimation with quality metrics."""
	rate_bpm: float | None
	confidence: float
	snr_db: float = 0.0
	spectral_purity: float = 0.0
	peak_prominence: float = 0.0


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
		result = self.estimate_with_quality(signal)
		return result.rate_bpm, result.confidence

	def estimate_with_quality(self, signal: NDArray[np.float32]) -> EstimationResult:
		"""Returns EstimationResult with rate and quality metrics."""
		if len(signal) < 20:
			return EstimationResult(rate_bpm=None, confidence=0.0)

		n_fft = len(signal) * self.fft_padding_factor
		fft_result = np.fft.rfft(signal, n=n_fft)
		freqs = np.fft.rfftfreq(n_fft, 1.0 / self.sample_rate_hz)
		magnitude = np.abs(fft_result)

		freq_mask = (freqs >= self.freq_min_hz) & (freqs <= self.freq_max_hz)
		band_freqs = freqs[freq_mask]
		band_magnitude = magnitude[freq_mask]

		if len(band_magnitude) == 0:
			return EstimationResult(rate_bpm=None, confidence=0.0)

		peak_idx = np.argmax(band_magnitude)
		peak_freq = band_freqs[peak_idx]
		peak_mag = band_magnitude[peak_idx]

		heart_rate_bpm = peak_freq * 60.0

		# Calculate quality metrics
		mean_mag = np.mean(band_magnitude)
		median_mag = np.median(band_magnitude)

		# SNR: peak power vs average noise floor
		noise_floor = np.percentile(band_magnitude, 25)
		snr_db = 20 * np.log10(peak_mag / noise_floor) if noise_floor > 0 else 0.0

		# Spectral purity: how much energy is concentrated at peak (0-1, higher=better)
		# Uses ratio of peak to total band energy
		total_energy = np.sum(band_magnitude ** 2)
		peak_energy = peak_mag ** 2
		spectral_purity = peak_energy / total_energy if total_energy > 0 else 0.0

		# Peak prominence: peak vs median ratio
		peak_prominence = (peak_mag / median_mag - 1) if median_mag > 0 else 0.0

		# Confidence: combine multiple metrics
		base_confidence = min(1.0, (peak_mag / mean_mag - 1) / 5.0) if mean_mag > 0 else 0.0

		# Boost confidence if SNR is good (>10dB)
		if snr_db > 10:
			base_confidence = min(1.0, base_confidence * 1.2)

		# Penalize large jumps from previous estimate
		if self._last_hr is not None and abs(heart_rate_bpm - self._last_hr) > 20:
			base_confidence *= 0.5

		self._last_hr = heart_rate_bpm
		self._hr_history.append(heart_rate_bpm)
		if len(self._hr_history) > 10:
			self._hr_history = self._hr_history[-10:]

		return EstimationResult(
			rate_bpm=heart_rate_bpm,
			confidence=base_confidence,
			snr_db=snr_db,
			spectral_purity=spectral_purity,
			peak_prominence=peak_prominence,
		)

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
