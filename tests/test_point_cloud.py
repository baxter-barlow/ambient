"""Tests for point cloud module."""

from dataclasses import dataclass
from unittest.mock import MagicMock

import numpy as np

from ambient.processing.point_cloud import (
    Point3D,
    PointCloudAccumulator,
    PointCloudConfig,
    age_to_opacity,
    doppler_to_color,
    height_to_color,
    snr_to_color,
)


# Mock DetectedPoint for testing (matches sensor/frame.py structure)
@dataclass
class MockDetectedPoint:
    """Mock detected point for testing."""
    x: float = 0.0
    y: float = 1.0
    z: float = 0.5
    velocity: float = 0.0
    snr: float = 15.0


# Mock CompressedPoint for testing
@dataclass
class MockCompressedPoint:
    """Mock compressed point for testing."""
    range: float = 2.0
    azimuth: float = 0.0
    elevation: float = 0.0
    doppler: float = 0.5
    snr: float = 20.0

    def to_cartesian(self) -> tuple[float, float, float]:
        """Convert spherical to Cartesian coordinates."""
        x = self.range * np.sin(self.azimuth) * np.cos(self.elevation)
        y = self.range * np.cos(self.azimuth) * np.cos(self.elevation)
        z = self.range * np.sin(self.elevation)
        return x, y, z


class TestPoint3D:
    """Tests for Point3D dataclass."""

    def test_default_values(self):
        pt = Point3D(x=1.0, y=2.0, z=0.5)
        assert pt.x == 1.0
        assert pt.y == 2.0
        assert pt.z == 0.5
        assert pt.velocity == 0.0
        assert pt.snr == 0.0
        assert pt.age == 0
        assert pt.track_id == -1
        assert pt.frame_number == 0

    def test_all_values(self):
        pt = Point3D(
            x=1.0, y=2.0, z=0.5,
            velocity=1.5, snr=20.0,
            age=5, track_id=3, frame_number=100,
        )
        assert pt.velocity == 1.5
        assert pt.snr == 20.0
        assert pt.age == 5
        assert pt.track_id == 3
        assert pt.frame_number == 100

    def test_range_property(self):
        pt = Point3D(x=3.0, y=4.0, z=0.0)
        assert pt.range == 5.0  # 3-4-5 triangle

    def test_range_property_3d(self):
        pt = Point3D(x=1.0, y=2.0, z=2.0)
        expected = np.sqrt(1**2 + 2**2 + 2**2)
        assert pt.range == expected

    def test_azimuth_property(self):
        # Point directly in front (positive Y direction)
        pt = Point3D(x=0.0, y=1.0, z=0.0)
        assert pt.azimuth == 0.0

        # Point to the right (positive X)
        pt = Point3D(x=1.0, y=0.0, z=0.0)
        assert np.isclose(pt.azimuth, np.pi / 2)

        # Point to the left (negative X)
        pt = Point3D(x=-1.0, y=0.0, z=0.0)
        assert np.isclose(pt.azimuth, -np.pi / 2)

    def test_elevation_property(self):
        # Point at ground level
        pt = Point3D(x=0.0, y=1.0, z=0.0)
        assert pt.elevation == 0.0

        # Point above (positive Z)
        pt = Point3D(x=0.0, y=1.0, z=1.0)
        assert np.isclose(pt.elevation, np.pi / 4)

        # Point below (negative Z)
        pt = Point3D(x=0.0, y=1.0, z=-1.0)
        assert np.isclose(pt.elevation, -np.pi / 4)

    def test_elevation_at_origin(self):
        """Test elevation when point is directly above/below radar."""
        pt = Point3D(x=0.0, y=0.0, z=1.0)
        assert pt.elevation == 0.0  # r_xy is 0, so returns 0

    def test_to_array(self):
        pt = Point3D(x=1.0, y=2.0, z=3.0, velocity=4.0, snr=5.0, age=6)
        arr = pt.to_array()
        assert arr.dtype == np.float32
        assert len(arr) == 6
        np.testing.assert_array_equal(arr, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


class TestPointCloudConfig:
    """Tests for PointCloudConfig dataclass."""

    def test_default_values(self):
        config = PointCloudConfig()
        assert config.persistence_frames == 10
        assert config.max_points == 1000
        assert config.age_fade is True
        assert config.min_snr_db == 5.0
        assert config.merge_distance == 0.1

    def test_custom_values(self):
        config = PointCloudConfig(
            persistence_frames=20,
            max_points=500,
            min_snr_db=10.0,
        )
        assert config.persistence_frames == 20
        assert config.max_points == 500
        assert config.min_snr_db == 10.0


class TestPointCloudAccumulator:
    """Tests for PointCloudAccumulator class."""

    def test_initialization_default_config(self):
        acc = PointCloudAccumulator()
        assert acc.config is not None
        assert isinstance(acc.config, PointCloudConfig)
        assert acc.num_points == 0
        assert acc.frame_count == 0

    def test_initialization_custom_config(self):
        config = PointCloudConfig(persistence_frames=5, max_points=100)
        acc = PointCloudAccumulator(config=config)
        assert acc.config.persistence_frames == 5
        assert acc.config.max_points == 100

    def test_add_points_empty(self):
        acc = PointCloudAccumulator()
        acc.add_points([])
        assert acc.num_points == 0
        assert acc.frame_count == 1

    def test_add_points_single(self):
        acc = PointCloudAccumulator()
        point = MockDetectedPoint(x=1.0, y=2.0, z=0.5, snr=15.0)
        acc.add_points([point])

        assert acc.num_points == 1
        assert acc.frame_count == 1

        pts = acc.get_points()
        assert len(pts) == 1
        assert pts[0].x == 1.0
        assert pts[0].y == 2.0
        assert pts[0].z == 0.5
        assert pts[0].age == 0

    def test_add_points_multiple(self):
        acc = PointCloudAccumulator()
        points = [
            MockDetectedPoint(x=1.0, y=1.0, z=0.5, snr=15.0),
            MockDetectedPoint(x=2.0, y=2.0, z=0.5, snr=15.0),
            MockDetectedPoint(x=3.0, y=3.0, z=0.5, snr=15.0),
        ]
        acc.add_points(points)

        assert acc.num_points == 3
        pts = acc.get_points()
        assert pts[0].x == 1.0
        assert pts[1].x == 2.0
        assert pts[2].x == 3.0

    def test_add_points_with_track_indices(self):
        acc = PointCloudAccumulator()
        points = [
            MockDetectedPoint(x=1.0, y=1.0, z=0.5, snr=15.0),
            MockDetectedPoint(x=2.0, y=2.0, z=0.5, snr=15.0),
        ]
        track_indices = [0, 1]
        acc.add_points(points, track_indices)

        pts = acc.get_points()
        assert pts[0].track_id == 0
        assert pts[1].track_id == 1

    def test_add_points_filters_low_snr(self):
        config = PointCloudConfig(min_snr_db=10.0)
        acc = PointCloudAccumulator(config=config)

        points = [
            MockDetectedPoint(snr=5.0),   # Below threshold
            MockDetectedPoint(snr=15.0),  # Above threshold
            MockDetectedPoint(snr=8.0),   # Below threshold
        ]
        acc.add_points(points)

        assert acc.num_points == 1  # Only one point above threshold

    def test_point_aging(self):
        acc = PointCloudAccumulator()
        point = MockDetectedPoint(snr=15.0)

        acc.add_points([point])
        assert acc.get_points()[0].age == 0

        acc.add_points([])  # Add empty frame to age existing points
        assert acc.get_points()[0].age == 1

        acc.add_points([])
        assert acc.get_points()[0].age == 2

    def test_point_persistence_removal(self):
        config = PointCloudConfig(persistence_frames=3)
        acc = PointCloudAccumulator(config=config)

        point = MockDetectedPoint(snr=15.0)
        acc.add_points([point])

        # Age the point by adding empty frames
        for _ in range(2):
            acc.add_points([])
            assert acc.num_points == 1  # Point still present

        acc.add_points([])  # This should remove the point (age >= persistence_frames)
        assert acc.num_points == 0

    def test_max_points_limit(self):
        config = PointCloudConfig(max_points=5)
        acc = PointCloudAccumulator(config=config)

        # Add more points than max
        points = [MockDetectedPoint(x=float(i), snr=15.0) for i in range(10)]
        acc.add_points(points)

        assert acc.num_points == 5  # Limited to max_points
        # Newest points should be kept (deque maxlen behavior)
        pts = acc.get_points()
        assert pts[-1].x == 9.0  # Last added point

    def test_get_points_empty(self):
        acc = PointCloudAccumulator()
        pts = acc.get_points()
        assert pts == []

    def test_get_points_array_empty(self):
        acc = PointCloudAccumulator()
        arr = acc.get_points_array()
        assert arr.shape == (0, 6)

    def test_get_points_array(self):
        acc = PointCloudAccumulator()
        points = [
            MockDetectedPoint(x=1.0, y=2.0, z=3.0, velocity=0.5, snr=20.0),
            MockDetectedPoint(x=4.0, y=5.0, z=6.0, velocity=-0.5, snr=15.0),
        ]
        acc.add_points(points)

        arr = acc.get_points_array()
        assert arr.shape == (2, 6)
        assert arr.dtype == np.float32
        np.testing.assert_array_equal(arr[0, :3], [1.0, 2.0, 3.0])
        np.testing.assert_array_equal(arr[1, :3], [4.0, 5.0, 6.0])

    def test_get_points_by_track(self):
        acc = PointCloudAccumulator()
        points = [
            MockDetectedPoint(x=1.0, snr=15.0),
            MockDetectedPoint(x=2.0, snr=15.0),
            MockDetectedPoint(x=3.0, snr=15.0),
            MockDetectedPoint(x=4.0, snr=15.0),
        ]
        track_indices = [0, 1, 0, 1]
        acc.add_points(points, track_indices)

        track0_pts = acc.get_points_by_track(0)
        assert len(track0_pts) == 2
        assert track0_pts[0].x == 1.0
        assert track0_pts[1].x == 3.0

        track1_pts = acc.get_points_by_track(1)
        assert len(track1_pts) == 2
        assert track1_pts[0].x == 2.0
        assert track1_pts[1].x == 4.0

    def test_get_points_by_track_nonexistent(self):
        acc = PointCloudAccumulator()
        points = [MockDetectedPoint(snr=15.0)]
        acc.add_points(points, track_indices=[0])

        pts = acc.get_points_by_track(99)
        assert pts == []

    def test_clear(self):
        acc = PointCloudAccumulator()
        acc.add_points([MockDetectedPoint(snr=15.0)])
        acc.add_points([MockDetectedPoint(snr=15.0)])

        assert acc.num_points == 2
        assert acc.frame_count == 2

        acc.clear()

        assert acc.num_points == 0
        assert acc.frame_count == 0

    def test_reset(self):
        acc = PointCloudAccumulator()
        acc.add_points([MockDetectedPoint(snr=15.0)])

        acc.reset()

        assert acc.num_points == 0
        assert acc.frame_count == 0

    def test_to_dict(self):
        config = PointCloudConfig(persistence_frames=15)
        acc = PointCloudAccumulator(config=config)

        point = MockDetectedPoint(x=1.0, y=2.0, z=0.5, velocity=0.3, snr=20.0)
        acc.add_points([point], track_indices=[5])

        d = acc.to_dict()
        assert d["num_points"] == 1
        assert d["persistence_frames"] == 15
        assert len(d["points"]) == 1
        assert d["points"][0]["x"] == 1.0
        assert d["points"][0]["y"] == 2.0
        assert d["points"][0]["z"] == 0.5
        assert d["points"][0]["velocity"] == 0.3
        assert d["points"][0]["snr"] == 20.0
        assert d["points"][0]["age"] == 0
        assert d["points"][0]["track_id"] == 5

    def test_add_frame_with_detected_points(self):
        acc = PointCloudAccumulator()

        # Create mock frame
        frame = MagicMock()
        frame.detected_points = [
            MockDetectedPoint(x=1.0, y=2.0, z=0.5, snr=15.0),
            MockDetectedPoint(x=3.0, y=4.0, z=1.0, snr=20.0),
        ]
        frame.target_index = None
        frame.compressed_points = None

        acc.add_frame(frame)

        assert acc.num_points == 2
        assert acc.frame_count == 1

    def test_add_frame_with_target_index(self):
        acc = PointCloudAccumulator()

        # Create mock frame with target indices
        frame = MagicMock()
        frame.detected_points = [
            MockDetectedPoint(x=1.0, snr=15.0),
            MockDetectedPoint(x=2.0, snr=15.0),
        ]
        frame.target_index = MagicMock()
        frame.target_index.indices = [0, 1]
        frame.compressed_points = None

        acc.add_frame(frame)

        pts = acc.get_points()
        assert pts[0].track_id == 0
        assert pts[1].track_id == 1

    def test_add_frame_with_compressed_points(self):
        config = PointCloudConfig(min_snr_db=5.0)
        acc = PointCloudAccumulator(config=config)

        # Create mock frame with compressed points
        frame = MagicMock()
        frame.detected_points = []
        frame.target_index = None

        # Mock compressed points
        mock_cp = MagicMock()
        mock_cp.snr = 20.0
        mock_cp.doppler = 0.5
        mock_cp.to_cartesian.return_value = (1.0, 2.0, 0.5)

        frame.compressed_points = MagicMock()
        frame.compressed_points.points = [mock_cp]

        acc.add_frame(frame)

        assert acc.num_points == 1
        pts = acc.get_points()
        assert pts[0].x == 1.0
        assert pts[0].y == 2.0
        assert pts[0].z == 0.5
        assert pts[0].velocity == 0.5  # doppler maps to velocity

    def test_add_frame_filters_low_snr(self):
        config = PointCloudConfig(min_snr_db=10.0)
        acc = PointCloudAccumulator(config=config)

        frame = MagicMock()
        frame.detected_points = [
            MockDetectedPoint(snr=5.0),   # Below threshold
            MockDetectedPoint(snr=15.0),  # Above threshold
        ]
        frame.target_index = None
        frame.compressed_points = None

        acc.add_frame(frame)

        assert acc.num_points == 1


class TestSNRToColor:
    """Tests for snr_to_color utility function."""

    def test_low_snr(self):
        r, g, b = snr_to_color(0, min_snr=0, max_snr=30)
        assert r == 0
        assert g == 0
        assert b == 1  # Blue for low SNR

    def test_high_snr(self):
        r, g, b = snr_to_color(30, min_snr=0, max_snr=30)
        assert r == 1  # Red for high SNR
        assert g == 0
        assert b == 0

    def test_mid_snr(self):
        r, g, b = snr_to_color(15, min_snr=0, max_snr=30)
        # At t=0.5, should be green
        assert r == 0
        assert g == 1
        assert b == 0

    def test_clipping_below_min(self):
        r, g, b = snr_to_color(-10, min_snr=0, max_snr=30)
        assert r == 0
        assert g == 0
        assert b == 1  # Clipped to min

    def test_clipping_above_max(self):
        r, g, b = snr_to_color(50, min_snr=0, max_snr=30)
        assert r == 1  # Clipped to max
        assert g == 0
        assert b == 0


class TestHeightToColor:
    """Tests for height_to_color utility function."""

    def test_low_height(self):
        r, g, b = height_to_color(-1, min_z=-1, max_z=2)
        assert r == 1  # Purple at low height
        assert g == 0
        assert b == 1

    def test_high_height(self):
        r, g, b = height_to_color(2, min_z=-1, max_z=2)
        assert r == 0  # Cyan at high height
        assert g == 1
        assert b == 1

    def test_mid_height(self):
        r, g, b = height_to_color(0.5, min_z=-1, max_z=2)
        # At t=0.5
        assert r == 0.5
        assert g == 0.5
        assert b == 1

    def test_clipping(self):
        # Below min
        r1, g1, b1 = height_to_color(-5, min_z=-1, max_z=2)
        assert r1 == 1
        assert g1 == 0

        # Above max
        r2, g2, b2 = height_to_color(10, min_z=-1, max_z=2)
        assert r2 == 0
        assert g2 == 1


class TestDopplerToColor:
    """Tests for doppler_to_color utility function."""

    def test_approaching(self):
        r, g, b = doppler_to_color(-5, max_velocity=5)
        # Approaching: blue
        assert r == 0
        assert g == 0
        assert b == 0  # 1 + (-1) = 0

    def test_receding(self):
        r, g, b = doppler_to_color(5, max_velocity=5)
        # Receding: red
        assert r == 1
        assert g == 0
        assert b == 0

    def test_stationary(self):
        r, g, b = doppler_to_color(0, max_velocity=5)
        # Stationary: no color
        assert r == 0
        assert g == 0
        assert b == 0

    def test_slow_approach(self):
        r, g, b = doppler_to_color(-2.5, max_velocity=5)
        # Slow approach: partial blue
        assert r == 0
        assert g == 0
        assert b == 0.5

    def test_clipping(self):
        # Very fast approaching
        r, g, b = doppler_to_color(-10, max_velocity=5)
        assert r == 0
        assert g == 0
        assert b == 0  # Clipped to -1 gives 1 + (-1) = 0

        # Very fast receding
        r, g, b = doppler_to_color(10, max_velocity=5)
        assert r == 1  # Clipped to 1
        assert g == 0
        assert b == 0


class TestAgeToOpacity:
    """Tests for age_to_opacity utility function."""

    def test_new_point(self):
        opacity = age_to_opacity(0, max_age=10)
        assert opacity == 1.0

    def test_old_point(self):
        opacity = age_to_opacity(10, max_age=10)
        assert opacity == 0.0

    def test_mid_age(self):
        opacity = age_to_opacity(5, max_age=10)
        assert opacity == 0.5

    def test_quarter_age(self):
        opacity = age_to_opacity(2, max_age=8)
        assert opacity == 0.75


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_zero_snr_point(self):
        acc = PointCloudAccumulator()
        point = MockDetectedPoint(snr=0.0)
        acc.add_points([point])

        # Default min_snr_db is 5.0, so this should be filtered
        assert acc.num_points == 0

    def test_negative_coordinates(self):
        acc = PointCloudAccumulator()
        point = MockDetectedPoint(x=-2.0, y=-3.0, z=-0.5, snr=15.0)
        acc.add_points([point])

        pts = acc.get_points()
        assert pts[0].x == -2.0
        assert pts[0].y == -3.0
        assert pts[0].z == -0.5

    def test_very_large_velocity(self):
        acc = PointCloudAccumulator()
        point = MockDetectedPoint(velocity=100.0, snr=15.0)
        acc.add_points([point])

        pts = acc.get_points()
        assert pts[0].velocity == 100.0

    def test_track_indices_shorter_than_points(self):
        acc = PointCloudAccumulator()
        points = [
            MockDetectedPoint(x=1.0, snr=15.0),
            MockDetectedPoint(x=2.0, snr=15.0),
            MockDetectedPoint(x=3.0, snr=15.0),
        ]
        track_indices = [0]  # Only one track index for three points

        acc.add_points(points, track_indices)

        pts = acc.get_points()
        assert pts[0].track_id == 0
        assert pts[1].track_id == -1  # Default
        assert pts[2].track_id == -1  # Default

    def test_concurrent_add_and_age(self):
        """Test that adding new points while aging old ones works correctly."""
        config = PointCloudConfig(persistence_frames=5)
        acc = PointCloudAccumulator(config=config)

        # Add initial point
        acc.add_points([MockDetectedPoint(x=1.0, snr=15.0)])

        # Add more points over several frames
        for i in range(3):
            acc.add_points([MockDetectedPoint(x=float(i + 2), snr=15.0)])

        # All 4 points should still be present
        assert acc.num_points == 4

        pts = acc.get_points()
        # Check ages
        assert pts[0].age == 3  # Oldest
        assert pts[1].age == 2
        assert pts[2].age == 1
        assert pts[3].age == 0  # Newest

    def test_frame_count_increments(self):
        acc = PointCloudAccumulator()

        for i in range(5):
            acc.add_points([])
            assert acc.frame_count == i + 1

    def test_untracked_points_have_negative_track_id(self):
        acc = PointCloudAccumulator()
        point = MockDetectedPoint(snr=15.0)
        acc.add_points([point])

        pts = acc.get_points()
        assert pts[0].track_id == -1
