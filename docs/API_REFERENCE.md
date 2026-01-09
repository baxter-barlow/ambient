# Ambient API Reference

Complete API reference for the Ambient mmWave radar SDK.

## CLI Commands

### Main Commands

```bash
ambient --help              # Show all commands
ambient --version           # Show version
```

### `ambient info`

Query sensor firmware information.

```bash
ambient info [--cli-port PORT] [--data-port PORT]
```

Options:
- `--cli-port`: CLI serial port (default: /dev/ttyUSB0)
- `--data-port`: Data serial port (default: /dev/ttyUSB1)

### `ambient detect`

Detect and identify connected radar firmware type.

```bash
ambient detect [--cli-port PORT] [--data-port PORT]
```

Returns:
- Firmware type (vital_signs, oob_demo, or unknown)
- Version string if detected
- Recommended configuration

### `ambient status`

Quick device status check.

```bash
ambient status [--cli-port PORT] [--data-port PORT]
```

Example output (device connected):
```
Connected - vital_signs (chirp mode)
  Version: 3.5.0.4
  Ports: /dev/ttyUSB0, /dev/ttyUSB1
```

Example output (device disconnected):
```
Disconnected - ports not found
  CLI port missing: /dev/ttyUSB0
```

### `ambient capture`

Capture radar data and vital signs to file.

```bash
ambient capture [OPTIONS]
```

Options:
- `--cli-port`: CLI serial port
- `--data-port`: Data serial port
- `--config`: Path to .cfg file
- `-o, --output`: Output file (.h5 or .parquet)
- `-d, --duration`: Recording duration in seconds (0=unlimited)

Example:
```bash
ambient capture --config configs/vital_signs.cfg -o data/session.h5 -d 60
```

### `ambient monitor`

Live monitoring with matplotlib visualization.

```bash
ambient monitor [--cli-port PORT] [--data-port PORT] [--config FILE]
```

### `ambient reset`

Send soft reset commands to sensor (sensorStop + flushCfg).

```bash
ambient reset [--cli-port PORT]
```

### Configuration Management

#### `ambient config list`

List available configuration files.

```bash
ambient config list
```

#### `ambient config show <name>`

Display configuration file contents.

```bash
ambient config show vital_signs
```

#### `ambient config validate <name>`

Validate configuration and show key parameters.

```bash
ambient config validate vital_signs
```

### Profile Management

#### `ambient profile list`

List saved profiles.

```bash
ambient profile list
```

#### `ambient profile save <name>`

Save a new profile.

```bash
ambient profile save my_profile --config vital_signs -d "My test profile"
```

Options:
- `--config`: Config file name (required)
- `-d, --description`: Profile description

#### `ambient profile apply <name>`

Apply saved profile to sensor.

```bash
ambient profile apply my_profile [--cli-port PORT] [--data-port PORT]
```

#### `ambient profile delete <name>`

Delete a saved profile.

```bash
ambient profile delete my_profile
```

---

## Python API

### RadarSensor

Main interface for radar communication.

```python
from ambient import RadarSensor, SensorDisconnectedError
from ambient.sensor.config import SerialConfig

# Initialize with default ports
sensor = RadarSensor()

# Or with custom config
config = SerialConfig(
    cli_port="/dev/ttyUSB0",
    data_port="/dev/ttyUSB1",
    cli_baud=115200,
    data_baud=921600,
)
sensor = RadarSensor(config)

# Enable auto-reconnection
sensor = RadarSensor(config, auto_reconnect=True)
```

#### Methods

##### `connect()`
Open serial connections.

##### `disconnect()`
Close serial connections.

##### `configure(config)`
Send configuration to sensor. Accepts:
- Path to .cfg file (str or Path)
- ChirpConfig object
- List of command strings

```python
sensor.configure("configs/vital_signs.cfg")
# or
sensor.configure(create_vital_signs_config())
```

##### `start()`
Send sensorStart command.

##### `stop()`
Send sensorStop command.

##### `stream(max_frames=None, duration=None) -> Iterator[RadarFrame]`
Generator yielding frames.

```python
for frame in sensor.stream(duration=60):
    print(f"Frame {frame.header.frame_number}")
```

##### `read_frame(timeout=1.0) -> RadarFrame | None`
Read single frame with timeout.

##### `detect_firmware() -> dict`
Detect firmware type and version.

```python
info = sensor.detect_firmware()
# {'type': 'vital_signs', 'version': '3.5.0.4', 'raw': '...'}
```

##### `get_version() -> str`
Query firmware version string.

##### `reconnect(reconfigure=True) -> bool`
Attempt to reconnect after disconnection.

```python
if not sensor.is_connected:
    if sensor.reconnect():
        print("Reconnected successfully")
```

##### `set_callbacks(on_disconnect, on_reconnect)`
Set callbacks for connection events.

```python
sensor.set_callbacks(
    on_disconnect=lambda: print("Lost connection!"),
    on_reconnect=lambda: print("Reconnected!"),
)
```

#### Context Manager

```python
with RadarSensor() as sensor:
    sensor.configure("configs/vital_signs.cfg")
    for frame in sensor.stream(duration=10):
        process(frame)
```

---

### RadarFrame

Parsed radar frame with all TLV data.

```python
from ambient.sensor.frame import RadarFrame
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `header` | `FrameHeader` | Frame metadata |
| `detected_points` | `list[DetectedPoint]` | Point cloud |
| `range_profile` | `NDArray[float32]` | Range magnitude (dB) |
| `range_doppler_heatmap` | `NDArray[float32]` | Range-Doppler map |
| `vital_signs` | `VitalSignsTLV` | TI vital signs TLV |
| `chirp_phase` | `ChirpPhaseOutput` | Chirp phase output |
| `chirp_complex_fft` | `ChirpComplexRangeFFT` | Raw I/Q data |
| `chirp_target_iq` | `ChirpTargetIQ` | Target bin I/Q |
| `chirp_presence` | `ChirpPresence` | Presence detection |
| `chirp_motion` | `ChirpMotionStatus` | Motion status |
| `chirp_target_info` | `ChirpTargetInfo` | Target metadata |
| `timestamp` | `float` | Unix timestamp |
| `raw_data` | `bytes` | Original frame bytes |

---

### VitalSigns

Result from vital signs extraction.

```python
from ambient.vitals import VitalsExtractor, VitalSigns
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `heart_rate_bpm` | `float \| None` | Heart rate in BPM |
| `heart_rate_confidence` | `float` | 0.0 to 1.0 |
| `heart_rate_waveform` | `NDArray` | Filtered HR signal |
| `respiratory_rate_bpm` | `float \| None` | Respiratory rate in BPM |
| `respiratory_rate_confidence` | `float` | 0.0 to 1.0 |
| `respiratory_waveform` | `NDArray` | Filtered RR signal |
| `signal_quality` | `float` | Overall quality (0-1) |
| `motion_detected` | `bool` | Motion flag |
| `source` | `str` | "firmware", "estimated", or "chirp" |
| `hr_snr_db` | `float` | Heart rate SNR in dB |
| `rr_snr_db` | `float` | Respiratory rate SNR in dB |
| `phase_stability` | `float` | Phase variance (lower=better) |

#### Methods

##### `is_valid(min_confidence=0.5) -> bool`
Check if both HR and RR are within valid ranges with sufficient confidence.

##### `quality_summary() -> str`
Human-readable quality assessment ("excellent", "good", "fair", "poor").

---

### VitalsExtractor

Extract vital signs from processed frames.

```python
from ambient.vitals import VitalsExtractor, VitalsConfig

# Default configuration
extractor = VitalsExtractor()

# Custom configuration
config = VitalsConfig(
    sample_rate_hz=20.0,
    window_seconds=10.0,
    hr_freq_min_hz=0.8,
    hr_freq_max_hz=3.0,
    rr_freq_min_hz=0.1,
    rr_freq_max_hz=0.6,
    motion_threshold=0.5,
)
extractor = VitalsExtractor(config)
```

#### Methods

##### `process_frame(frame) -> VitalSigns`
Process a ProcessedFrame and extract vitals.

##### `process(phase_data, timestamp) -> VitalSigns`
Process raw phase data.

##### `reset()`
Clear buffers and reset state.

##### Properties

- `buffer_fullness` (float): Fraction of buffer filled (0.0-1.0)

---

### ChirpVitalsProcessor

Specialized processor for Chirp firmware PHASE_OUTPUT TLV.

```python
from ambient.vitals import ChirpVitalsProcessor

processor = ChirpVitalsProcessor()

for frame in sensor.stream():
    if frame.chirp_phase:
        vitals = processor.process_chirp_phase(frame.chirp_phase)
```

#### Methods

##### `process_chirp_phase(phase_output, timestamp=None) -> VitalSigns`
Process ChirpPhaseOutput TLV.

##### `process_frame(frame) -> VitalSigns | None`
Process RadarFrame with chirp TLVs.

##### `reset()`
Clear buffers.

##### Properties

- `buffer_fullness` (float): Buffer fill level
- `is_ready` (bool): True when enough samples collected

---

### ProcessingPipeline

Signal processing for radar data.

```python
from ambient.processing import ProcessingPipeline

pipeline = ProcessingPipeline()
processed = pipeline.process(frame)
```

#### ProcessedFrame Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `range_fft` | `NDArray` | Range FFT output |
| `doppler_fft` | `NDArray` | Doppler FFT output |
| `phase_data` | `float \| NDArray` | Extracted phase |
| `timestamp` | `float` | Frame timestamp |

---

### Storage Writers

#### HDF5Writer

```python
from ambient.storage import HDF5Writer

writer = HDF5Writer("data/session.h5")
writer.write_frame(frame)
writer.write_vitals(vitals)
writer.close()
```

#### ParquetWriter

```python
from ambient.storage import ParquetWriter

writer = ParquetWriter("data/session.parquet")
writer.write_frame(frame)
writer.close()
```

---

## Configuration Classes

### ChirpConfig

```python
from ambient.sensor.config import ChirpConfig, ProfileConfig, FrameConfig

# Use defaults (matches vital_signs_chirp.cfg)
config = ChirpConfig()

# Or customize parameters
config = ChirpConfig(
    profile=ProfileConfig(
        start_freq_ghz=60.0,
        freq_slope_mhz_us=100.0,
        ramp_end_time_us=39.0,
        adc_samples=256,
        sample_rate_ksps=7200,
        rx_gain_db=30,
    ),
    frame=FrameConfig(
        num_loops=32,
        frame_period_ms=50.0,
    ),
)

commands = config.to_commands()
```

#### Properties

- `range_resolution`: Range resolution in meters
- `max_range`: Maximum detectable range
- `velocity_resolution`: Velocity resolution

### create_vital_signs_config()

Factory function for optimized vital signs configuration.

```python
from ambient.sensor.config import create_vital_signs_config

config = create_vital_signs_config()
sensor.configure(config)
```

---

## Error Handling

```python
try:
    sensor.connect()
except RuntimeError as e:
    # Connection failed - check ports, permissions
    print(f"Connection error: {e}")

try:
    sensor.configure("configs/invalid.cfg")
except FileNotFoundError:
    # Config file doesn't exist
    pass
except ValueError as e:
    # Invalid configuration
    pass
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AMBIENT_CLI_PORT` | /dev/ttyUSB0 | Default CLI port |
| `AMBIENT_DATA_PORT` | /dev/ttyUSB1 | Default data port |
| `AMBIENT_DATA_DIR` | data/ | Recording storage directory |
| `AMBIENT_PERF_ENABLED` | false | Enable performance profiling |
| `AMBIENT_PERF_LOG_INTERVAL` | 100 | Log stats every N frames |
| `AMBIENT_STREAM_MAX_QUEUE` | 100 | WebSocket broadcast queue size |
| `AMBIENT_STREAM_DROP_POLICY` | oldest | Queue drop policy (oldest/newest/none) |
| `AMBIENT_STREAM_MAX_HEATMAP` | 64 | Max range_doppler matrix size |
| `AMBIENT_STREAM_MAX_WAVEFORM` | 200 | Max waveform samples |
| `AMBIENT_STREAM_VITALS_HZ` | 1.0 | Vitals broadcast rate |

---

## REST API Endpoints

### Device Endpoints

#### `GET /api/device/status`
Get current device status.

Response:
```json
{
  "state": "streaming",
  "cli_port": "/dev/ttyUSB0",
  "data_port": "/dev/ttyUSB1",
  "frame_rate": 20.1,
  "frame_count": 1234,
  "dropped_frames": 0,
  "buffer_usage": 0.12,
  "error": null,
  "config_name": "default"
}
```

#### `GET /api/device/metrics`
Get performance profiling metrics.

Response:
```json
{
  "enabled": true,
  "frame_count": 5000,
  "sampled_count": 5000,
  "dropped_frames": 0,
  "sample_rate": 1.0,
  "timing": {
    "total": {
      "count": 5000,
      "mean_ms": 2.5,
      "min_ms": 1.2,
      "max_ms": 15.3,
      "p50_ms": 2.3,
      "p95_ms": 4.1,
      "p99_ms": 8.2,
      "last_ms": 2.4
    },
    "pipeline": {...},
    "vitals": {...},
    "broadcast": {...}
  },
  "queues": {
    "sensor": {
      "current_depth": 5,
      "max_depth": 20,
      "avg_depth": 3.2,
      "total_enqueued": 5000,
      "total_dropped": 0,
      "drop_rate_percent": 0.0
    }
  },
  "websocket": {
    "total": {
      "messages_sent": 10000,
      "messages_dropped": 0,
      "bytes_sent": 50000000,
      "send_errors": 0,
      "avg_send_time_ms": 1.2,
      "queue_depth": 3
    },
    "by_channel": {...},
    "connections": {"sensor": 2, "logs": 1}
  }
}
```

#### `POST /api/device/metrics/reset`
Reset all performance metrics.

#### `POST /api/device/connect`
Connect to radar sensor.

Request:
```json
{
  "cli_port": "/dev/ttyUSB0",
  "data_port": "/dev/ttyUSB1",
  "config": "default"
}
```

#### `POST /api/device/disconnect`
Disconnect from radar sensor.

#### `POST /api/device/stop`
Emergency stop - immediately halt all acquisition.

#### `POST /api/device/verify-ports`
Verify serial ports before connecting.

Request:
```json
{
  "cli_port": "/dev/ttyUSB0",
  "data_port": "/dev/ttyUSB1"
}
```

Response:
```json
{
  "cli_port": {"path": "/dev/ttyUSB0", "status": "ok", "details": "TI mmWave detected"},
  "data_port": {"path": "/dev/ttyUSB1", "status": "ok", "details": "Port accessible at 921600 baud"},
  "overall": "pass"
}
```

### Config Endpoints

#### `GET /api/config/validate`
Validate current application configuration.

Response:
```json
{
  "valid": true,
  "errors": [],
  "config": {
    "sensor": {...},
    "api": {...},
    "streaming": {...},
    "performance": {...},
    "chirp": {...}
  }
}
```

#### `GET /api/config/profiles`
List all saved configuration profiles.

#### `GET /api/config/profiles/{name}`
Get a specific configuration profile.

#### `POST /api/config/profiles`
Create a new configuration profile.

#### `DELETE /api/config/profiles/{name}`
Delete a configuration profile.

#### `POST /api/config/flash`
Flash configuration to device.

### Recording Endpoints

#### `GET /api/recordings`
List all recordings.

#### `GET /api/recordings/status`
Get current recording status.

#### `POST /api/recordings/start`
Start a new recording.

Request:
```json
{
  "name": "session_001",
  "format": "h5"
}
```

#### `POST /api/recordings/stop`
Stop current recording.

#### `DELETE /api/recordings/{id}`
Delete a recording.

---

## Scripts Reference

### Load Testing Scripts

#### `scripts/simulate_frames.py`
Generate synthetic radar frames for load testing without hardware.

```bash
# Standard test
python scripts/simulate_frames.py

# Using load profile
python scripts/simulate_frames.py --profile stress

# Custom settings
python scripts/simulate_frames.py --fps 30 --duration 120 --no-ws
```

Options:
- `--profile`: Load profile (standard, stress, sustained)
- `--fps`: Frames per second
- `--duration`: Test duration in seconds
- `--no-ws`: Disable WebSocket broadcast
- `--include-doppler`: Include range_doppler matrix
- `--output`: Save stats to file

#### `scripts/replay_recording.py`
Replay recorded HDF5/Parquet files through the pipeline.

```bash
# Replay at original speed
python scripts/replay_recording.py data/session.h5

# Fast replay (2x speed)
python scripts/replay_recording.py data/session.h5 --speed 2.0

# Validate only (no replay)
python scripts/replay_recording.py data/session.h5 --validate
```

Options:
- `--speed`: Playback speed multiplier (default: 1.0)
- `--broadcast`: Broadcast to WebSocket
- `--validate`: Validate file without replaying
- `--loop`: Loop replay indefinitely

#### `scripts/validate_recording.py`
Validate recording files for schema and data integrity.

```bash
# Validate single file
python scripts/validate_recording.py data/session.h5

# Verbose output
python scripts/validate_recording.py data/session.h5 --verbose

# Batch validation with summary
python scripts/validate_recording.py data/*.h5 --summary

# JSON output
python scripts/validate_recording.py data/session.h5 --json
```

Validates:
- Schema compliance (HDF5/Parquet structure)
- Timestamp monotonicity
- Data ranges (heart rate, respiratory rate, etc.)
- Frame sequence gaps
- Metadata presence
