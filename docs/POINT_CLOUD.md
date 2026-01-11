# Point Cloud Module

The point cloud module (`src/ambient/processing/point_cloud.py`) provides point cloud accumulation and visualization utilities for radar data.

## Overview

Radar point clouds are sparse and noisy. This module:
- **Accumulates points** across frames for persistence
- **Ages points** to create fade-out effects
- **Filters by SNR** to remove low-quality detections
- **Associates tracks** when tracking is enabled

## Configuration

```python
from ambient.processing.point_cloud import PointCloudConfig, PointCloudAccumulator

config = PointCloudConfig(
    persistence_frames=10,   # Frames to retain points
    max_points=1000,         # Maximum stored points
    age_fade=True,           # Enable age-based fading
    min_snr_db=5.0,          # SNR threshold for inclusion
    merge_distance=0.1,      # Merge points within 10cm
)

accumulator = PointCloudAccumulator(config)
```

## Usage

### Basic Accumulation

```python
from ambient.processing.point_cloud import PointCloudAccumulator

accumulator = PointCloudAccumulator()

# Add points from each frame
for frame in frame_stream:
    accumulator.add_frame(frame)

    # Get all accumulated points
    points = accumulator.get_points()

    # Render with age-based colors
    for point in points:
        alpha = 1.0 - (point.age / config.persistence_frames)
        render_point(point.x, point.y, point.z, alpha)
```

### With Track Association

```python
# Points include track IDs when tracking is enabled
for point in accumulator.get_points():
    if point.track_id >= 0:
        color = get_track_color(point.track_id)
    else:
        color = DEFAULT_COLOR
```

## Point3D Class

```python
@dataclass
class Point3D:
    x: float              # X position (meters)
    y: float              # Y position (meters)
    z: float              # Z position (meters)
    velocity: float       # Radial velocity (m/s)
    snr: float            # Signal-to-noise ratio (dB)
    age: int              # Frames since detection
    track_id: int         # Associated track (-1 if none)
    frame_number: int     # Frame when detected

    # Computed properties
    @property
    def range(self) -> float:
        """Distance from radar."""

    @property
    def azimuth(self) -> float:
        """Azimuth angle in radians."""

    @property
    def elevation(self) -> float:
        """Elevation angle in radians."""
```

## Color Mapping Utilities

```python
from ambient.processing.point_cloud import (
    velocity_to_color,
    snr_to_color,
    height_to_color,
)

# Map velocity to color (blue=approaching, red=receding)
r, g, b = velocity_to_color(point.velocity, max_velocity=2.0)

# Map SNR to color (dark=low, bright=high)
r, g, b = snr_to_color(point.snr, min_snr=5.0, max_snr=25.0)

# Map height to color (rainbow gradient)
r, g, b = height_to_color(point.z, min_height=0.0, max_height=2.0)
```

## Integration with Dashboard

The `PointCloud3D.tsx` component uses Three.js for 3D visualization:

```typescript
// Dashboard receives points via WebSocket
const pointCloud = useAppStore(s => s.pointCloud)

// Points include age for fade effect
for (const point of pointCloud) {
    const opacity = 1.0 - point.age / maxAge
    // Render point at (x, y, z) with opacity
}
```

## Performance Notes

- **Max points**: Keep below 2000 for smooth rendering
- **Persistence**: 10-20 frames provides good visual continuity
- **Merge distance**: 0.05-0.15m depending on resolution
- **Age fade**: Disable for static scene capture
