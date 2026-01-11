"""Point cloud accumulation and processing for 3D visualization."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
	from ambient.sensor.frame import CompressedPoint, DetectedPoint, RadarFrame


@dataclass
class Point3D:
	"""3D point with metadata for visualization."""
	x: float
	y: float
	z: float
	velocity: float = 0.0
	snr: float = 0.0
	age: int = 0           # Frames since detection
	track_id: int = -1     # Associated track ID (-1 = untracked)
	frame_number: int = 0  # Frame when point was detected

	@property
	def range(self) -> float:
		"""Distance from radar."""
		return np.sqrt(self.x**2 + self.y**2 + self.z**2)

	@property
	def azimuth(self) -> float:
		"""Azimuth angle in radians."""
		return np.arctan2(self.x, self.y)

	@property
	def elevation(self) -> float:
		"""Elevation angle in radians."""
		r_xy = np.sqrt(self.x**2 + self.y**2)
		return np.arctan2(self.z, r_xy) if r_xy > 0 else 0.0

	def to_array(self) -> NDArray[np.float32]:
		"""Convert to numpy array [x, y, z, velocity, snr, age]."""
		return np.array([self.x, self.y, self.z, self.velocity, self.snr, self.age], dtype=np.float32)


@dataclass
class PointCloudConfig:
	"""Configuration for point cloud accumulation."""
	persistence_frames: int = 10   # Number of frames to retain points
	max_points: int = 1000         # Maximum points to store
	age_fade: bool = True          # Enable age-based fading
	min_snr_db: float = 5.0        # Minimum SNR for point inclusion
	merge_distance: float = 0.1    # Distance threshold for merging points (meters)


class PointCloudAccumulator:
	"""Accumulates point clouds across frames for persistence visualization.

	Implements TI's point cloud persistence algorithm:
	- Points are retained for a configurable number of frames
	- Older points gradually fade out (age increases)
	- Points can be merged if they are close together
	- Track associations are preserved when available

	Example:
		accumulator = PointCloudAccumulator(
			PointCloudConfig(persistence_frames=15, max_points=500)
		)

		for frame in frame_stream:
			# Add new points from frame
			accumulator.add_frame(frame)

			# Get all accumulated points for visualization
			points = accumulator.get_points()

			# Render points with age-based coloring
			for pt in points:
				opacity = 1.0 - (pt.age / accumulator.config.persistence_frames)
				render_point(pt.x, pt.y, pt.z, opacity)
	"""

	def __init__(self, config: PointCloudConfig | None = None) -> None:
		self.config = config or PointCloudConfig()
		self._points: deque[Point3D] = deque(maxlen=self.config.max_points)
		self._frame_count = 0

	def add_frame(self, frame: RadarFrame) -> None:
		"""Add points from a radar frame.

		Args:
			frame: RadarFrame containing detected points
		"""
		self._frame_count += 1

		# Age existing points
		for pt in self._points:
			pt.age += 1

		# Remove points that exceed persistence
		self._points = deque(
			(pt for pt in self._points if pt.age < self.config.persistence_frames),
			maxlen=self.config.max_points,
		)

		# Add new points from detected_points
		for i, dp in enumerate(frame.detected_points):
			if dp.snr < self.config.min_snr_db:
				continue

			# Get track ID if available
			track_id = -1
			if frame.target_index and i < len(frame.target_index.indices):
				track_id = frame.target_index.indices[i]

			new_point = Point3D(
				x=dp.x,
				y=dp.y,
				z=dp.z,
				velocity=dp.velocity,
				snr=dp.snr,
				age=0,
				track_id=track_id,
				frame_number=self._frame_count,
			)
			self._points.append(new_point)

		# Also add compressed points if available
		if frame.compressed_points:
			for cp in frame.compressed_points.points:
				if cp.snr < self.config.min_snr_db:
					continue

				x, y, z = cp.to_cartesian()
				new_point = Point3D(
					x=x,
					y=y,
					z=z,
					velocity=cp.doppler,
					snr=cp.snr,
					age=0,
					track_id=-1,
					frame_number=self._frame_count,
				)
				self._points.append(new_point)

	def add_points(
		self,
		points: list[DetectedPoint],
		track_indices: list[int] | None = None,
	) -> None:
		"""Add points directly without a frame.

		Args:
			points: List of detected points
			track_indices: Optional list of track IDs for each point
		"""
		self._frame_count += 1

		# Age existing points
		for pt in self._points:
			pt.age += 1

		# Remove old points
		self._points = deque(
			(pt for pt in self._points if pt.age < self.config.persistence_frames),
			maxlen=self.config.max_points,
		)

		# Add new points
		for i, dp in enumerate(points):
			if dp.snr < self.config.min_snr_db:
				continue

			track_id = -1
			if track_indices and i < len(track_indices):
				track_id = track_indices[i]

			new_point = Point3D(
				x=dp.x,
				y=dp.y,
				z=dp.z,
				velocity=dp.velocity,
				snr=dp.snr,
				age=0,
				track_id=track_id,
				frame_number=self._frame_count,
			)
			self._points.append(new_point)

	def get_points(self) -> list[Point3D]:
		"""Get all accumulated points.

		Returns:
			List of Point3D with age information
		"""
		return list(self._points)

	def get_points_array(self) -> NDArray[np.float32]:
		"""Get points as numpy array for efficient rendering.

		Returns:
			Array of shape (N, 6) with columns [x, y, z, velocity, snr, age]
		"""
		if not self._points:
			return np.zeros((0, 6), dtype=np.float32)

		return np.array([pt.to_array() for pt in self._points], dtype=np.float32)

	def get_points_by_track(self, track_id: int) -> list[Point3D]:
		"""Get points associated with a specific track.

		Args:
			track_id: Track ID to filter by

		Returns:
			List of points with matching track ID
		"""
		return [pt for pt in self._points if pt.track_id == track_id]

	def clear(self) -> None:
		"""Clear all accumulated points."""
		self._points.clear()
		self._frame_count = 0

	def reset(self) -> None:
		"""Reset accumulator state."""
		self.clear()

	@property
	def num_points(self) -> int:
		"""Number of currently accumulated points."""
		return len(self._points)

	@property
	def frame_count(self) -> int:
		"""Total frames processed."""
		return self._frame_count

	def to_dict(self) -> dict:
		"""Convert to dictionary for JSON serialization."""
		points = []
		for pt in self._points:
			points.append({
				"x": pt.x,
				"y": pt.y,
				"z": pt.z,
				"velocity": pt.velocity,
				"snr": pt.snr,
				"age": pt.age,
				"track_id": pt.track_id,
			})
		return {
			"points": points,
			"num_points": len(points),
			"persistence_frames": self.config.persistence_frames,
		}


# Color mapping utilities for point cloud visualization
def snr_to_color(snr: float, min_snr: float = 0, max_snr: float = 30) -> tuple[float, float, float]:
	"""Map SNR to RGB color (blue=low, red=high).

	Args:
		snr: SNR value in dB
		min_snr: Minimum SNR for mapping
		max_snr: Maximum SNR for mapping

	Returns:
		RGB tuple (0-1 range)
	"""
	t = np.clip((snr - min_snr) / (max_snr - min_snr), 0, 1)
	# Blue -> Green -> Red gradient
	if t < 0.5:
		return (0, t * 2, 1 - t * 2)
	else:
		return ((t - 0.5) * 2, 1 - (t - 0.5) * 2, 0)


def height_to_color(z: float, min_z: float = -1, max_z: float = 2) -> tuple[float, float, float]:
	"""Map height to RGB color.

	Args:
		z: Height in meters
		min_z: Minimum height for mapping
		max_z: Maximum height for mapping

	Returns:
		RGB tuple (0-1 range)
	"""
	t = np.clip((z - min_z) / (max_z - min_z), 0, 1)
	# Purple -> Cyan gradient
	return (1 - t, t, 1)


def doppler_to_color(velocity: float, max_velocity: float = 5) -> tuple[float, float, float]:
	"""Map Doppler velocity to RGB color (blue=approaching, red=receding).

	Args:
		velocity: Velocity in m/s (negative=approaching)
		max_velocity: Maximum velocity for mapping

	Returns:
		RGB tuple (0-1 range)
	"""
	t = np.clip(velocity / max_velocity, -1, 1)
	if t < 0:
		# Approaching: blue
		return (0, 0, 1 + t)
	else:
		# Receding: red
		return (t, 0, 0)


def age_to_opacity(age: int, max_age: int) -> float:
	"""Map point age to opacity (newer=opaque, older=transparent).

	Args:
		age: Point age in frames
		max_age: Maximum age (persistence frames)

	Returns:
		Opacity value (0-1)
	"""
	return 1.0 - (age / max_age)
