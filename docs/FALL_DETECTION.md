# Fall Detection Module

The fall detection module (`src/ambient/processing/fall_detection.py`) implements radar-based fall detection using tracked object trajectories.

## Algorithm Overview

The algorithm detects falls by analyzing:
- **Vertical velocity changes** - Sudden downward motion
- **Height drops** - Position falling below thresholds
- **Motion cessation** - Stillness after impact

### State Machine

```
MONITORING -> FALL_DETECTED -> IMPACT_DETECTED -> LYING_DOWN -> RECOVERED
     ^                                                              |
     |______________________________________________________________|
```

| State | Description | Transition Trigger |
|-------|-------------|-------------------|
| `MONITORING` | Normal tracking | Height drop + velocity threshold |
| `FALL_DETECTED` | Fall in progress | Impact detected (velocity change) |
| `IMPACT_DETECTED` | Just hit ground | Stillness timeout |
| `LYING_DOWN` | Person on ground | Height recovery |
| `RECOVERED` | Standing up | Returns to MONITORING |

## Configuration

```python
from ambient.processing.fall_detection import FallDetectionConfig, FallDetector

config = FallDetectionConfig(
    # Height thresholds (meters)
    standing_height_min=1.2,      # Minimum standing height
    fall_height_threshold=0.6,    # Fall confirmed below this
    lying_height_max=0.4,         # Lying down threshold

    # Velocity thresholds (m/s)
    fall_velocity_threshold=-1.5, # Downward velocity for fall
    impact_velocity_change=2.0,   # Sudden stop at impact

    # Time thresholds (seconds)
    fall_duration_max=2.0,        # Max fall duration
    lying_timeout=5.0,            # Time before alert
    recovery_timeout=30.0,        # Wait for recovery

    # Detection parameters
    min_confidence=0.7,           # Minimum detection confidence
    min_track_history=5,          # Frames before detection
)

detector = FallDetector(config)
```

## Usage

```python
from ambient.processing.fall_detection import FallDetector

detector = FallDetector()

# Process tracked objects from radar frame
result = detector.process_tracked_objects(frame.tracked_objects, frame.timestamp)

# Or process full frame
result = detector.process_frame(frame)

# Check for fall events
if result.fall_detected:
    for event in result.events:
        print(f"Fall detected: track {event.track_id}, confidence {event.confidence}")
```

## Output

```python
@dataclass
class FallDetectionResult:
    fall_detected: bool           # Any fall detected this frame
    events: list[FallEvent]       # List of fall events
    active_tracks: int            # Number of tracked objects
    timestamp: float              # Frame timestamp
```

```python
@dataclass
class FallEvent:
    track_id: int                 # Which track fell
    state: FallState              # Current state
    confidence: float             # Detection confidence (0-1)
    position: tuple[float, float, float]  # Last known position
    time_in_state: float          # Seconds in current state
```

## Integration

The fall detector integrates with the processing pipeline:

```python
from ambient.processing import FallDetector
from ambient.sensor import RadarSensor

sensor = RadarSensor()
detector = FallDetector()

sensor.connect()
sensor.configure("tracking_config.cfg")
sensor.start()

while True:
    frame = sensor.read_frame()
    if frame and frame.tracked_objects:
        result = detector.process_frame(frame)
        if result.fall_detected:
            trigger_alert(result.events)
```

## Requirements

- Radar must be configured for **3D tracking mode**
- `tracked_objects` TLV must be enabled in radar config
- Minimum frame rate: 10 Hz recommended
