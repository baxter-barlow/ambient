#!/usr/bin/env python3
"""Test both ports at various baud rates to find data stream."""

import sys
import time
from pathlib import Path

import serial

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ambient.sensor.ports import find_ti_radar_ports, get_default_ports

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'

def send_config(port, baud=115200):
    """Send config to start the sensor."""
    ser = serial.Serial(port, baud, timeout=1)
    time.sleep(0.1)
    ser.reset_input_buffer()

    config_lines = [
        "sensorStop", "flushCfg", "dfeDataOutputMode 1", "channelCfg 15 7 0",
        "adcCfg 2 1", "adcbufCfg -1 0 1 1 1",
        "profileCfg 0 60 7 5 60 0 0 60 1 256 10000 0 0 30",
        "chirpCfg 0 0 0 0 0 0 0 1", "chirpCfg 1 1 0 0 0 0 0 2", "chirpCfg 2 2 0 0 0 0 0 4",
        "frameCfg 0 2 64 0 100 1 0", "lowPower 0 0", "guiMonitor -1 1 1 0 0 0 1",
        "cfarCfg -1 0 2 8 4 3 0 15 1", "cfarCfg -1 1 0 4 2 3 1 15 1",
        "multiObjBeamForming -1 1 0.5", "clutterRemoval -1 0",
        "calibDcRangeSig -1 0 -5 8 256", "extendedMaxVelocity -1 0",
        "compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0",
        "measureRangeBiasAndRxChanPhase 0 1.5 0.2", "nearFieldCfg -1 0 0 0",
        "analogMonitor 0 0", "aoaFovCfg -1 -90 90 -90 90", "sensorStart"
    ]

    for line in config_lines:
        ser.write(f"{line}\n".encode())
        time.sleep(0.03)
        ser.read(ser.in_waiting)  # Discard response

    ser.close()
    print(f"Config sent to {port}")

def test_read(port, baud, duration=3):
    """Try reading from a port at given baud rate."""
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
        time.sleep(0.1)
        ser.reset_input_buffer()

        total = 0
        magic = 0
        buf = bytearray()
        start = time.time()

        while time.time() - start < duration:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                total += len(data)
                buf.extend(data)
                while MAGIC_WORD in buf:
                    magic += 1
                    idx = buf.find(MAGIC_WORD)
                    buf = buf[idx + 8:]
            time.sleep(0.01)

        ser.close()
        return total, magic
    except Exception as e:
        return -1, str(e)

print("=== Testing Port Configurations ===\n")

# Auto-detect ports
ports = find_ti_radar_ports()
if ports:
    cli_port = ports["cli"]
    data_port = ports["data"]
    print(f"Detected ports: CLI={cli_port}, Data={data_port}")
else:
    cli_port, data_port = get_default_ports()
    print(f"Could not auto-detect, using defaults: CLI={cli_port}, Data={data_port}")

# First send config via Enhanced port (known to work for CLI)
send_config(cli_port)
time.sleep(0.5)

# Test both ports at various baud rates
test_configs = [
    (cli_port, 921600),    # CLI port at high baud
    (cli_port, 460800),    # CLI port at medium baud
    (cli_port, 115200),    # CLI port at CLI baud (data might come here too)
    (data_port, 921600),   # Data port at high baud
    (data_port, 460800),   # Data port at medium baud
    (data_port, 115200),   # Data port at low baud
]

print("Reading from ports for 3 seconds each...\n")
for port, baud in test_configs:
    bytes_recv, magic = test_read(port, baud)
    if bytes_recv == -1:
        print(f"{port} @ {baud:>7}: ERROR - {magic}")
    elif bytes_recv > 0:
        print(f"{port} @ {baud:>7}: {bytes_recv:>6} bytes, {magic} frames  {'<-- DATA FOUND!' if magic > 0 else ''}")
    else:
        print(f"{port} @ {baud:>7}: no data")

print("\n=== Also checking if data comes on same port as CLI ===")
# Maybe data comes out on the CLI port after sensorStart
ser = serial.Serial(cli_port, 115200, timeout=0.5)
time.sleep(0.1)
ser.reset_input_buffer()

# Re-send sensorStart
ser.write(b"sensorStart\n")
time.sleep(0.1)

total = 0
start = time.time()
while time.time() - start < 3:
    if ser.in_waiting:
        data = ser.read(ser.in_waiting)
        total += len(data)
        if MAGIC_WORD in data:
            print("MAGIC WORD found in CLI port response!")
    time.sleep(0.05)

print(f"CLI port after sensorStart: {total} bytes")
ser.close()
