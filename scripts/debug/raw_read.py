#!/usr/bin/env python3
"""Raw continuous read from both ports simultaneously."""

import serial
import time
import threading

MAGIC = b'\x02\x01\x04\x03\x06\x05\x08\x07'

def read_port(port, baud, name, duration=10):
    """Read from a port continuously."""
    try:
        ser = serial.Serial(port, baud, timeout=0.1)
        time.sleep(0.1)
        ser.reset_input_buffer()

        total = 0
        magic_count = 0
        start = time.time()
        all_data = bytearray()

        while time.time() - start < duration:
            data = ser.read(1024)
            if data:
                total += len(data)
                all_data.extend(data)
                if MAGIC in data:
                    magic_count += 1

        ser.close()

        print(f"\n{name} ({port} @ {baud}):")
        print(f"  Total bytes: {total}")
        print(f"  Magic words: {magic_count}")
        if total > 0:
            print(f"  First 100 bytes (hex): {all_data[:100].hex()}")
            # Check for any pattern
            if all_data[:20]:
                print(f"  First 20 bytes (raw): {all_data[:20]}")

    except Exception as e:
        print(f"\n{name} ({port} @ {baud}): ERROR - {e}")

# First configure the device
print("=== Configuring radar ===")
cli = serial.Serial("/dev/ttyUSB0", 115200, timeout=1)
time.sleep(0.2)
cli.reset_input_buffer()
cli.reset_output_buffer()

# Read any pending data first
pending = cli.read(cli.in_waiting)
if pending:
    print(f"Pending data on CLI: {len(pending)} bytes")

# Send config with explicit reads
config = """sensorStop
flushCfg
dfeDataOutputMode 1
channelCfg 15 7 0
adcCfg 2 1
adcbufCfg -1 0 1 1 1
profileCfg 0 60 7 5 60 0 0 60 1 256 10000 0 0 30
chirpCfg 0 0 0 0 0 0 0 1
chirpCfg 1 1 0 0 0 0 0 2
chirpCfg 2 2 0 0 0 0 0 4
frameCfg 0 2 64 0 100 1 0
lowPower 0 0
guiMonitor -1 1 1 0 0 0 1
cfarCfg -1 0 2 8 4 3 0 15 1
cfarCfg -1 1 0 4 2 3 1 15 1
multiObjBeamForming -1 1 0.5
clutterRemoval -1 0
calibDcRangeSig -1 0 -5 8 256
extendedMaxVelocity -1 0
lvdsStreamCfg -1 0 0 0
compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0
measureRangeBiasAndRxChanPhase 0 1.5 0.2
analogMonitor 0 0
aoaFovCfg -1 -90 90 -90 90
sensorStart"""

print("Sending configuration...")
for line in config.strip().split('\n'):
    line = line.strip()
    if not line:
        continue
    cli.write(f"{line}\n".encode())
    time.sleep(0.05)
    resp = cli.read(cli.in_waiting)
    # Only print errors
    if b'Error' in resp or b'error' in resp:
        print(f"  ERROR: {line} -> {resp.decode(errors='ignore').strip()}")

print("Configuration sent, sensor should be running")
cli.close()

time.sleep(0.5)  # Let sensor start

print("\n=== Reading from all ports for 10 seconds ===")

# Test USB0 (Enhanced - supports high baud) and USB1 (Standard)
# Need to re-start sensor between tests since opening CLI port stops it
def test_with_restart(data_port, data_baud, name):
    # Restart sensor
    cli = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.5)
    cli.write(b"sensorStart\n")
    time.sleep(0.3)
    cli.close()

    time.sleep(0.2)
    read_port(data_port, data_baud, name, duration=5)

# Primary test: USB0 (Enhanced) at high baud for data
read_port("/dev/ttyUSB0", 921600, "USB0 @ 921600 (Enhanced, high-speed)", duration=5)

# Restart and test USB1
test_with_restart("/dev/ttyUSB1", 460800, "USB1 @ 460800 (Standard, max baud)")
test_with_restart("/dev/ttyUSB1", 115200, "USB1 @ 115200 (Standard, low baud)")

print("\n=== Done ===")
