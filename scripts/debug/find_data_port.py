#!/usr/bin/env python3
"""Find and test the data port after connecting second USB."""

import time

import serial
import serial.tools.list_ports

MAGIC = b'\x02\x01\x04\x03\x06\x05\x08\x07'

print("=== Scanning for Serial Ports ===\n")

ports = list(serial.tools.list_ports.comports())
usb_ports = [p for p in ports if 'ttyUSB' in p.device or 'ttyACM' in p.device]

print("USB Serial Ports Found:")
for p in sorted(usb_ports, key=lambda x: x.device):
    print(f"  {p.device}: {p.description}")

if len(usb_ports) < 3:
    print(f"\nOnly {len(usb_ports)} USB serial ports found.")
    print("Please connect the SECOND USB port on the radar board.")
    print("After connecting, run this script again.")
    exit(1)

# Identify ports by description
cli_port = None
data_port = None
xds_ports = []

for p in usb_ports:
    if 'Enhanced' in p.description:
        cli_port = p.device
    elif 'XDS' in p.description or 'ACM' in p.device:
        xds_ports.append(p.device)
    elif 'Standard' in p.description:
        pass  # CP2105 standard port - not used for data

# The XDS110 usually creates ttyACM devices for data
if xds_ports:
    xds_ports.sort()
    data_port = xds_ports[-1]  # Usually the higher-numbered one is data

print("\nIdentified ports:")
print(f"  CLI port:  {cli_port}")
print(f"  Data port: {data_port}")

if not cli_port or not data_port:
    print("\nCouldn't auto-identify ports. Trying all combinations...")
    cli_port = usb_ports[0].device
    data_port = usb_ports[-1].device
    print(f"  Trying CLI: {cli_port}, Data: {data_port}")

# Configure radar via CLI
print(f"\n=== Configuring radar via {cli_port} ===")
cli = serial.Serial(cli_port, 115200, timeout=1)
time.sleep(0.2)
cli.reset_input_buffer()

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

for line in config.strip().split('\n'):
    cli.write(f"{line}\n".encode())
    time.sleep(0.03)
    cli.read(cli.in_waiting)

print("Configuration sent")
cli.close()

# Test data port
print(f"\n=== Testing data port {data_port} ===")

for baud in [921600, 460800, 115200]:
    print(f"\nTrying {baud} baud...")
    try:
        data = serial.Serial(data_port, baud, timeout=0.5)
        time.sleep(0.1)
        data.reset_input_buffer()

        total = 0
        frames = 0
        buf = bytearray()
        start = time.time()

        while time.time() - start < 5:
            chunk = data.read(1024)
            if chunk:
                total += len(chunk)
                buf.extend(chunk)
                while MAGIC in buf:
                    frames += 1
                    idx = buf.find(MAGIC)
                    buf = buf[idx + 8:]

        data.close()

        print(f"  Received: {total} bytes, {frames} frames")
        if frames > 0:
            print(f"\n*** SUCCESS! Data port is {data_port} at {baud} baud ***")
            print("\nUpdate radar.py to use:")
            print(f"  cli_port = '{cli_port}'")
            print(f"  data_port = '{data_port}'")
            break
    except Exception as e:
        print(f"  Error: {e}")
