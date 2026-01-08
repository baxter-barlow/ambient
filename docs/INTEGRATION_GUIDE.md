# Integration Guide

End-to-end setup guide for Ambient mmWave radar vital signs monitoring.

## Overview

Ambient provides contact-free vital signs monitoring using the TI IWR6843AOPEVM mmWave radar. The system extracts heart rate and respiratory rate from chest motion detected via radar phase variations.

```
+-------------+     Serial      +------------+     WebSocket     +-----------+
|  IWR6843    | --------------> |  Ambient   | ----------------> | Dashboard |
|  Radar      |    CLI+Data     |  Backend   |    /ws/sensor     |  (React)  |
+-------------+                 +------------+                   +-----------+
```

## Hardware Requirements

- **TI IWR6843AOPEVM** evaluation module
- **USB cable** (typically included)
- **Linux host** (Ubuntu 22.04+ recommended)
- **5V power supply** (2A minimum)

## Step 1: Hardware Setup

### 1.1 Physical Setup

1. Position radar 0.5-1.5m from the subject
2. Aim antenna at subject's chest
3. Minimize metal reflectors in field of view
4. Subject should be stationary for best results

### 1.2 Flash Firmware

For best results, use TI Vital Signs demo firmware:

1. Download [UniFlash](https://www.ti.com/tool/UNIFLASH)
2. Download [Vital Signs Lab firmware](https://dev.ti.com/tirex/explore/node?node=A__ACkOIiM4M1.c0vA9s9Y4HA__radar_toolbox__1AslXXD__LATEST)
3. Set SOP jumpers to flash mode:
   - SOP0: 00 (short)
   - SOP2: 10 (open)
4. Flash via UniFlash
5. Reset SOP jumpers for run mode:
   - SOP0: 01 (open)
   - SOP2: 00 (short)
6. Power cycle the board

See `docs/firmware_setup.md` for detailed instructions.

### 1.3 Linux Permissions

```bash
# Add user to dialout group
sudo usermod -aG dialout $USER

# Log out and back in, then verify
groups | grep dialout

# Verify ports
ls /dev/ttyUSB*
# Should show: /dev/ttyUSB0 /dev/ttyUSB1
```

## Step 2: Software Installation

### 2.1 Basic Installation

```bash
# Clone repository
git clone https://github.com/your-org/ambient.git
cd ambient

# Install Python package
pip install -e .

# Verify installation
ambient --version
```

### 2.2 Development Installation

```bash
# Install with all dependencies
pip install -e ".[dev,viz,dashboard]"

# Install pre-commit hooks
pre-commit install
```

### 2.3 Dashboard Installation

```bash
# Install dashboard dependencies
make dashboard-install

# Or manually:
pip install -e ".[dashboard]"
cd dashboard && npm install
```

## Step 3: Verify Connection

### 3.1 Detect Firmware

```bash
ambient detect
```

Expected output:
```
Detected Firmware
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Property     ┃ Value          ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ Type         │ vital_signs    │
│ Version      │ 3.5.0.4        │
│ Raw Response │ mmWave SDK...  │
└──────────────┴────────────────┘

Recommended config: vital_signs.cfg
```

### 3.2 Test Sensor Info

```bash
ambient info
```

### 3.3 List Configurations

```bash
ambient config list
```

## Step 4: Run Vital Signs Capture

### 4.1 CLI Monitoring

```bash
# Live terminal display
ambient capture --config configs/vital_signs.cfg
```

Press Ctrl+C to stop.

### 4.2 Record to File

```bash
# Record 60 seconds to HDF5
ambient capture --config configs/vital_signs.cfg -o data/test.h5 -d 60

# Record to Parquet
ambient capture --config configs/vital_signs.cfg -o data/test.parquet -d 60
```

### 4.3 Matplotlib Visualization

```bash
# Live plots (requires viz extras)
ambient monitor --config configs/vital_signs.cfg
```

## Step 5: Run Dashboard

### 5.1 Development Mode

```bash
# Start both backend and frontend
make dashboard

# Or separately:
# Terminal 1: Backend
make dashboard-backend

# Terminal 2: Frontend
make dashboard-frontend
```

Open http://localhost:5173

### 5.2 Production Mode

```bash
# Build frontend
make dashboard-build

# Run production server
uvicorn ambient.api.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

### 5.3 Docker

```bash
# Development with hot reload
make docker-dev

# Production
make docker-prod
```

## Step 6: Dashboard Usage

### 6.1 Connect to Sensor

1. Go to **Device Status** page
2. Select CLI and Data ports
3. Click **Verify Ports**
4. Click **Connect**

### 6.2 View Live Data

1. Go to **Signal Viewer** page
2. Observe:
   - Vital signs (HR, RR)
   - Range profile
   - Phase signal
   - Range-Doppler heatmap

### 6.3 Start Recording

1. Go to **Recordings** page
2. Enter session name
3. Select format (HDF5 or Parquet)
4. Click **Start Recording**

### 6.4 Tune Algorithm

1. Go to **Algorithm Tuning** page
2. Adjust filter cutoffs
3. Modify motion threshold
4. Save as preset

## Step 7: Python Integration

### 7.1 Basic Example

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
            print(f"HR: {vitals.heart_rate_bpm:.0f} BPM, "
                  f"RR: {vitals.respiratory_rate_bpm:.0f} BPM, "
                  f"Quality: {vitals.quality_summary()}")
```

### 7.2 Using Chirp Firmware

```python
from ambient import RadarSensor
from ambient.vitals import ChirpVitalsProcessor

with RadarSensor() as sensor:
    sensor.configure("configs/vital_signs.cfg")
    processor = ChirpVitalsProcessor()

    for frame in sensor.stream():
        if frame.chirp_phase:
            vitals = processor.process_frame(frame)
            if vitals and vitals.is_valid():
                print(f"HR: {vitals.heart_rate_bpm:.0f}")
```

### 7.3 Recording Data

```python
from ambient import RadarSensor
from ambient.storage import HDF5Writer

with RadarSensor() as sensor:
    sensor.configure("configs/vital_signs.cfg")

    with HDF5Writer("data/session.h5") as writer:
        for frame in sensor.stream(duration=300):
            writer.write_frame(frame)
```

### 7.4 WebSocket Client

```python
import asyncio
import websockets
import json

async def monitor():
    async with websockets.connect("ws://localhost:8000/ws/sensor") as ws:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)

            if data["type"] == "vitals":
                payload = data["payload"]
                print(f"HR: {payload['heart_rate_bpm']}")

asyncio.run(monitor())
```

## Configuration Reference

### vital_signs.cfg

Optimized for vital signs detection at 20 FPS:

| Parameter | Value | Notes |
|-----------|-------|-------|
| Frame rate | 20 Hz | 50ms period |
| Loops/frame | 32 | Balance SNR vs crash |
| Start freq | 60 GHz | 60 GHz band |
| Bandwidth | ~4 GHz | Range resolution |
| ADC samples | 256 | Range bins |

### Profile Parameters

```
profileCfg <id> <start_freq> <idle_time> <adc_start> <ramp_end> <tx_power> <tx_phase> <slope> <tx_start> <adc_samples> <sample_rate> <hpf1> <hpf2> <rx_gain>
```

### Frame Parameters

```
frameCfg <chirp_start> <chirp_end> <loops> <frames> <period_ms> <trigger> <delay>
```

## Troubleshooting

### No Serial Ports

```bash
# Check USB connection
lsusb | grep -i ti

# Check kernel driver
dmesg | tail -20

# Reload driver
sudo modprobe ftdi_sio
```

### Permission Denied

```bash
# Add to dialout group
sudo usermod -aG dialout $USER
# Then log out and back in
```

### No Data Frames

1. Check firmware is running (LED blinking)
2. Verify correct port assignment:
   - CLI: Usually lower-numbered port
   - Data: Usually higher-numbered port
3. Try swapping ports
4. Reset sensor: `ambient reset`

### Poor Vital Signs Quality

1. Reduce distance to subject (0.5-1m optimal)
2. Ensure subject is stationary
3. Minimize environmental motion
4. Adjust motion threshold in algorithm tuning
5. Use vital_signs.cfg (optimized parameters)

### Dashboard Not Connecting

1. Verify backend is running on port 8000
2. Check CORS origins in `main.py`
3. Verify WebSocket path: `/ws/sensor`
4. Check browser console for errors

### High CPU Usage

1. Reduce frame rate in config
2. Disable range-Doppler heatmap output
3. Use data decimation for visualization

## Performance Tips

### Optimal Setup

- Distance: 0.5-1.0m from subject
- Angle: Perpendicular to chest
- Environment: Minimize reflective surfaces
- Subject: Seated or lying down, stationary

### Signal Quality

- HR confidence > 0.6: Good
- RR confidence > 0.6: Good
- SNR > 10 dB: Good signal
- Phase stability < 0.3: Low motion

### Frame Rate Selection

| Use Case | Frame Rate | Config |
|----------|------------|--------|
| Real-time display | 20 Hz | vital_signs.cfg |
| Long recording | 10 Hz | Reduce power |
| High accuracy | 20 Hz | More averaging |

## Next Steps

- Review [API Reference](API_REFERENCE.md) for complete API documentation
- Review [TLV Specification](TLV_SPECIFICATION.md) for data format details
- Check [firmware_setup.md](firmware_setup.md) for detailed flashing instructions
