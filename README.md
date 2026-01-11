# ambient

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos-lightgrey.svg)
![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-purple.svg)

Contact-free vital signs monitoring using TI IWR6843AOPEVM mmWave radar. Extracts heart rate and respiratory rate from radar phase variations.

## Requirements

- TI IWR6843AOPEVM with out-of-box demo firmware
- **Linux** (Ubuntu 22.04+) or **macOS** (12+)
- Python 3.10+
- Node.js 18+ (optional, for dashboard)

## Quick Start

```bash
# Clone and install
git clone https://github.com/your-org/ambient.git
cd ambient
./scripts/setup.sh

# Verify installation
make check

# Test without hardware (mock mode)
AMBIENT_MOCK_RADAR=true ambient capture -d 10
```

## Installation

```bash
pip install -e .
```

With dashboard:
```bash
pip install -e ".[dashboard,dev]"
cd dashboard && npm install
```

## Hardware Setup

1. Flash firmware using [UniFlash](https://www.ti.com/tool/UNIFLASH)
2. Connect the radar via USB
3. Configure serial port access:
   - **Linux**: `sudo usermod -aG dialout $USER` (log out and back in)
   - **macOS**: Usually works automatically; check System Settings > Privacy & Security if issues
4. Verify device detection: `ambient detect`

## Usage

### CLI

```bash
ambient detect                        # detect sensor and ports
ambient info                          # sensor info
ambient monitor                       # live visualization
ambient capture -o data/session.h5    # record session
ambient config list                   # available configurations
```

### Python API

```python
from ambient import RadarSensor, ProcessingPipeline, VitalsExtractor

with RadarSensor() as sensor:
    sensor.configure("configs/basic.cfg")
    pipeline = ProcessingPipeline()
    extractor = VitalsExtractor()

    for frame in sensor.stream(duration=60):
        vitals = extractor.process_frame(pipeline.process(frame))
        if vitals.is_valid():
            print(f"HR: {vitals.heart_rate_bpm:.0f} RR: {vitals.respiratory_rate_bpm:.0f}")
```

### Mock Mode (No Hardware)

Test the dashboard and data pipeline without physical hardware:

```bash
AMBIENT_MOCK_RADAR=true make dashboard
AMBIENT_MOCK_RADAR=true ambient capture -d 30 -o test.h5
```

## Dashboard

```bash
make dashboard-install    # first time
make dashboard            # run backend + frontend
```

Open http://localhost:5173 (dev) or http://localhost:8000 (prod).

Docker:
```bash
make docker-dev           # development with hot reload
make docker-prod          # production
```

## Configuration

Copy `.env.example` to `.env` and customize. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| AMBIENT_CLI_PORT | (auto-detect) | CLI serial port |
| AMBIENT_DATA_PORT | (auto-detect) | Data serial port |
| AMBIENT_MOCK_RADAR | false | Enable mock mode (no hardware) |
| AMBIENT_API_PORT | 8000 | API server port |
| AMBIENT_DATA_DIR | data/ | Recording storage |
| AMBIENT_LOG_LEVEL | INFO | Logging level |

See `.env.example` for the full list of configuration options.

## Serial Ports

Ports are auto-detected. If manual configuration is needed:

| Platform | CLI Port | Data Port |
|----------|----------|-----------|
| Linux | /dev/ttyUSB0 or /dev/ttyACM0 | /dev/ttyUSB1 or /dev/ttyACM1 |
| macOS | /dev/cu.usbserial-* | /dev/cu.usbserial-* |

Both ports use: CLI @ 115200 baud, Data @ 921600 baud.

## Project Structure

```
src/ambient/
├── sensor/      # serial, frame parsing, mock sensor
├── processing/  # FFT, clutter removal
├── vitals/      # HR/RR extraction
├── storage/     # HDF5/Parquet I/O
└── api/         # FastAPI backend

dashboard/       # React frontend
configs/         # Radar configuration files
scripts/         # Setup and utility scripts
docs/            # Additional documentation
```

## Development

```bash
make dev       # install with dev deps
make check     # verify environment
make test      # run tests
make test-mock # run tests with mock sensor
make lint      # ruff + black
make format    # auto-format code
```

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues including:
- Serial port permission errors
- Device detection problems
- Dashboard connection issues
- Firmware compatibility

Quick diagnostics:
```bash
make check                    # Full environment check
ambient detect                # Test device detection
python3 -c "from ambient.sensor.ports import diagnose_ports; print(diagnose_ports())"
```

## License

MIT
