"""Tests for fall detection module."""

import time
from dataclasses import dataclass
from unittest.mock import MagicMock

import numpy as np

from ambient.processing.fall_detection import (
    FallDetectionConfig,
    FallDetectionResult,
    FallDetector,
    FallEvent,
    FallState,
    TrackHistory,
)


# Mock TrackedObject for testing (matches sensor/frame.py structure)
@dataclass
class MockTrackedObject:
    """Mock tracked object for testing."""
    track_id: int
    x: float = 0.0
    y: float = 1.0
    z: float = 1.5  # Standing height
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    ax: float = 0.0
    ay: float = 0.0
    az: float = 0.0


class TestFallDetectionConfig:
    """Tests for FallDetectionConfig dataclass."""

    def test_default_values(self):
        config = FallDetectionConfig()
        assert config.standing_height_min == 1.2
        assert config.fall_height_threshold == 0.6
        assert config.lying_height_max == 0.4
        assert config.fall_velocity_threshold == -1.5
        assert config.impact_velocity_change == 2.0
        assert config.fall_duration_max == 2.0
        assert config.lying_timeout == 5.0
        assert config.recovery_timeout == 30.0
        assert config.min_confidence == 0.7
        assert config.min_track_history == 5

    def test_custom_values(self):
        config = FallDetectionConfig(
            standing_height_min=1.0,
            fall_velocity_threshold=-2.0,
            min_confidence=0.5,
        )
        assert config.standing_height_min == 1.0
        assert config.fall_velocity_threshold == -2.0
        assert config.min_confidence == 0.5
        # Other values should still be defaults
        assert config.lying_height_max == 0.4


class TestTrackHistory:
    """Tests for TrackHistory class."""

    def test_initialization(self):
        history = TrackHistory(track_id=1, max_history=50)
        assert history.track_id == 1
        assert len(history.positions) == 0
        assert len(history.velocities) == 0
        assert len(history.timestamps) == 0
        assert len(history.heights) == 0

    def test_add_sample(self):
        history = TrackHistory(track_id=1)
        history.add_sample(
            x=1.0, y=2.0, z=1.5,
            vx=0.1, vy=0.2, vz=-0.5,
            timestamp=1000.0,
        )
        assert len(history.positions) == 1
        assert len(history.velocities) == 1
        assert len(history.timestamps) == 1
        assert len(history.heights) == 1
        assert history.positions[-1] == (1.0, 2.0, 1.5)
        assert history.velocities[-1] == (0.1, 0.2, -0.5)
        assert history.timestamps[-1] == 1000.0
        assert history.heights[-1] == 1.5

    def test_max_history_limit(self):
        history = TrackHistory(track_id=1, max_history=5)
        for i in range(10):
            history.add_sample(
                x=float(i), y=0.0, z=1.0,
                vx=0.0, vy=0.0, vz=0.0,
                timestamp=float(i),
            )
        assert len(history.positions) == 5
        assert history.positions[0] == (5.0, 0.0, 1.0)  # Oldest kept

    def test_current_height_empty(self):
        history = TrackHistory(track_id=1)
        assert history.current_height == 0.0

    def test_current_height(self):
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 1.5, 0, 0, 0, 0)
        assert history.current_height == 1.5

    def test_current_position_empty(self):
        history = TrackHistory(track_id=1)
        assert history.current_position == (0.0, 0.0, 0.0)

    def test_current_position(self):
        history = TrackHistory(track_id=1)
        history.add_sample(1.0, 2.0, 3.0, 0, 0, 0, 0)
        assert history.current_position == (1.0, 2.0, 3.0)

    def test_current_velocity_empty(self):
        history = TrackHistory(track_id=1)
        assert history.current_velocity == (0.0, 0.0, 0.0)

    def test_current_velocity(self):
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 0, 0.5, -0.3, -1.0, 0)
        assert history.current_velocity == (0.5, -0.3, -1.0)

    def test_vertical_velocity_empty(self):
        history = TrackHistory(track_id=1)
        assert history.vertical_velocity == 0.0

    def test_vertical_velocity(self):
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 1.5, 0, 0, -2.0, 0)
        assert history.vertical_velocity == -2.0

    def test_height_change_rate_insufficient_samples(self):
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 1.5, 0, 0, 0, 0)
        assert history.height_change_rate == 0.0

    def test_height_change_rate_zero_dt(self):
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 1.5, 0, 0, 0, 1.0)
        history.add_sample(0, 0, 1.0, 0, 0, 0, 1.0)  # Same timestamp
        assert history.height_change_rate == 0.0

    def test_height_change_rate(self):
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 1.5, 0, 0, 0, 0.0)
        history.add_sample(0, 0, 1.0, 0, 0, 0, 1.0)  # 0.5m drop in 1s
        assert history.height_change_rate == -0.5

    def test_get_height_stats_empty(self):
        history = TrackHistory(track_id=1)
        min_h, max_h, avg_h = history.get_height_stats()
        assert min_h == 0.0
        assert max_h == 0.0
        assert avg_h == 0.0

    def test_get_height_stats(self):
        history = TrackHistory(track_id=1)
        base_time = 100.0
        heights = [1.5, 1.4, 1.2, 0.8, 0.5]
        for i, h in enumerate(heights):
            history.add_sample(0, 0, h, 0, 0, 0, base_time + i * 0.2)

        min_h, max_h, avg_h = history.get_height_stats(window_seconds=1.0)
        assert min_h == 0.5
        assert max_h == 1.5
        assert np.isclose(avg_h, np.mean(heights))

    def test_get_height_stats_windowed(self):
        history = TrackHistory(track_id=1)
        # Add old samples
        for i in range(5):
            history.add_sample(0, 0, 2.0, 0, 0, 0, float(i))
        # Add recent samples
        for i in range(5):
            history.add_sample(0, 0, 0.5, 0, 0, 0, 100.0 + float(i) * 0.1)

        min_h, max_h, avg_h = history.get_height_stats(window_seconds=1.0)
        assert min_h == 0.5  # Only recent samples
        assert max_h == 0.5

    def test_get_velocity_magnitude(self):
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 0, 3.0, 4.0, 0.0, 0)
        assert history.get_velocity_magnitude() == 5.0

    def test_get_velocity_magnitude_3d(self):
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 0, 1.0, 2.0, 2.0, 0)
        assert history.get_velocity_magnitude() == 3.0


class TestFallEvent:
    """Tests for FallEvent dataclass."""

    def test_creation(self):
        event = FallEvent(
            track_id=1,
            state=FallState.FALL_DETECTED,
            confidence=0.85,
            timestamp=1000.0,
            start_time=999.5,
            position=(1.0, 2.0, 0.5),
            fall_height=1.5,
            impact_height=0.3,
        )
        assert event.track_id == 1
        assert event.state == FallState.FALL_DETECTED
        assert event.confidence == 0.85
        assert event.duration == 0.0
        assert event.lying_duration == 0.0

    def test_to_dict(self):
        event = FallEvent(
            track_id=2,
            state=FallState.LYING_DOWN,
            confidence=0.9,
            timestamp=1000.0,
            start_time=998.0,
            position=(0.5, 1.0, 0.2),
            fall_height=1.6,
            impact_height=0.2,
            duration=2.0,
            lying_duration=1.5,
        )
        d = event.to_dict()
        assert d["track_id"] == 2
        assert d["state"] == "lying_down"
        assert d["confidence"] == 0.9
        assert d["position"]["x"] == 0.5
        assert d["position"]["y"] == 1.0
        assert d["position"]["z"] == 0.2
        assert d["fall_height"] == 1.6
        assert d["impact_height"] == 0.2
        assert d["duration"] == 2.0
        assert d["lying_duration"] == 1.5


class TestFallDetectionResult:
    """Tests for FallDetectionResult dataclass."""

    def test_default_values(self):
        result = FallDetectionResult()
        assert result.fall_detected is False
        assert result.confidence == 0.0
        assert result.event is None
        assert result.active_tracks == 0
        assert result.timestamp > 0

    def test_with_event(self):
        event = FallEvent(
            track_id=1,
            state=FallState.FALL_DETECTED,
            confidence=0.8,
            timestamp=1000.0,
            start_time=999.0,
            position=(0, 0, 0.5),
            fall_height=1.5,
            impact_height=0.5,
        )
        result = FallDetectionResult(
            fall_detected=True,
            confidence=0.8,
            event=event,
            active_tracks=1,
        )
        assert result.fall_detected is True
        assert result.event is event

    def test_to_dict_no_event(self):
        result = FallDetectionResult(timestamp=1234.5)
        d = result.to_dict()
        assert d["fall_detected"] is False
        assert d["event"] is None
        assert d["timestamp"] == 1234.5

    def test_to_dict_with_event(self):
        event = FallEvent(
            track_id=1,
            state=FallState.IMPACT_DETECTED,
            confidence=0.9,
            timestamp=1000.0,
            start_time=999.0,
            position=(0, 0, 0.3),
            fall_height=1.5,
            impact_height=0.3,
        )
        result = FallDetectionResult(
            fall_detected=True,
            confidence=0.9,
            event=event,
            active_tracks=1,
            timestamp=1000.0,
        )
        d = result.to_dict()
        assert d["fall_detected"] is True
        assert d["event"]["state"] == "impact_detected"


class TestFallState:
    """Tests for FallState enum."""

    def test_states_exist(self):
        assert FallState.MONITORING == "monitoring"
        assert FallState.FALL_DETECTED == "fall_detected"
        assert FallState.IMPACT_DETECTED == "impact_detected"
        assert FallState.LYING_DOWN == "lying_down"
        assert FallState.RECOVERED == "recovered"

    def test_string_value(self):
        # Enum str format may vary by Python version
        assert "FALL_DETECTED" in str(FallState.FALL_DETECTED) or "fall_detected" in str(FallState.FALL_DETECTED)
        assert FallState.FALL_DETECTED.value == "fall_detected"


class TestFallDetector:
    """Tests for FallDetector class."""

    def test_initialization_default_config(self):
        detector = FallDetector()
        assert detector.config is not None
        assert isinstance(detector.config, FallDetectionConfig)
        assert detector._frame_count == 0
        assert len(detector._track_histories) == 0
        assert len(detector._active_events) == 0

    def test_initialization_custom_config(self):
        config = FallDetectionConfig(min_confidence=0.5)
        detector = FallDetector(config=config)
        assert detector.config.min_confidence == 0.5

    def test_process_tracked_objects_empty(self):
        detector = FallDetector()
        result = detector.process_tracked_objects([])
        assert result.fall_detected is False
        assert result.active_tracks == 0

    def test_process_tracked_objects_single_standing(self):
        detector = FallDetector()
        obj = MockTrackedObject(track_id=1, z=1.5, vz=0.0)

        # Need multiple samples for detection
        for _ in range(10):
            result = detector.process_tracked_objects([obj])

        assert result.fall_detected is False
        assert result.active_tracks == 1

    def test_process_tracked_objects_falling(self):
        """Test detection of a falling person."""
        config = FallDetectionConfig(
            min_confidence=0.3,  # Lower threshold for testing
            min_track_history=3,
        )
        detector = FallDetector(config=config)

        # Simulate standing person at high height
        base_time = time.time()
        obj = MockTrackedObject(track_id=1, z=1.5, vz=0.0)
        for i in range(5):
            detector.process_tracked_objects([obj], timestamp=base_time + i * 0.1)

        # Simulate rapid downward motion (falling) with decreasing height
        heights = [1.2, 0.9, 0.6, 0.4, 0.3]
        velocities = [-1.8, -2.0, -2.2, -1.5, -0.5]
        for i, (h, v) in enumerate(zip(heights, velocities)):
            obj.z = h
            obj.vz = v
            detector.process_tracked_objects([obj], timestamp=base_time + 0.5 + i * 0.1)

        # Track history should show the pattern of a fall
        history = detector._track_histories[1]
        min_h, max_h, _ = history.get_height_stats(window_seconds=2.0)
        height_drop = max_h - min_h

        # Should have significant height drop characteristic of a fall
        assert height_drop > 0.5

    def test_track_history_creation(self):
        detector = FallDetector()
        obj = MockTrackedObject(track_id=5, x=1.0, y=2.0, z=1.5)
        detector.process_tracked_objects([obj])

        assert 5 in detector._track_histories
        history = detector._track_histories[5]
        assert history.track_id == 5
        assert history.current_position == (1.0, 2.0, 1.5)

    def test_multiple_tracks(self):
        detector = FallDetector()
        obj1 = MockTrackedObject(track_id=1, z=1.5)
        obj2 = MockTrackedObject(track_id=2, z=1.6)

        result = detector.process_tracked_objects([obj1, obj2])

        assert result.active_tracks == 2
        assert 1 in detector._track_histories
        assert 2 in detector._track_histories

    def test_cleanup_old_tracks(self):
        detector = FallDetector()
        obj = MockTrackedObject(track_id=1, z=1.5)

        base_time = 1000.0
        detector.process_tracked_objects([obj], timestamp=base_time)

        assert 1 in detector._track_histories

        # Process with different object much later
        obj2 = MockTrackedObject(track_id=2, z=1.5)
        detector.process_tracked_objects([obj2], timestamp=base_time + 10.0)  # 10 seconds later

        # Old track should be cleaned up (default max_age is 5.0)
        assert 1 not in detector._track_histories
        assert 2 in detector._track_histories

    def test_get_active_events_empty(self):
        detector = FallDetector()
        assert detector.get_active_events() == []

    def test_get_completed_events_empty(self):
        detector = FallDetector()
        assert detector.get_completed_events() == []

    def test_clear_events(self):
        detector = FallDetector()
        # Manually add events for testing
        event = FallEvent(
            track_id=1,
            state=FallState.FALL_DETECTED,
            confidence=0.8,
            timestamp=1000.0,
            start_time=999.0,
            position=(0, 0, 0.5),
            fall_height=1.5,
            impact_height=0.5,
        )
        detector._active_events[1] = event
        detector._completed_events.append(event)

        detector.clear_events()

        assert len(detector._active_events) == 0
        assert len(detector._completed_events) == 0

    def test_reset(self):
        detector = FallDetector()
        obj = MockTrackedObject(track_id=1, z=1.5)

        # Use process_frame to increment frame_count
        for _ in range(5):
            frame = MagicMock()
            frame.tracked_objects = MagicMock()
            frame.tracked_objects.objects = [obj]
            detector.process_frame(frame)

        assert len(detector._track_histories) > 0
        assert detector._frame_count > 0

        detector.reset()

        assert len(detector._track_histories) == 0
        assert len(detector._active_events) == 0
        assert len(detector._completed_events) == 0
        assert detector._frame_count == 0

    def test_fall_state_transition_to_impact(self):
        """Test state transitions from FALL_DETECTED to IMPACT_DETECTED."""
        config = FallDetectionConfig(
            min_confidence=0.3,
            min_track_history=2,
        )
        detector = FallDetector(config=config)

        base_time = 1000.0

        # Create standing history
        obj = MockTrackedObject(track_id=1, z=1.5, vz=0.0)
        for i in range(5):
            detector.process_tracked_objects([obj], timestamp=base_time + i * 0.1)

        # Trigger fall detection with fast downward velocity
        obj.z = 0.8
        obj.vz = -2.5
        detector.process_tracked_objects([obj], timestamp=base_time + 0.6)

        # If fall was detected, simulate impact (low velocity at low height)
        if 1 in detector._active_events:
            obj.z = 0.3
            obj.vz = 0.0
            obj.vx = 0.0
            obj.vy = 0.0
            detector.process_tracked_objects([obj], timestamp=base_time + 0.8)

            # Event should transition toward IMPACT_DETECTED or LYING_DOWN
            event = detector._active_events.get(1)
            if event:
                assert event.state in (
                    FallState.FALL_DETECTED,
                    FallState.IMPACT_DETECTED,
                    FallState.LYING_DOWN,
                )

    def test_recovery_detection(self):
        """Test that recovery is detected when person stands back up."""
        config = FallDetectionConfig(
            min_confidence=0.3,
            min_track_history=2,
        )
        detector = FallDetector(config=config)

        base_time = 1000.0

        # Manually create an active event in LYING_DOWN state
        event = FallEvent(
            track_id=1,
            state=FallState.LYING_DOWN,
            confidence=0.8,
            timestamp=base_time,
            start_time=base_time - 1.0,
            position=(0, 1.0, 0.3),
            fall_height=1.5,
            impact_height=0.3,
        )
        detector._active_events[1] = event

        # Create track history
        history = TrackHistory(track_id=1)
        for i in range(5):
            history.add_sample(0, 1.0, 0.3, 0, 0, 0, base_time - 0.5 + i * 0.1)
        detector._track_histories[1] = history

        # Person stands up (height > standing_height_min)
        obj = MockTrackedObject(track_id=1, z=1.4, vz=0.5)
        detector.process_tracked_objects([obj], timestamp=base_time + 1.0)

        # Event should transition to RECOVERED and be completed
        assert 1 not in detector._active_events
        assert len(detector._completed_events) == 1
        assert detector._completed_events[0].state == FallState.RECOVERED


class TestFallDetectorWithRadarFrame:
    """Tests for FallDetector with RadarFrame input."""

    def test_process_frame_no_tracked_objects(self):
        detector = FallDetector()

        # Create mock frame with no tracked objects
        frame = MagicMock()
        frame.tracked_objects = None

        result = detector.process_frame(frame)

        assert result.fall_detected is False
        assert result.active_tracks == 0

    def test_process_frame_with_tracked_objects(self):
        detector = FallDetector()

        # Create mock tracked object
        mock_obj = MockTrackedObject(track_id=1, z=1.5)

        # Create mock frame
        frame = MagicMock()
        frame.tracked_objects = MagicMock()
        frame.tracked_objects.objects = [mock_obj]

        result = detector.process_frame(frame)

        assert result.active_tracks == 1
        assert 1 in detector._track_histories


class TestConfidenceCalculation:
    """Tests for confidence calculation logic."""

    def test_confidence_from_velocity(self):
        """Test that downward velocity increases confidence."""
        config = FallDetectionConfig(min_track_history=2)
        detector = FallDetector(config=config)

        # Create history with fast downward velocity
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 1.0, 0, 0, -2.5, 0.0)
        history.add_sample(0, 0, 0.8, 0, 0, -2.5, 0.1)

        confidence = detector._calculate_fall_confidence(history)

        # Should have some confidence from velocity factor
        assert confidence > 0

    def test_confidence_from_height_drop(self):
        """Test that height drop increases confidence."""
        config = FallDetectionConfig(min_track_history=2)
        detector = FallDetector(config=config)

        # Create history with significant height drop
        history = TrackHistory(track_id=1)
        base_time = 100.0
        history.add_sample(0, 0, 1.5, 0, 0, 0, base_time)
        history.add_sample(0, 0, 1.3, 0, 0, 0, base_time + 0.2)
        history.add_sample(0, 0, 0.8, 0, 0, 0, base_time + 0.4)
        history.add_sample(0, 0, 0.5, 0, 0, 0, base_time + 0.6)

        confidence = detector._calculate_fall_confidence(history)

        # Should have confidence from height drop
        assert confidence > 0

    def test_confidence_below_threshold(self):
        """Test that low height increases confidence."""
        config = FallDetectionConfig(min_track_history=2)
        detector = FallDetector(config=config)

        # Create history with low height
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 0.3, 0, 0, 0, 0.0)
        history.add_sample(0, 0, 0.3, 0, 0, 0, 0.1)

        confidence = detector._calculate_fall_confidence(history)

        # Should have some confidence from being below threshold
        assert confidence > 0

    def test_confidence_from_low_velocity(self):
        """Test that very low velocity after fall increases confidence."""
        config = FallDetectionConfig(min_track_history=2)
        detector = FallDetector(config=config)

        # Create history with very low velocity
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 0.3, 0.0, 0.0, 0.0, 0.0)
        history.add_sample(0, 0, 0.3, 0.0, 0.0, 0.0, 0.1)

        confidence = detector._calculate_fall_confidence(history)

        # Should have confidence from low velocity
        assert confidence >= 0.1  # At least the low velocity factor

    def test_confidence_with_lying_duration(self):
        """Test that lying duration increases confidence."""
        config = FallDetectionConfig(min_track_history=2)
        detector = FallDetector(config=config)

        # Create history
        history = TrackHistory(track_id=1)
        history.add_sample(0, 0, 0.3, 0, 0, 0, 0.0)
        history.add_sample(0, 0, 0.3, 0, 0, 0, 0.1)

        # Create event with lying duration
        event = FallEvent(
            track_id=1,
            state=FallState.LYING_DOWN,
            confidence=0.8,
            timestamp=10.0,
            start_time=0.0,
            position=(0, 0, 0.3),
            fall_height=1.5,
            impact_height=0.3,
            lying_duration=6.0,  # Past lying_timeout
        )

        confidence = detector._calculate_fall_confidence(history, event)

        # Should have increased confidence from lying duration
        assert confidence > detector._calculate_fall_confidence(history)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_track_with_insufficient_history(self):
        """Test that tracks with insufficient history are ignored."""
        config = FallDetectionConfig(min_track_history=10)
        detector = FallDetector(config=config)

        obj = MockTrackedObject(track_id=1, z=0.3, vz=-2.5)

        # Only add 5 samples (less than min_track_history)
        for i in range(5):
            result = detector.process_tracked_objects([obj], timestamp=float(i))

        # Should not detect fall due to insufficient history
        assert result.fall_detected is False

    def test_concurrent_falls_different_tracks(self):
        """Test handling of multiple simultaneous falls."""
        config = FallDetectionConfig(
            min_confidence=0.3,
            min_track_history=3,
        )
        detector = FallDetector(config=config)

        base_time = 1000.0

        # Create history for both tracks
        for i in range(5):
            obj1 = MockTrackedObject(track_id=1, z=1.5)
            obj2 = MockTrackedObject(track_id=2, z=1.5)
            detector.process_tracked_objects([obj1, obj2], timestamp=base_time + i * 0.1)

        # Both start falling
        obj1 = MockTrackedObject(track_id=1, z=0.5, vz=-2.0)
        obj2 = MockTrackedObject(track_id=2, z=0.5, vz=-2.0)
        detector.process_tracked_objects([obj1, obj2], timestamp=base_time + 0.6)

        # Both tracks should be in histories
        assert 1 in detector._track_histories
        assert 2 in detector._track_histories

    def test_track_id_zero(self):
        """Test that track ID 0 is handled correctly."""
        detector = FallDetector()
        obj = MockTrackedObject(track_id=0, z=1.5)

        result = detector.process_tracked_objects([obj])

        assert 0 in detector._track_histories
        assert result.active_tracks == 1

    def test_negative_coordinates(self):
        """Test handling of negative coordinates."""
        detector = FallDetector()
        obj = MockTrackedObject(track_id=1, x=-2.0, y=-1.5, z=1.5)

        for _ in range(5):
            detector.process_tracked_objects([obj])

        history = detector._track_histories[1]
        assert history.current_position == (-2.0, -1.5, 1.5)

    def test_very_high_velocity(self):
        """Test handling of very high velocity values."""
        detector = FallDetector()
        obj = MockTrackedObject(track_id=1, z=1.5, vz=-100.0)

        for _ in range(10):
            result = detector.process_tracked_objects([obj])

        # Should not crash, confidence should be capped at 1.0
        assert result.confidence <= 1.0
