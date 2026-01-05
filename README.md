# ambient

Contact-free vital signs monitoring using TI IWR6843AOPEVM mmWave radar. Extracts heart rate and respiratory rate from radar phase variations.

## Requirements

- TI IWR6843AOPEVM with out-of-box demo firmware
- Ubuntu Linux 22.04+
- Python 3.10+

## Installation

```bash
pip install -e .
```

With dashboard:
```bash
pip install -e ".[dashboard,dev]"
```

## Hardware Setup

1. Flash firmware using [UniFlash](https://www.ti.com/tool/UNIFLASH)
2. Add user to dialout: `sudo usermod -aG dialout $USER` (re-login)
3. Verify ports: `ls /dev/ttyUSB*`

## Usage

CLI:
```bash
ambient info                          # sensor info
ambient monitor                       # live visualization
ambient capture -o data/session.h5    # record session
```

Python:
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

## Project Structure

```
src/ambient/
├── sensor/      # serial, frame parsing
├── processing/  # FFT, clutter removal
├── vitals/      # HR/RR extraction
├── storage/     # HDF5/Parquet I/O
└── api/         # FastAPI backend

dashboard/       # React frontend
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| AMBIENT_CLI_PORT | /dev/ttyUSB0 | CLI port |
| AMBIENT_DATA_PORT | /dev/ttyUSB1 | Data port |
| AMBIENT_DATA_DIR | data/ | Recording storage |

## Development

```bash
make dev      # install with dev deps
make test     # run tests
make lint     # ruff + black
```

## Serial Ports

| Port | Baud |
|------|------|
| CLI (ttyUSB0) | 115200 |
| Data (ttyUSB1) | 921600 |

## License

MIT
