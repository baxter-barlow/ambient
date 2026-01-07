"""Signal filtering for vital signs extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import structlog
from numpy.typing import NDArray
from scipy import signal as sp_signal

logger = structlog.get_logger(__name__)


class Filter(ABC):
	@abstractmethod
	def process(self, signal: NDArray) -> NDArray:
		pass

	@abstractmethod
	def reset(self) -> None:
		pass


class BandpassFilter(Filter):
	"""Butterworth bandpass for isolating frequency bands."""

	def __init__(
		self,
		sample_rate_hz: float,
		low_freq_hz: float,
		high_freq_hz: float,
		order: int = 4,
	) -> None:
		self.sample_rate_hz = sample_rate_hz
		self.low_freq_hz = low_freq_hz
		self.high_freq_hz = high_freq_hz
		self.order = order

		nyquist = sample_rate_hz / 2
		low = max(0.001, min(0.999, low_freq_hz / nyquist))
		high = max(0.001, min(0.999, high_freq_hz / nyquist))

		if low >= high:
			raise ValueError(f"Invalid frequency range: {low_freq_hz}-{high_freq_hz} Hz")

		self._sos = sp_signal.butter(order, [low, high], btype="band", output="sos")
		self._zi: NDArray | None = None

	def process(self, signal: NDArray) -> NDArray:
		if len(signal) < 3 * self.order:
			return np.zeros_like(signal)

		try:
			filtered = sp_signal.sosfiltfilt(self._sos, signal)
		except ValueError:
			filtered = sp_signal.sosfilt(self._sos, signal)

		return filtered.astype(np.float32)

	def process_sample(self, sample: float) -> float:
		"""Real-time single-sample filtering."""
		if self._zi is None:
			self._zi = sp_signal.sosfilt_zi(self._sos) * sample

		filtered, self._zi = sp_signal.sosfilt(self._sos, [sample], zi=self._zi)
		return float(filtered[0])

	def reset(self) -> None:
		self._zi = None


class PhaseFilter(Filter):
	"""DC removal, detrending, optional smoothing."""

	def __init__(self, remove_dc: bool = True, detrend: bool = True, smooth_window: int = 0) -> None:
		self.remove_dc = remove_dc
		self.detrend = detrend
		self.smooth_window = smooth_window

	def process(self, signal: NDArray) -> NDArray:
		result = signal.astype(np.float64)

		if self.remove_dc:
			result = result - np.mean(result)
		if self.detrend:
			result = sp_signal.detrend(result)
		if self.smooth_window > 1:
			kernel = np.ones(self.smooth_window) / self.smooth_window
			result = np.convolve(result, kernel, mode="same")

		return result.astype(np.float32)

	def reset(self) -> None:
		pass


class MedianFilter(Filter):
	"""Spike removal via median filtering."""

	def __init__(self, window_size: int = 5) -> None:
		self.window_size = window_size | 1  # ensure odd

	def process(self, signal: NDArray) -> NDArray:
		return sp_signal.medfilt(signal, self.window_size).astype(np.float32)

	def reset(self) -> None:
		pass


class ExponentialSmoother(Filter):
	"""Exponential moving average."""

	def __init__(self, alpha: float = 0.1) -> None:
		self.alpha = alpha
		self._value: float | None = None

	def process(self, signal: NDArray) -> NDArray:
		if len(signal) == 0:
			return np.zeros_like(signal, dtype=np.float32)

		result = np.zeros_like(signal, dtype=np.float32)
		result[0] = signal[0]
		for i in range(1, len(signal)):
			result[i] = self.alpha * signal[i] + (1 - self.alpha) * result[i - 1]
		return result

	def update(self, sample: float) -> float:
		"""Process single sample."""
		if self._value is None:
			self._value = sample
		else:
			self._value = self.alpha * sample + (1 - self.alpha) * self._value
		return self._value

	def reset(self) -> None:
		self._value = None


class PhaseUnwrapper:
	"""Phase unwrapping for continuous phase tracking.

	Handles 2π discontinuities in wrapped phase data to produce
	a continuous unwrapped signal for vital signs extraction.
	"""

	def __init__(self, max_jump: float = np.pi) -> None:
		"""
		Args:
			max_jump: Maximum expected phase jump between samples (radians).
				Values above this trigger unwrapping. Default π.
		"""
		self.max_jump = max_jump
		self._last_phase: float | None = None
		self._cumulative_offset: float = 0.0

	def unwrap_sample(self, phase: float) -> float:
		"""Unwrap a single phase sample.

		Args:
			phase: Wrapped phase in radians (-π to +π)

		Returns:
			Unwrapped phase (continuous, unbounded)
		"""
		if self._last_phase is None:
			self._last_phase = phase
			return phase + self._cumulative_offset

		delta = phase - self._last_phase

		# Detect and correct 2π discontinuities
		if delta > self.max_jump:
			self._cumulative_offset -= 2 * np.pi
		elif delta < -self.max_jump:
			self._cumulative_offset += 2 * np.pi

		self._last_phase = phase
		return phase + self._cumulative_offset

	def unwrap_array(self, phases: NDArray) -> NDArray[np.float32]:
		"""Unwrap an array of phase values.

		Args:
			phases: Array of wrapped phases in radians

		Returns:
			Unwrapped phase array
		"""
		if len(phases) == 0:
			return np.array([], dtype=np.float32)
		return np.unwrap(phases).astype(np.float32)

	def reset(self) -> None:
		"""Reset unwrapper state."""
		self._last_phase = None
		self._cumulative_offset = 0.0

	@property
	def cumulative_phase(self) -> float:
		"""Total accumulated phase offset."""
		return self._cumulative_offset
