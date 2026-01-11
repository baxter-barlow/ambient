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


def _find_peak_with_smoothing(
	spectrum: NDArray[np.float32],
	start_idx: int = 0,
	end_idx: int | None = None,
) -> tuple[int, float]:
	"""Find peak using 3-sample smoothed peak detection (TI algorithm).

	Instead of finding the raw maximum, this uses a 3-sample window
	(i-1, i, i+1) sum for peak detection, reducing noise sensitivity.

	Args:
		spectrum: Magnitude spectrum array
		start_idx: Start index for search
		end_idx: End index for search (exclusive)

	Returns:
		(peak_index, peak_value) where peak_value is the 3-sample sum
	"""
	if end_idx is None:
		end_idx = len(spectrum)

	if end_idx - start_idx < 3:
		# Not enough samples for smoothing
		if end_idx <= start_idx:
			return 0, 0.0
		local_idx = int(np.argmax(spectrum[start_idx:end_idx]))
		return start_idx + local_idx, float(spectrum[start_idx + local_idx])

	best_idx = start_idx + 1
	best_value = 0.0

	for i in range(start_idx + 1, end_idx - 1):
		value = spectrum[i - 1] + spectrum[i] + spectrum[i + 1]
		if value > best_value:
			best_value = value
			best_idx = i

	return best_idx, best_value


class HeartRateEstimator:
	"""FFT-based heart rate estimation (0.8-3.0 Hz band).

	Implements TI's algorithm enhancements:
	- Harmonic product spectrum for robust HR detection
	- 3-sample smoothed peak detection to reduce noise sensitivity
	"""

	def __init__(
		self,
		sample_rate_hz: float = 20.0,
		freq_min_hz: float = 0.8,
		freq_max_hz: float = 3.0,
		fft_padding_factor: int = 4,
		use_harmonic_product: bool = True,
	) -> None:
		self.sample_rate_hz = sample_rate_hz
		self.freq_min_hz = freq_min_hz
		self.freq_max_hz = freq_max_hz
		self.fft_padding_factor = fft_padding_factor
		self.use_harmonic_product = use_harmonic_product
		self._last_hr: float | None = None
		self._hr_history: list[float] = []

	def estimate(self, signal: NDArray[np.float32]) -> tuple[float | None, float]:
		"""Returns (heart_rate_bpm, confidence)."""
		result = self.estimate_with_quality(signal)
		return result.rate_bpm, result.confidence

	def estimate_with_quality(
		self,
		signal: NDArray[np.float32],
		use_harmonic: bool | None = None,
	) -> EstimationResult:
		"""Returns EstimationResult with rate and quality metrics.

		Args:
			signal: Input phase signal (bandpass filtered for HR band)
			use_harmonic: Override harmonic product spectrum setting

		Returns:
			EstimationResult with heart rate and quality metrics
		"""
		if len(signal) < 20:
			return EstimationResult(rate_bpm=None, confidence=0.0)

		n_fft = len(signal) * self.fft_padding_factor
		fft_result = np.fft.rfft(signal, n=n_fft)
		freqs = np.fft.rfftfreq(n_fft, 1.0 / self.sample_rate_hz)
		magnitude = np.abs(fft_result)

		# Find frequency band indices
		freq_mask = (freqs >= self.freq_min_hz) & (freqs <= self.freq_max_hz)
		band_indices = np.where(freq_mask)[0]

		if len(band_indices) == 0:
			return EstimationResult(rate_bpm=None, confidence=0.0)

		start_idx = band_indices[0]
		end_idx = band_indices[-1] + 1

		# Decide whether to use harmonic product spectrum
		should_use_harmonic = use_harmonic if use_harmonic is not None else self.use_harmonic_product

		if should_use_harmonic:
			# Harmonic product spectrum: multiply spectrum[i] * spectrum[2*i]
			# This enhances the true HR by requiring both fundamental and harmonic
			harmonic_spectrum = self._compute_harmonic_product_spectrum(magnitude)
			search_spectrum = harmonic_spectrum
		else:
			search_spectrum = magnitude

		# Use 3-sample smoothed peak detection (TI algorithm)
		peak_idx, _ = _find_peak_with_smoothing(
			search_spectrum, start_idx, min(end_idx, len(search_spectrum))
		)

		peak_freq = freqs[peak_idx]
		peak_mag = magnitude[peak_idx]  # Use original magnitude for SNR calculation
		heart_rate_bpm = peak_freq * 60.0

		# Calculate quality metrics using the HR band
		band_magnitude = magnitude[start_idx:end_idx]
		mean_mag = np.mean(band_magnitude)
		median_mag = np.median(band_magnitude)

		# SNR: peak power vs noise floor (25th percentile)
		noise_floor = np.percentile(band_magnitude, 25)
		snr_db = 20 * np.log10(peak_mag / noise_floor) if noise_floor > 0 else 0.0

		# Spectral purity: energy concentration at peak (0-1, higher=better)
		total_energy = np.sum(band_magnitude ** 2)
		peak_energy = peak_mag ** 2
		spectral_purity = peak_energy / total_energy if total_energy > 0 else 0.0

		# Peak prominence: peak vs median ratio
		peak_prominence = (peak_mag / median_mag - 1) if median_mag > 0 else 0.0

		# Base confidence from peak-to-mean ratio
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

	def _compute_harmonic_product_spectrum(
		self,
		magnitude: NDArray[np.float32],
	) -> NDArray[np.float32]:
		"""Compute harmonic product spectrum.

		Heart signals typically have energy at both f (fundamental) and 2f (harmonic).
		Multiplying spectrum[i] * spectrum[2*i] enhances the true HR peak by
		requiring both the fundamental and its first harmonic to be present.

		This is TI's 'decimated product' technique for robust HR detection.

		Args:
			magnitude: FFT magnitude spectrum

		Returns:
			Harmonic product spectrum (same length as input, zeros where harmonic unavailable)
		"""
		n = len(magnitude)
		result = np.zeros(n, dtype=np.float32)

		# Only compute where we have both i and 2*i available
		max_idx = n // 2
		if max_idx > 0:
			# Vectorized: result[i] = magnitude[i] * magnitude[2*i] for i < n//2
			indices = np.arange(max_idx)
			harmonic_indices = indices * 2
			result[:max_idx] = magnitude[:max_idx] * magnitude[harmonic_indices]

		return result

	def estimate_with_harmonic(
		self,
		signal: NDArray[np.float32],
	) -> EstimationResult:
		"""Estimate heart rate using harmonic product spectrum.

		Convenience method that forces use of harmonic product spectrum.
		"""
		return self.estimate_with_quality(signal, use_harmonic=True)

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
			return float(freq * 60.0), float(autocorr[peak_idx])
		return None, 0.0

	def get_smoothed_hr(self, window: int = 5) -> float | None:
		if len(self._hr_history) < window:
			return None
		return float(np.median(self._hr_history[-window:]))

	def reset(self) -> None:
		self._last_hr = None
		self._hr_history.clear()
