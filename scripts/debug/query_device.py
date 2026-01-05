#!/usr/bin/env python3
"""Query device info and test various data output configurations."""

import serial
import time

cli_port = "/dev/ttyUSB0"

def query(ser, cmd, wait=0.2):
    """Send command and return response."""
    ser.reset_input_buffer()
    ser.write(f"{cmd}\n".encode())
    time.sleep(wait)
    return ser.read(ser.in_waiting).decode('utf-8', errors='ignore')

print("=== Detailed Device Query ===\n")

ser = serial.Serial(cli_port, 115200, timeout=1)
time.sleep(0.1)

# Get full version info
print("Version info:")
print(query(ser, "version", 0.3))

# Query sensor status
print("\nSensor status:")
print(query(ser, "sensorStop", 0.2))

# Try to get configuration info
print("\nTrying various query commands:")
test_commands = [
    "queryDemoStatus",
    "getStats",
    "configInfo",
    "getFrameRate",
    "status",
    "sensorStatus",
]

for cmd in test_commands:
    resp = query(ser, cmd, 0.2)
    if resp.strip() and "Error" not in resp and "Unknown" not in resp:
        print(f"{cmd}: {resp.strip()[:100]}")

# Check what data output modes are available
print("\n=== Testing Data Output Modes ===\n")

# Stop sensor first
query(ser, "sensorStop")
query(ser, "flushCfg")

# Try minimal config
print("Sending minimal config...")
minimal_commands = [
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
]

for cmd in minimal_commands:
    resp = query(ser, cmd, 0.05)
    if "Error" in resp:
        print(f"  ERROR: {cmd} -> {resp.strip()}")

# Now try different guiMonitor settings
print("\nTesting guiMonitor configurations:")

gui_configs = [
    "guiMonitor -1 1 0 0 0 0 0",   # Just detected objects
    "guiMonitor -1 1 1 0 0 0 1",   # Objects + range profile + stats
    "guiMonitor 0 1 0 0 0 0 0",    # Using subframe 0 instead of -1
    "guiMonitor 0 1 1 1 1 1 1",    # Enable everything
]

for gui in gui_configs:
    resp = query(ser, gui, 0.05)
    status = "OK" if "Error" not in resp else "ERROR"
    print(f"  [{status}] {gui}")

# Check CFAR config
print("\nCFAR config:")
for cmd in ["cfarCfg -1 0 2 8 4 3 0 15 1", "cfarCfg -1 1 0 4 2 3 1 15 1"]:
    resp = query(ser, cmd, 0.05)
    status = "OK" if "Error" not in resp else "ERROR"
    print(f"  [{status}] {cmd}")

# Additional required configs
print("\nAdditional configs:")
extra = [
    "multiObjBeamForming -1 1 0.5",
    "clutterRemoval -1 0",
    "calibDcRangeSig -1 0 -5 8 256",
    "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0",
    "compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2",
    "analogMonitor 0 0",
    "aoaFovCfg -1 -90 90 -90 90",
]
for cmd in extra:
    resp = query(ser, cmd, 0.05)
    if "Error" in resp:
        print(f"  ERROR: {cmd}")

# Start sensor
print("\nStarting sensor...")
resp = query(ser, "sensorStart", 0.3)
print(f"sensorStart response: {resp.strip()[:200]}")

# Now check if CLI port itself receives data after sensor starts
print("\n=== Checking CLI port for data after sensorStart ===")
time.sleep(1)  # Wait for frames to start

for _ in range(5):
    data = ser.read(ser.in_waiting)
    if data:
        print(f"Received {len(data)} bytes on CLI port")
        print(f"First 50 bytes (hex): {data[:50].hex()}")
        if b'\x02\x01\x04\x03\x06\x05\x08\x07' in data:
            print("MAGIC WORD FOUND!")
        break
    time.sleep(0.5)
else:
    print("No data on CLI port")

ser.close()

# Double-check data ports exist and permissions
print("\n=== Checking port permissions ===")
import os
import stat

for port in ["/dev/ttyUSB0", "/dev/ttyUSB1"]:
    try:
        st = os.stat(port)
        mode = stat.filemode(st.st_mode)
        print(f"{port}: {mode}")
    except Exception as e:
        print(f"{port}: {e}")
