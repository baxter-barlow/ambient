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
from ambient import RadarSensor
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

config = ChirpConfig(
    profile=ProfileConfig(
        start_freq_ghz=60.0,
        freq_slope_mhz_us=66.67,
        adc_samples=256,
        sample_rate_ksps=10000,
        rx_gain_db=30,
    ),
    frame=FrameConfig(
        num_loops=64,
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
