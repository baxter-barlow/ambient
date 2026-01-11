# TI Config Parser Module

The config parser module (`src/ambient/sensor/config_parser.py`) parses Texas Instruments mmWave radar `.cfg` configuration files and computes derived parameters.

## Overview

TI radar configs are text files with CLI commands. This parser:
- **Extracts parameters** from all standard commands
- **Computes derived values** (range resolution, max velocity, etc.)
- **Validates configurations** for common issues
- **Provides structured access** via dataclasses

## Usage

### Parsing a Config File

```python
from ambient.sensor.config_parser import parse_config_file

config = parse_config_file("configs/vital_signs.cfg")

# Access computed parameters
print(f"Range resolution: {config.range_resolution_m:.3f} m")
print(f"Max range: {config.max_range_m:.2f} m")
print(f"Frame rate: {config.frame_rate_hz:.1f} Hz")
print(f"Velocity resolution: {config.velocity_resolution_mps:.3f} m/s")
```

### Parsing Config Content

```python
from ambient.sensor.config_parser import parse_config_content

content = """
sensorStop
flushCfg
channelCfg 15 5 0
profileCfg 0 60.25 30 10 62 0 0 70 1 256 10000 0 0 48
frameCfg 0 0 16 0 100 1 0
sensorStart
"""

config = parse_config_content(content)
```

## Computed Parameters

| Parameter | Description | Formula |
|-----------|-------------|---------|
| `range_resolution_m` | Range bin size | c / (2 * bandwidth) |
| `max_range_m` | Maximum detection range | range_resolution * num_adc_samples |
| `velocity_resolution_mps` | Velocity bin size | lambda / (2 * num_chirps * frame_time) |
| `max_velocity_mps` | Maximum velocity | velocity_resolution * num_doppler_bins / 2 |
| `frame_rate_hz` | Frames per second | 1000 / frame_period_ms |
| `num_range_bins` | Range FFT size | num_adc_samples |
| `num_doppler_bins` | Doppler FFT size | num_chirps_per_frame |
| `num_virtual_antennas` | MIMO array size | num_rx * num_tx |

## Supported Commands

| Command | Dataclass | Key Parameters |
|---------|-----------|----------------|
| `channelCfg` | `ChannelConfig` | RX/TX channel enable masks |
| `profileCfg` | `ProfileConfig` | Frequency, bandwidth, timing |
| `frameCfg` | `FrameConfig` | Chirps, frame period |
| `chirpCfg` | `ChirpConfig` | Chirp timing, antenna config |
| `lowPower` | `LowPowerConfig` | ADC mode, LP mode |
| `adcCfg` | `ADCConfig` | Output format, bits |
| `adcbufCfg` | `ADCBufConfig` | Buffer configuration |
| `clutterRemoval` | `ClutterRemovalConfig` | Static clutter removal |
| `compRangeBiasAndRxChanPhase` | `CalibrationConfig` | Antenna calibration |
| `guiMonitor` | `GuiMonitorConfig` | TLV output enable flags |

## Data Structures

```python
@dataclass
class ParsedConfig:
    # Raw data
    raw_commands: list[str]

    # Individual configs
    channel: ChannelConfig
    profile: ProfileConfig
    frame: FrameConfig
    chirps: list[ChirpConfig]
    low_power: LowPowerConfig
    adc: ADCConfig
    adc_buf: ADCBufConfig
    clutter_removal: ClutterRemovalConfig
    calibration: CalibrationConfig
    gui_monitor: GuiMonitorConfig

    # Computed parameters
    @property
    def range_resolution_m(self) -> float: ...
    @property
    def max_range_m(self) -> float: ...
    @property
    def velocity_resolution_mps(self) -> float: ...
    @property
    def max_velocity_mps(self) -> float: ...
    @property
    def frame_rate_hz(self) -> float: ...

    def to_dict(self) -> dict: ...
```

## API Integration

The config parser is exposed via REST API:

```
GET  /api/config/ti-configs          # List .cfg files
GET  /api/config/ti-configs/{name}   # Get parsed parameters
POST /api/config/ti-configs/upload   # Upload new config
POST /api/config/ti-configs/{name}/apply  # Apply to device
```

## Example Output

```python
config = parse_config_file("vital_signs_chirp.cfg")
print(config.to_dict())
```

```json
{
    "range_resolution_m": 0.044,
    "max_range_m": 11.26,
    "velocity_resolution_mps": 0.039,
    "max_velocity_mps": 1.25,
    "frame_rate_hz": 20.0,
    "num_range_bins": 256,
    "num_doppler_bins": 64,
    "num_virtual_antennas": 8,
    "bandwidth_mhz": 3397.28
}
```

## Error Handling

```python
from ambient.sensor.config_parser import parse_config_file, ConfigParseError

try:
    config = parse_config_file("invalid.cfg")
except ConfigParseError as e:
    print(f"Parse error: {e}")
except FileNotFoundError:
    print("Config file not found")
```
