#!/usr/bin/env python3
"""
Test if data can be routed through CLI UART.
Some TI demos support a mode where data comes back on the CLI port.
"""

import serial
import time

MAGIC = b'\x02\x01\x04\x03\x06\x05\x08\x07'
cli_port = "/dev/ttyUSB0"

def send_cmd(ser, cmd, wait=0.1):
    """Send command and return response."""
    ser.write(f"{cmd}\n".encode())
    time.sleep(wait)
    return ser.read(ser.in_waiting)

print("=== Testing Data on CLI UART ===\n")

ser = serial.Serial(cli_port, 115200, timeout=1)
time.sleep(0.2)

# Clear buffers
ser.reset_input_buffer()
ser.reset_output_buffer()

# Get version
ser.write(b"version\n")
time.sleep(0.3)
version = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
print(f"Version:\n{version}")

# Stop and configure
print("\nConfiguring radar...")
send_cmd(ser, "sensorStop", 0.2)
send_cmd(ser, "flushCfg", 0.1)

# Try dfeDataOutputMode with different values
# Mode 1 = frame-based, Mode 2 = continuous, Mode 3 = advanced frame
for mode in [1, 2, 3]:
    resp = send_cmd(ser, f"dfeDataOutputMode {mode}")
    if b'Error' not in resp:
        print(f"  dfeDataOutputMode {mode}: OK")
    else:
        print(f"  dfeDataOutputMode {mode}: {resp.decode(errors='ignore').strip()}")

# Use mode 1
send_cmd(ser, "dfeDataOutputMode 1")

# Basic configuration
cmds = [
    "channelCfg 15 7 0",
    "adcCfg 2 1",
    "adcbufCfg -1 0 1 1 1",
    "profileCfg 0 60 7 5 60 0 0 60 1 256 10000 0 0 30",
    "chirpCfg 0 0 0 0 0 0 0 1",
    "chirpCfg 1 1 0 0 0 0 0 2",
    "chirpCfg 2 2 0 0 0 0 0 4",
    "frameCfg 0 2 64 0 100 1 0",
    "lowPower 0 0",
    "guiMonitor -1 1 0 0 0 0 0",  # Minimal: just detected objects
    "cfarCfg -1 0 2 8 4 3 0 15 1",
    "cfarCfg -1 1 0 4 2 3 1 15 1",
    "multiObjBeamForming -1 1 0.5",
    "clutterRemoval -1 0",
    "calibDcRangeSig -1 0 -5 8 256",
    "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0",  # Disable LVDS
    "compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2",
    "analogMonitor 0 0",
    "aoaFovCfg -1 -90 90 -90 90",
]

for cmd in cmds:
    resp = send_cmd(ser, cmd, 0.03)
    if b'Error' in resp:
        print(f"  ERROR: {cmd}")

# Start sensor
print("\nStarting sensor...")
resp = send_cmd(ser, "sensorStart", 0.5)
print(f"sensorStart response: {resp[:100]}")

# Now continuously read from CLI port looking for data frames
print("\nReading from CLI port for 30 seconds...")
print("(Looking for magic word or any binary data)\n")

ser.timeout = 0.1
start = time.time()
total_bytes = 0
magic_count = 0
text_lines = 0
buffer = bytearray()

while time.time() - start < 30:
    data = ser.read(1024)
    if data:
        total_bytes += len(data)
        buffer.extend(data)

        # Check for magic word
        if MAGIC in buffer:
            idx = buffer.find(MAGIC)
            magic_count += 1
            print(f"  [FRAME] Magic word at offset {idx}, buffer size {len(buffer)}")
            buffer = buffer[idx + 8:]

        # Check for text responses (like debug output)
        try:
            text = data.decode('utf-8', errors='ignore')
            for line in text.split('\n'):
                if line.strip():
                    text_lines += 1
                    if text_lines <= 10:  # Print first 10 lines
                        print(f"  [TEXT] {line.strip()[:80]}")
        except:
            pass

        # Keep buffer manageable
        if len(buffer) > 10000:
            buffer = buffer[-1000:]

    # Print progress every 5 seconds
    elapsed = time.time() - start
    if int(elapsed) % 5 == 0 and int(elapsed) > 0:
        if total_bytes > 0:
            print(f"  ... {elapsed:.0f}s: {total_bytes} bytes, {magic_count} frames, {text_lines} text lines")

ser.close()

print(f"\n=== Results ===")
print(f"Total bytes received: {total_bytes}")
print(f"Magic words (frames): {magic_count}")
print(f"Text lines: {text_lines}")

if total_bytes == 0:
    print("\n[DIAGNOSIS] No data received on CLI UART after sensorStart")
    print("This suggests the data UART is NOT connected via USB.")
    print("")
    print("For IWR6843AOPEVM, data output options:")
    print("1. LVDS output (requires capture card)")
    print("2. Separate UART pins on J3/J4 connector")
    print("3. Different firmware that sends data on CLI UART")
elif magic_count == 0:
    print("\n[DIAGNOSIS] Text data received but no frame data")
    print("The radar is outputting debug info but not point cloud data")
else:
    print("\n[SUCCESS] Frames detected on CLI UART!")
