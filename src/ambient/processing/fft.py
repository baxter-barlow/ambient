"""FFT processing for range and Doppler analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import structlog
from numpy.typing import NDArray

logger = structlog.get_logger(__name__)


class FFTProcessor(ABC):
	@abstractmethod
	def process(self, data: NDArray) -> NDArray:
		pass

	@abstractmethod
	def reset(self) -> None:
		pass


@dataclass
class RangeFFTConfig:
	fft_size: int = 256
	window: str = "hann"
	zero_pad_factor: int = 1
	output_type: str = "magnitude"  # magnitude, power, complex


class RangeFFT(FFTProcessor):
	"""Range FFT converts ADC samples to range bins."""

	def __init__(self, config: RangeFFTConfig | None = None) -> None:
		self.config = config or RangeFFTConfig()
		self._window: NDArray | None = None
		self._setup_window()

	def _setup_window(self) -> None:
		n = self.config.fft_size
		windows = {"hann": np.hanning, "hamming": np.hamming, "blackman": np.blackman}
		self._window = windows.get(self.config.window, lambda x: np.ones(x))(n)

	def process(self, data: NDArray) -> NDArray:
		if data.ndim == 1:
			data = data.reshape(1, -1)

		num_chirps, num_samples = data.shape

		if self._window is not None and len(self._window) == num_samples:
			windowed = data * self._window
		else:
			windowed = data

		fft_size = self.config.fft_size * self.config.zero_pad_factor
		fft_result = np.fft.fft(windowed, n=fft_size, axis=-1)
		fft_result = fft_result[:, :fft_size // 2]

		if self.config.output_type == "magnitude":
			return np.abs(fft_result).squeeze()
		elif self.config.output_type == "power":
			return (np.abs(fft_result) ** 2).squeeze()
		return fft_result.squeeze()

	def reset(self) -> None:
		pass


@dataclass
class DopplerFFTConfig:
	fft_size: int = 64
	window: str = "hann"
	zero_pad_factor: int = 1
	output_type: str = "magnitude"


class DopplerFFT(FFTProcessor):
	"""Doppler FFT extracts velocity from chirp-to-chirp phase changes."""

	def __init__(self, config: DopplerFFTConfig | None = None) -> None:
		self.config = config or DopplerFFTConfig()
		self._window: NDArray | None = None
		self._setup_window()

	def _setup_window(self) -> None:
		n = self.config.fft_size
		windows = {"hann": np.hanning, "hamming": np.hamming, "blackman": np.blackman}
		self._window = windows.get(self.config.window, lambda x: np.ones(x))(n)

	def process(self, data: NDArray) -> NDArray:
		num_chirps, num_range_bins = data.shape

		if self._window is not None and len(self._window) == num_chirps:
			windowed = data * self._window[:, np.newaxis]
		else:
			windowed = data

		fft_size = self.config.fft_size * self.config.zero_pad_factor
		fft_result = np.fft.fftshift(np.fft.fft(windowed, n=fft_size, axis=0), axes=0)

		if self.config.output_type == "magnitude":
			return np.abs(fft_result)
		elif self.config.output_type == "power":
			return np.abs(fft_result) ** 2
		return fft_result

	def reset(self) -> None:
		pass


class RangeDopplerProcessor:
	"""Combined range-Doppler processing pipeline."""

	def __init__(
		self,
		range_fft_size: int = 256,
		doppler_fft_size: int = 64,
		window: str = "hann",
	) -> None:
		self.range_fft = RangeFFT(RangeFFTConfig(
			fft_size=range_fft_size, window=window, output_type="complex"
		))
		self.doppler_fft = DopplerFFT(DopplerFFTConfig(
			fft_size=doppler_fft_size, window=window, output_type="magnitude"
		))
		logger.info("range_doppler_init", range_fft=range_fft_size, doppler_fft=doppler_fft_size)

	def process(self, adc_data: NDArray) -> NDArray:
		range_profiles = self.range_fft.process(adc_data)
		return self.doppler_fft.process(range_profiles)

	def reset(self) -> None:
		self.range_fft.reset()
		self.doppler_fft.reset()
