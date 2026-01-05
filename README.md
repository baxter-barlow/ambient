# ambient

Contact-free sleep biometrics using TI IWR6843AOPEVM mmWave radar.

Extracts heart rate and respiratory rate from radar phase variations without any wearable sensors.

## Requirements

- TI IWR6843AOPEVM evaluation module
- Ubuntu Linux (tested on 22.04)
- Python 3.10+

## Installation

```bash
pip install -e .
```

With dev tools:

```bash
pip install -e ".[dev]"
```

## Hardware Setup

1. Connect IWR6843AOPEVM via USB
2. Verify ports: `ls /dev/ttyUSB*` (should show ttyUSB0 and ttyUSB1)
3. Add yourself to dialout group: `sudo usermod -a -G dialout $USER` and re-login

## Usage

### CLI

```bash
# sensor info
ambient info

# live monitoring with plot
ambient monitor

# record session
ambient capture -o data/session.h5 -d 3600
```

### Python

```python
from ambient import RadarSensor, ProcessingPipeline, VitalsExtractor

with RadarSensor() as sensor:
    sensor.configure("configs/vital_signs.cfg")
    pipeline = ProcessingPipeline()
    extractor = VitalsExtractor()

    for frame in sensor.stream(duration=60):
        processed = pipeline.process(frame)
        vitals = extractor.process_frame(processed)

        if vitals.is_valid():
            print(f"HR: {vitals.heart_rate_bpm:.0f}, RR: {vitals.respiratory_rate_bpm:.0f}")
```

### Load recorded data

```python
from ambient.storage import DataReader

with DataReader("data/session.h5") as reader:
    df = reader.get_vitals_dataframe()
    print(df.describe())
```

## Project Structure

```
src/ambient/
├── sensor/      # serial communication, frame parsing
├── processing/  # FFT, clutter removal
├── vitals/      # HR/RR extraction, filtering
├── storage/     # HDF5/Parquet I/O
└── viz/         # matplotlib plotting
```

## Configuration

Chirp configs in `configs/`. Default `vital_signs.cfg` is optimized for:
- 20 Hz frame rate
- 0.3-2.0m range
- Static clutter removal

## Development

```bash
make dev      # install with dev deps
make lint     # ruff + black + mypy
make test     # pytest
make format   # auto-format
```

## Serial Ports

| Port | Purpose | Baud |
|------|---------|------|
| /dev/ttyUSB0 | CLI | 115200 |
| /dev/ttyUSB1 | Data | 921600 |

## License

MIT
