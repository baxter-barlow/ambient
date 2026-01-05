"""Clutter removal for radar signal processing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import structlog
from numpy.typing import NDArray

logger = structlog.get_logger(__name__)


class ClutterFilter(ABC):
	@abstractmethod
	def process(self, data: NDArray) -> NDArray:
		pass

	@abstractmethod
	def reset(self) -> None:
		pass


@dataclass
class MovingAverageConfig:
	alpha: float = 0.1
	warmup_frames: int = 10


class MovingAverageClutter(ClutterFilter):
	"""EMA-based static clutter removal."""

	def __init__(self, config: MovingAverageConfig | None = None) -> None:
		self.config = config or MovingAverageConfig()
		self._background: NDArray | None = None
		self._frame_count = 0

	def process(self, data: NDArray) -> NDArray:
		self._frame_count += 1

		if self._background is None:
			self._background = data.astype(np.float64)
			return data

		alpha = self.config.alpha
		self._background = alpha * data + (1 - alpha) * self._background

		if self._frame_count < self.config.warmup_frames:
			return data

		return data - self._background

	def reset(self) -> None:
		self._background = None
		self._frame_count = 0


@dataclass
class MTIConfig:
	num_taps: int = 2
	weights: list[float] | None = None


class MTIFilter(ClutterFilter):
	"""Moving Target Indicator - frame-to-frame differencing."""

	def __init__(self, config: MTIConfig | None = None) -> None:
		self.config = config or MTIConfig()
		self._weights = np.array(self.config.weights or [1.0, -1.0])
		self._history: list[NDArray] = []

	def process(self, data: NDArray) -> NDArray:
		self._history.append(data.copy())

		max_history = len(self._weights)
		if len(self._history) > max_history:
			self._history = self._history[-max_history:]

		if len(self._history) < max_history:
			return np.zeros_like(data)

		result = np.zeros_like(data, dtype=np.float64)
		for i, weight in enumerate(self._weights):
			result += weight * self._history[i]
		return result

	def reset(self) -> None:
		self._history = []


class NullFilter(ClutterFilter):
	"""Pass-through filter."""

	def process(self, data: NDArray) -> NDArray:
		return data

	def reset(self) -> None:
		pass


class ClutterRemoval:
	"""Unified clutter removal interface."""

	def __init__(self, method: str = "mti", **kwargs) -> None:
		self.method = method

		if method == "mti":
			cfg = MTIConfig(**{k: v for k, v in kwargs.items() if k in MTIConfig.__annotations__})
			self._filter: ClutterFilter = MTIFilter(cfg)
		elif method == "moving_average":
			cfg = MovingAverageConfig(**{k: v for k, v in kwargs.items() if k in MovingAverageConfig.__annotations__})
			self._filter = MovingAverageClutter(cfg)
		elif method == "none":
			self._filter = NullFilter()
		else:
			raise ValueError(f"Unknown method: {method}")

		logger.info("clutter_removal_init", method=method)

	def process(self, data: NDArray) -> NDArray:
		return self._filter.process(data)

	def reset(self) -> None:
		self._filter.reset()
