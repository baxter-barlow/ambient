"""Fall detection algorithm for radar-based monitoring.

Detects falls by analyzing tracked object trajectories and motion patterns.
Based on TI's fall detection approach using:
- Sudden vertical velocity changes
- Height drops below threshold
- Horizontal spread changes (body orientation)
- Motion cessation after impact
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
	from ambient.sensor.frame import RadarFrame, TrackedObject


class FallState(str, Enum):
	"""Fall detection state machine states."""
	MONITORING = "monitoring"           # Normal monitoring
	FALL_DETECTED = "fall_detected"     # Fall in progress
	IMPACT_DETECTED = "impact_detected" # Impact detected
	LYING_DOWN = "lying_down"           # Person lying down post-fall
	RECOVERED = "recovered"             # Person recovered/stood up


@dataclass
class FallDetectionConfig:
	"""Configuration for fall detection algorithm."""
	# Height thresholds (meters)
	standing_height_min: float = 1.2      # Minimum height for standing
	fall_height_threshold: float = 0.6    # Height below which fall is confirmed
	lying_height_max: float = 0.4         # Maximum height for lying down

	# Velocity thresholds (m/s)
	fall_velocity_threshold: float = -1.5  # Downward velocity indicating fall
	impact_velocity_change: float = 2.0    # Sudden velocity change at impact

	# Time thresholds (seconds)
	fall_duration_max: float = 2.0        # Maximum fall duration
	lying_timeout: float = 5.0            # Time lying down before alert
	recovery_timeout: float = 30.0        # Time to wait for recovery

	# Confidence thresholds
	min_confidence: float = 0.7           # Minimum confidence for detection
	min_track_history: int = 5            # Minimum frames of tracking before detection


@dataclass
class TrackHistory:
	"""History of a tracked object for fall analysis."""
	track_id: int
	positions: deque[tuple[float, float, float]]  # (x, y, z)
	velocities: deque[tuple[float, float, float]]  # (vx, vy, vz)
	timestamps: deque[float]
	heights: deque[float]

	def __init__(self, track_id: int, max_history: int = 50) -> None:
		self.track_id = track_id
		self.positions = deque(maxlen=max_history)
		self.velocities = deque(maxlen=max_history)
		self.timestamps = deque(maxlen=max_history)
		self.heights = deque(maxlen=max_history)

	def add_sample(
		self,
		x: float,
		y: float,
		z: float,
		vx: float,
		vy: float,
		vz: float,
		timestamp: float,
	) -> None:
		"""Add a new sample to the history."""
		self.positions.append((x, y, z))
		self.velocities.append((vx, vy, vz))
		self.timestamps.append(timestamp)
		self.heights.append(z)

	@property
	def current_height(self) -> float:
		"""Current height (z position)."""
		return self.heights[-1] if self.heights else 0.0

	@property
	def current_position(self) -> tuple[float, float, float]:
		"""Current position."""
		return self.positions[-1] if self.positions else (0.0, 0.0, 0.0)

	@property
	def current_velocity(self) -> tuple[float, float, float]:
		"""Current velocity."""
		return self.velocities[-1] if self.velocities else (0.0, 0.0, 0.0)

	@property
	def vertical_velocity(self) -> float:
		"""Current vertical velocity (z component)."""
		return self.velocities[-1][2] if self.velocities else 0.0

	@property
	def height_change_rate(self) -> float:
		"""Rate of height change (m/s) over recent samples."""
		if len(self.heights) < 2 or len(self.timestamps) < 2:
			return 0.0
		dt = self.timestamps[-1] - self.timestamps[-2]
		if dt <= 0:
			return 0.0
		return (self.heights[-1] - self.heights[-2]) / dt

	def get_height_stats(self, window_seconds: float = 1.0) -> tuple[float, float, float]:
		"""Get height statistics over a time window.

		Returns:
			Tuple of (min_height, max_height, avg_height)
		"""
		if not self.heights or not self.timestamps:
			return 0.0, 0.0, 0.0

		cutoff_time = self.timestamps[-1] - window_seconds
		recent_heights = [
			h for h, t in zip(self.heights, self.timestamps)
			if t >= cutoff_time
		]

		if not recent_heights:
			return self.heights[-1], self.heights[-1], self.heights[-1]

		return min(recent_heights), max(recent_heights), float(np.mean(recent_heights))

	def get_velocity_magnitude(self) -> float:
		"""Get current velocity magnitude."""
		vx, vy, vz = self.current_velocity
		return np.sqrt(vx**2 + vy**2 + vz**2)


@dataclass
class FallEvent:
	"""Represents a detected fall event."""
	track_id: int
	state: FallState
	confidence: float
	timestamp: float
	start_time: float
	position: tuple[float, float, float]
	fall_height: float          # Height from which fall started
	impact_height: float        # Height at impact
	duration: float = 0.0       # Fall duration in seconds
	lying_duration: float = 0.0 # Time spent lying down

	def to_dict(self) -> dict:
		"""Convert to dictionary for serialization."""
		return {
			"track_id": self.track_id,
			"state": self.state.value,
			"confidence": self.confidence,
			"timestamp": self.timestamp,
			"start_time": self.start_time,
			"position": {"x": self.position[0], "y": self.position[1], "z": self.position[2]},
			"fall_height": self.fall_height,
			"impact_height": self.impact_height,
			"duration": self.duration,
			"lying_duration": self.lying_duration,
		}


@dataclass
class FallDetectionResult:
	"""Result of fall detection analysis."""
	fall_detected: bool = False
	confidence: float = 0.0
	event: FallEvent | None = None
	active_tracks: int = 0
	timestamp: float = field(default_factory=time.time)

	def to_dict(self) -> dict:
		"""Convert to dictionary for serialization."""
		return {
			"fall_detected": self.fall_detected,
			"confidence": self.confidence,
			"event": self.event.to_dict() if self.event else None,
			"active_tracks": self.active_tracks,
			"timestamp": self.timestamp,
		}


class FallDetector:
	"""Fall detection using tracked object trajectories.

	Implements a state machine approach:
	1. MONITORING: Normal state, watching for fall indicators
	2. FALL_DETECTED: Rapid downward motion detected
	3. IMPACT_DETECTED: Sudden velocity change detected
	4. LYING_DOWN: Low height maintained post-impact
	5. RECOVERED: Person stood back up

	Example:
		detector = FallDetector(FallDetectionConfig())

		for frame in frame_stream:
			result = detector.process_frame(frame)
			if result.fall_detected:
				alert_caregiver(result.event)
	"""

	def __init__(self, config: FallDetectionConfig | None = None) -> None:
		self.config = config or FallDetectionConfig()
		self._track_histories: dict[int, TrackHistory] = {}
		self._active_events: dict[int, FallEvent] = {}
		self._completed_events: list[FallEvent] = []
		self._frame_count = 0

	def process_frame(self, frame: RadarFrame) -> FallDetectionResult:
		"""Process a radar frame for fall detection.

		Args:
			frame: RadarFrame with tracked objects

		Returns:
			FallDetectionResult with detection status
		"""
		self._frame_count += 1
		current_time = time.time()

		result = FallDetectionResult(
			timestamp=current_time,
			active_tracks=0,
		)

		# Process tracked objects if available
		if frame.tracked_objects:
			result.active_tracks = len(frame.tracked_objects.objects)

			for obj in frame.tracked_objects.objects:
				self._update_track_history(obj, current_time)
				event = self._analyze_track(obj.track_id, current_time)

				if event and event.confidence >= self.config.min_confidence:
					if event.state in (FallState.FALL_DETECTED, FallState.IMPACT_DETECTED, FallState.LYING_DOWN):
						result.fall_detected = True
						result.confidence = max(result.confidence, event.confidence)
						result.event = event

		# Clean up old tracks
		self._cleanup_old_tracks(current_time)

		return result

	def process_tracked_objects(
		self,
		objects: list[TrackedObject],
		timestamp: float | None = None,
	) -> FallDetectionResult:
		"""Process tracked objects directly without a frame.

		Args:
			objects: List of TrackedObject instances
			timestamp: Optional timestamp (uses current time if not provided)

		Returns:
			FallDetectionResult with detection status
		"""
		current_time = timestamp or time.time()

		result = FallDetectionResult(
			timestamp=current_time,
			active_tracks=len(objects),
		)

		for obj in objects:
			self._update_track_history(obj, current_time)
			event = self._analyze_track(obj.track_id, current_time)

			if event and event.confidence >= self.config.min_confidence:
				if event.state in (FallState.FALL_DETECTED, FallState.IMPACT_DETECTED, FallState.LYING_DOWN):
					result.fall_detected = True
					result.confidence = max(result.confidence, event.confidence)
					result.event = event

		self._cleanup_old_tracks(current_time)
		return result

	def _update_track_history(self, obj: TrackedObject, timestamp: float) -> None:
		"""Update track history with new observation."""
		if obj.track_id not in self._track_histories:
			self._track_histories[obj.track_id] = TrackHistory(obj.track_id)

		history = self._track_histories[obj.track_id]
		history.add_sample(
			x=obj.x,
			y=obj.y,
			z=obj.z,
			vx=obj.vx,
			vy=obj.vy,
			vz=obj.vz,
			timestamp=timestamp,
		)

	def _analyze_track(self, track_id: int, current_time: float) -> FallEvent | None:
		"""Analyze a track for fall indicators.

		Returns:
			FallEvent if fall detected, None otherwise
		"""
		history = self._track_histories.get(track_id)
		if not history or len(history.heights) < self.config.min_track_history:
			return None

		# Check if we have an active event for this track
		if track_id in self._active_events:
			return self._update_active_event(track_id, history, current_time)

		# Check for new fall
		return self._detect_new_fall(track_id, history, current_time)

	def _detect_new_fall(
		self,
		track_id: int,
		history: TrackHistory,
		current_time: float,
	) -> FallEvent | None:
		"""Detect a new fall event."""
		# Get height statistics
		min_height, max_height, avg_height = history.get_height_stats(window_seconds=1.0)
		current_height = history.current_height
		vertical_velocity = history.vertical_velocity

		# Check for rapid downward motion
		if vertical_velocity < self.config.fall_velocity_threshold:
			confidence = self._calculate_fall_confidence(history)

			if confidence >= self.config.min_confidence:
				event = FallEvent(
					track_id=track_id,
					state=FallState.FALL_DETECTED,
					confidence=confidence,
					timestamp=current_time,
					start_time=current_time,
					position=history.current_position,
					fall_height=max_height,
					impact_height=current_height,
				)
				self._active_events[track_id] = event
				return event

		# Check for sudden height drop (person already fell)
		height_drop = max_height - current_height
		if height_drop > 0.5 and current_height < self.config.fall_height_threshold:
			confidence = min(1.0, height_drop / 1.0)  # Confidence based on drop magnitude

			if confidence >= self.config.min_confidence:
				event = FallEvent(
					track_id=track_id,
					state=FallState.IMPACT_DETECTED,
					confidence=confidence,
					timestamp=current_time,
					start_time=current_time,
					position=history.current_position,
					fall_height=max_height,
					impact_height=current_height,
				)
				self._active_events[track_id] = event
				return event

		return None

	def _update_active_event(
		self,
		track_id: int,
		history: TrackHistory,
		current_time: float,
	) -> FallEvent:
		"""Update an active fall event."""
		event = self._active_events[track_id]
		current_height = history.current_height
		velocity_mag = history.get_velocity_magnitude()

		event.duration = current_time - event.start_time
		event.position = history.current_position
		event.impact_height = min(event.impact_height, current_height)
		event.timestamp = current_time

		# State machine transitions
		if event.state == FallState.FALL_DETECTED:
			# Check for impact (sudden velocity reduction)
			if velocity_mag < 0.3 and current_height < self.config.fall_height_threshold:
				event.state = FallState.IMPACT_DETECTED
				event.confidence = min(1.0, event.confidence + 0.1)

			# Check for recovery (person caught themselves)
			elif current_height > self.config.standing_height_min:
				event.state = FallState.RECOVERED
				self._complete_event(track_id)

		elif event.state == FallState.IMPACT_DETECTED:
			# Check if person is lying down
			if current_height < self.config.lying_height_max and velocity_mag < 0.2:
				event.state = FallState.LYING_DOWN
				event.lying_duration = 0.0

			# Check for quick recovery
			elif current_height > self.config.standing_height_min:
				event.state = FallState.RECOVERED
				self._complete_event(track_id)

		elif event.state == FallState.LYING_DOWN:
			event.lying_duration = current_time - event.start_time - event.duration

			# Check for recovery
			if current_height > self.config.standing_height_min:
				event.state = FallState.RECOVERED
				self._complete_event(track_id)

			# Increase confidence over time if still lying down
			if event.lying_duration > self.config.lying_timeout:
				event.confidence = min(1.0, event.confidence + 0.05)

		# Update confidence based on current state
		event.confidence = self._calculate_fall_confidence(history, event)

		return event

	def _calculate_fall_confidence(
		self,
		history: TrackHistory,
		event: FallEvent | None = None,
	) -> float:
		"""Calculate confidence score for fall detection."""
		confidence = 0.0

		# Factor 1: Vertical velocity
		vz = history.vertical_velocity
		if vz < self.config.fall_velocity_threshold:
			velocity_factor = min(1.0, abs(vz) / 3.0)
			confidence += 0.3 * velocity_factor

		# Factor 2: Height drop
		min_h, max_h, _ = history.get_height_stats(window_seconds=2.0)
		height_drop = max_h - min_h
		if height_drop > 0.3:
			drop_factor = min(1.0, height_drop / 1.2)
			confidence += 0.3 * drop_factor

		# Factor 3: Current height below threshold
		current_height = history.current_height
		if current_height < self.config.fall_height_threshold:
			height_factor = 1.0 - (current_height / self.config.fall_height_threshold)
			confidence += 0.2 * height_factor

		# Factor 4: Low velocity after fall (impact)
		velocity_mag = history.get_velocity_magnitude()
		if velocity_mag < 0.3:
			confidence += 0.1

		# Factor 5: Time lying down
		if event and event.lying_duration > 0:
			lying_factor = min(1.0, event.lying_duration / self.config.lying_timeout)
			confidence += 0.1 * lying_factor

		return min(1.0, confidence)

	def _complete_event(self, track_id: int) -> None:
		"""Move event from active to completed."""
		if track_id in self._active_events:
			event = self._active_events.pop(track_id)
			self._completed_events.append(event)

	def _cleanup_old_tracks(self, current_time: float, max_age: float = 5.0) -> None:
		"""Remove tracks that haven't been updated recently."""
		to_remove = []
		for track_id, history in self._track_histories.items():
			if history.timestamps and current_time - history.timestamps[-1] > max_age:
				to_remove.append(track_id)

		for track_id in to_remove:
			del self._track_histories[track_id]
			if track_id in self._active_events:
				self._complete_event(track_id)

	def get_active_events(self) -> list[FallEvent]:
		"""Get all active fall events."""
		return list(self._active_events.values())

	def get_completed_events(self) -> list[FallEvent]:
		"""Get all completed fall events."""
		return self._completed_events.copy()

	def clear_events(self) -> None:
		"""Clear all events."""
		self._active_events.clear()
		self._completed_events.clear()

	def reset(self) -> None:
		"""Reset detector state."""
		self._track_histories.clear()
		self._active_events.clear()
		self._completed_events.clear()
		self._frame_count = 0
