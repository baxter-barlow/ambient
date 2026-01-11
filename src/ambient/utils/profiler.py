"""Performance profiling utilities for acquisition loop and processing.

Enable with environment variable: AMBIENT_PERF_ENABLED=true
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	pass

logger = logging.getLogger(__name__)


@dataclass
class TimingStats:
	"""Statistics for a single timing category with percentile tracking."""

	samples: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
	_sorted_cache: list[float] | None = field(default=None, repr=False)
	_cache_valid: bool = field(default=False, repr=False)

	def add(self, duration_ms: float) -> None:
		self.samples.append(duration_ms)
		self._cache_valid = False

	def _ensure_sorted(self) -> list[float]:
		if not self._cache_valid or self._sorted_cache is None:
			self._sorted_cache = sorted(self.samples)
			self._cache_valid = True
		return self._sorted_cache

	@property
	def count(self) -> int:
		return len(self.samples)

	@property
	def mean_ms(self) -> float:
		if not self.samples:
			return 0.0
		return sum(self.samples) / len(self.samples)

	@property
	def max_ms(self) -> float:
		if not self.samples:
			return 0.0
		return max(self.samples)

	@property
	def min_ms(self) -> float:
		if not self.samples:
			return 0.0
		return min(self.samples)

	@property
	def last_ms(self) -> float:
		if not self.samples:
			return 0.0
		return self.samples[-1]

	def percentile(self, p: float) -> float:
		"""Get percentile value (0-100)."""
		if not self.samples:
			return 0.0
		sorted_samples = self._ensure_sorted()
		idx = int(len(sorted_samples) * (p / 100.0))
		idx = max(0, min(idx, len(sorted_samples) - 1))
		return sorted_samples[idx]

	@property
	def p50_ms(self) -> float:
		return self.percentile(50)

	@property
	def p95_ms(self) -> float:
		return self.percentile(95)

	@property
	def p99_ms(self) -> float:
		return self.percentile(99)

	def reset(self) -> None:
		self.samples.clear()
		self._cache_valid = False
		self._sorted_cache = None

	def to_dict(self) -> dict[str, float]:
		"""Export stats as dictionary."""
		return {
			"count": self.count,
			"mean_ms": round(self.mean_ms, 3),
			"min_ms": round(self.min_ms, 3),
			"max_ms": round(self.max_ms, 3),
			"p50_ms": round(self.p50_ms, 3),
			"p95_ms": round(self.p95_ms, 3),
			"p99_ms": round(self.p99_ms, 3),
			"last_ms": round(self.last_ms, 3),
		}


@dataclass
class QueueStats:
	"""Statistics for queue depth and drops."""

	current_depth: int = 0
	max_depth: int = 0
	total_enqueued: int = 0
	total_dropped: int = 0
	depth_samples: deque[int] = field(default_factory=lambda: deque(maxlen=1000))

	def record_depth(self, depth: int) -> None:
		self.current_depth = depth
		self.max_depth = max(self.max_depth, depth)
		self.depth_samples.append(depth)

	def record_enqueue(self) -> None:
		self.total_enqueued += 1

	def record_drop(self) -> None:
		self.total_dropped += 1

	@property
	def avg_depth(self) -> float:
		if not self.depth_samples:
			return 0.0
		return sum(self.depth_samples) / len(self.depth_samples)

	@property
	def drop_rate(self) -> float:
		"""Percentage of messages dropped."""
		if self.total_enqueued == 0:
			return 0.0
		return (self.total_dropped / self.total_enqueued) * 100

	def reset(self) -> None:
		self.current_depth = 0
		self.max_depth = 0
		self.total_enqueued = 0
		self.total_dropped = 0
		self.depth_samples.clear()

	def to_dict(self) -> dict[str, Any]:
		return {
			"current_depth": self.current_depth,
			"max_depth": self.max_depth,
			"avg_depth": round(self.avg_depth, 1),
			"total_enqueued": self.total_enqueued,
			"total_dropped": self.total_dropped,
			"drop_rate_percent": round(self.drop_rate, 2),
		}


class FrameProfiler:
	"""Lightweight frame processing profiler with percentile tracking.

	Tracks timing for:
	- Total frame processing time
	- Pipeline processing time
	- Vitals extraction time
	- WebSocket broadcast time
	- Recording write time
	- Queue depth and drops

	Example:
		profiler = FrameProfiler(enabled=True, log_interval=100)

		with profiler.measure("pipeline"):
			processed = pipeline.process(frame)

		with profiler.measure("vitals"):
			vitals = extractor.process_frame(processed)

		profiler.record_queue_depth("sensor", queue.qsize())
		profiler.frame_complete()
	"""

	def __init__(
		self,
		enabled: bool = False,
		log_interval: int = 100,
		sample_rate: float = 1.0,
	) -> None:
		self.enabled = enabled
		self.log_interval = log_interval
		self.sample_rate = sample_rate  # 1.0 = every frame, 0.1 = 10% of frames

		self._stats: dict[str, TimingStats] = {
			"total": TimingStats(),
			"pipeline": TimingStats(),
			"vitals": TimingStats(),
			"broadcast": TimingStats(),
			"recording": TimingStats(),
		}
		self._queue_stats: dict[str, QueueStats] = {}
		self._frame_count = 0
		self._sampled_count = 0
		self._dropped_frames = 0
		self._frame_start: float | None = None
		self._should_sample = True

	class _TimerContext:
		"""Context manager for timing code blocks."""

		def __init__(self, profiler: FrameProfiler, name: str) -> None:
			self.profiler = profiler
			self.name = name
			self.start: float = 0.0

		def __enter__(self) -> FrameProfiler._TimerContext:
			if self.profiler.enabled and self.profiler._should_sample:
				self.start = time.perf_counter()
			return self

		def __exit__(self, *args) -> None:
			if self.profiler.enabled and self.profiler._should_sample and self.start > 0:
				duration_ms = (time.perf_counter() - self.start) * 1000
				if self.name not in self.profiler._stats:
					self.profiler._stats[self.name] = TimingStats()
				self.profiler._stats[self.name].add(duration_ms)

	def measure(self, name: str) -> _TimerContext:
		"""Return context manager for timing a code block.

		Args:
			name: Category name (pipeline, vitals, broadcast, recording)
		"""
		return self._TimerContext(self, name)

	def frame_start(self) -> None:
		"""Mark the start of frame processing."""
		if not self.enabled:
			return

		self._frame_count += 1

		# Determine if we should sample this frame
		if self.sample_rate >= 1.0:
			self._should_sample = True
		else:
			import random
			self._should_sample = random.random() < self.sample_rate

		if self._should_sample:
			self._frame_start = time.perf_counter()
			self._sampled_count += 1

	def frame_complete(self) -> None:
		"""Mark frame processing complete and potentially log stats."""
		if not self.enabled:
			return

		if self._should_sample and self._frame_start is not None:
			total_ms = (time.perf_counter() - self._frame_start) * 1000
			self._stats["total"].add(total_ms)
			self._frame_start = None

		if self._frame_count % self.log_interval == 0:
			self._log_stats()

	def record_dropped_frame(self) -> None:
		"""Record a dropped frame."""
		self._dropped_frames += 1

	def record_queue_depth(self, queue_name: str, depth: int) -> None:
		"""Record current queue depth."""
		if queue_name not in self._queue_stats:
			self._queue_stats[queue_name] = QueueStats()
		self._queue_stats[queue_name].record_depth(depth)

	def record_queue_enqueue(self, queue_name: str) -> None:
		"""Record message enqueued."""
		if queue_name not in self._queue_stats:
			self._queue_stats[queue_name] = QueueStats()
		self._queue_stats[queue_name].record_enqueue()

	def record_queue_drop(self, queue_name: str) -> None:
		"""Record message dropped from queue."""
		if queue_name not in self._queue_stats:
			self._queue_stats[queue_name] = QueueStats()
		self._queue_stats[queue_name].record_drop()

	def _log_stats(self) -> None:
		"""Log current statistics."""
		total = self._stats["total"]
		pipeline = self._stats["pipeline"]
		vitals = self._stats["vitals"]
		broadcast = self._stats["broadcast"]

		log_data = {
			"frames": self._frame_count,
			"sampled": self._sampled_count,
			"dropped": self._dropped_frames,
			"total_p50_ms": f"{total.p50_ms:.2f}",
			"total_p95_ms": f"{total.p95_ms:.2f}",
			"total_p99_ms": f"{total.p99_ms:.2f}",
			"pipeline_mean_ms": f"{pipeline.mean_ms:.2f}",
			"vitals_mean_ms": f"{vitals.mean_ms:.2f}",
			"broadcast_mean_ms": f"{broadcast.mean_ms:.2f}",
		}

		# Add queue stats
		for name, qstats in self._queue_stats.items():
			log_data[f"queue_{name}_depth"] = qstats.current_depth
			log_data[f"queue_{name}_drops"] = qstats.total_dropped

		logger.info("perf_stats", extra=log_data)

	def get_stats(self) -> dict[str, Any]:
		"""Get current statistics as dictionary."""
		timing: dict[str, Any] = {}
		queues: dict[str, Any] = {}

		for name, stats in self._stats.items():
			timing[name] = stats.to_dict()

		for name, qstats in self._queue_stats.items():
			queues[name] = qstats.to_dict()

		return {
			"frame_count": self._frame_count,
			"sampled_count": self._sampled_count,
			"dropped_frames": self._dropped_frames,
			"sample_rate": self.sample_rate,
			"timing": timing,
			"queues": queues,
		}

	def reset(self) -> None:
		"""Reset all statistics."""
		for stats in self._stats.values():
			stats.reset()
		for qstats in self._queue_stats.values():
			qstats.reset()
		self._frame_count = 0
		self._sampled_count = 0
		self._dropped_frames = 0

	@property
	def frame_count(self) -> int:
		return self._frame_count

	@property
	def dropped_frames(self) -> int:
		return self._dropped_frames


# Global profiler instance (lazy initialization)
_profiler: FrameProfiler | None = None


def get_profiler() -> FrameProfiler:
	"""Get the global profiler instance."""
	global _profiler
	if _profiler is None:
		from ambient.config import get_config

		config = get_config()
		_profiler = FrameProfiler(
			enabled=config.performance.enabled,
			log_interval=config.performance.log_interval_frames,
			sample_rate=config.performance.sample_rate,
		)
	return _profiler


def reset_profiler() -> None:
	"""Reset the global profiler (useful for testing)."""
	global _profiler
	_profiler = None
