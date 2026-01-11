#!/usr/bin/env python3
"""Test UART data output configuration."""

import sys
import time
from pathlib import Path

import serial

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ambient.sensor.ports import find_ti_radar_ports, get_default_ports

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'

def send_and_print(ser, cmd):
    """Send command and print response."""
    ser.write(f"{cmd}\n".encode())
    time.sleep(0.1)
    resp = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    status = "ERROR" if "Error" in resp or "error" in resp else "OK"
    print(f"[{status}] {cmd}")
    if "Error" in resp or "error" in resp:
        print(f"       {resp.strip()}")
    return resp

def test_data_output(data_port, baud=921600, duration=3):
    """Test for data output."""
    ser = serial.Serial(data_port, baud, timeout=0.5)
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

# Auto-detect ports
ports = find_ti_radar_ports()
if ports:
    cli_port = ports["cli"]
    data_port = ports["data"]
    print(f"Detected ports: CLI={cli_port}, Data={data_port}")
else:
    cli_port, data_port = get_default_ports()
    print(f"Could not auto-detect, using defaults: CLI={cli_port}, Data={data_port}")

print("=== Querying Radar Firmware ===\n")

ser = serial.Serial(cli_port, 115200, timeout=1)
time.sleep(0.1)
ser.reset_input_buffer()

# Get version info
send_and_print(ser, "version")

# Try help to see available commands
ser.write(b"help\n")
time.sleep(0.3)
help_resp = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
print(f"\nAvailable commands:\n{help_resp[:1500]}")

print("\n=== Testing Configuration with LVDS Disabled ===\n")

# Full config with LVDS disabled
commands = [
    "sensorStop",
    "flushCfg",
    "dfeDataOutputMode 1",
    "channelCfg 15 7 0",
    "adcCfg 2 1",
    "adcbufCfg -1 0 1 1 1",
    "profileCfg 0 60 7 5 60 0 0 60 1 256 10000 0 0 30",
    "chirpCfg 0 0 0 0 0 0 0 1",
    "chirpCfg 1 1 0 0 0 0 0 2",
    "chirpCfg 2 2 0 0 0 0 0 4",
    "frameCfg 0 2 64 0 100 1 0",
    "lowPower 0 0",
    "guiMonitor -1 1 1 0 0 0 1",
    "cfarCfg -1 0 2 8 4 3 0 15 1",
    "cfarCfg -1 1 0 4 2 3 1 15 1",
    "multiObjBeamForming -1 1 0.5",
    "clutterRemoval -1 0",
    "calibDcRangeSig -1 0 -5 8 256",
    "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0",  # Explicitly disable LVDS
    "compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2",
    "analogMonitor 0 0",
    "aoaFovCfg -1 -90 90 -90 90",
    "sensorStart",
]

for cmd in commands:
    send_and_print(ser, cmd)
    time.sleep(0.03)

ser.close()

print("\n=== Testing Data Output ===\n")

# Test CLI port at 921600
print(f"Testing {cli_port} @ 921600...")
total, magic = test_data_output(cli_port, 921600, 3)
print(f"  {total} bytes, {magic} frames")

# Also try reading from CLI port at 115200 (some firmware sends data there)
print(f"Testing {cli_port} @ 115200...")
total, magic = test_data_output(cli_port, 115200, 3)
print(f"  {total} bytes, {magic} frames")

# Try the data port too
print(f"Testing {data_port} @ 921600...")
try:
    total, magic = test_data_output(data_port, 921600, 3)
    print(f"  {total} bytes, {magic} frames")
except Exception as e:
    print(f"  Error: {e}")

print(f"Testing {data_port} @ 460800...")
try:
    total, magic = test_data_output(data_port, 460800, 3)
    print(f"  {total} bytes, {magic} frames")
except Exception as e:
    print(f"  Error: {e}")
