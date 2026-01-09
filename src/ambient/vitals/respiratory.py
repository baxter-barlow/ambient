"""Respiratory rate estimation from radar phase data."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog
from numpy.typing import NDArray
from scipy import signal as sp_signal

logger = structlog.get_logger(__name__)


@dataclass
class RREstimationResult:
	"""Result from respiratory rate estimation with quality metrics."""
	rate_bpm: float | None
	confidence: float
	snr_db: float = 0.0
	spectral_purity: float = 0.0
	peak_prominence: float = 0.0


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
		result = self.estimate_with_quality(signal)
		return result.rate_bpm, result.confidence

	def estimate_with_quality(self, signal: NDArray[np.float32]) -> RREstimationResult:
		"""Returns RREstimationResult with rate and quality metrics."""
		if len(signal) < 20:
			return RREstimationResult(rate_bpm=None, confidence=0.0)

		n_fft = len(signal) * self.fft_padding_factor
		fft_result = np.fft.rfft(signal, n=n_fft)
		freqs = np.fft.rfftfreq(n_fft, 1.0 / self.sample_rate_hz)
		magnitude = np.abs(fft_result)

		freq_mask = (freqs >= self.freq_min_hz) & (freqs <= self.freq_max_hz)
		band_freqs = freqs[freq_mask]
		band_magnitude = magnitude[freq_mask]

		if len(band_magnitude) == 0:
			return RREstimationResult(rate_bpm=None, confidence=0.0)

		peak_idx = np.argmax(band_magnitude)
		peak_freq = band_freqs[peak_idx]
		peak_mag = band_magnitude[peak_idx]

		rr_bpm = peak_freq * 60.0

		# Calculate quality metrics
		mean_mag = np.mean(band_magnitude)
		median_mag = np.median(band_magnitude)

		# SNR: peak power vs noise floor
		noise_floor = np.percentile(band_magnitude, 25)
		snr_db = 20 * np.log10(peak_mag / noise_floor) if noise_floor > 0 else 0.0

		# Spectral purity: energy concentration at peak
		total_energy = np.sum(band_magnitude ** 2)
		peak_energy = peak_mag ** 2
		spectral_purity = peak_energy / total_energy if total_energy > 0 else 0.0

		# Peak prominence
		peak_prominence = (peak_mag / median_mag - 1) if median_mag > 0 else 0.0

		# Confidence calculation
		confidence = min(1.0, (peak_mag / mean_mag - 1) / 3.0) if mean_mag > 0 else 0.0

		# Boost confidence if SNR is good
		if snr_db > 10:
			confidence = min(1.0, confidence * 1.2)

		if self._last_rr is not None and abs(rr_bpm - self._last_rr) > 10:
			confidence *= 0.5

		self._last_rr = rr_bpm
		self._rr_history.append(rr_bpm)
		if len(self._rr_history) > 10:
			self._rr_history = self._rr_history[-10:]

		return RREstimationResult(
			rate_bpm=rr_bpm,
			confidence=confidence,
			snr_db=snr_db,
			spectral_purity=spectral_purity,
			peak_prominence=peak_prominence,
		)

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
