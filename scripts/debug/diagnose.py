#!/usr/bin/env python3
"""Diagnostic script to debug radar data acquisition issues."""

import sys
import time

import serial
import serial.tools.list_ports

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'

def list_ports():
    """List all available serial ports."""
    print("=== Available Serial Ports ===")
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("  No serial ports found!")
        return []
    for p in ports:
        print(f"  {p.device}: {p.description} [hwid: {p.hwid}]")
    return ports

def test_cli_port(port, baud=115200):
    """Test CLI port responsiveness."""
    print(f"\n=== Testing CLI Port: {port} @ {baud} ===")
    try:
        ser = serial.Serial(port, baud, timeout=2)
        time.sleep(0.1)
        ser.reset_input_buffer()

        # Send a simple command
        ser.write(b"version\n")
        time.sleep(0.3)
        response = ser.read(ser.in_waiting)

        if response and len(response) > 5:
            print(f"  Response to 'version': {response[:200]}")
            if b'mmWave' in response or b'SDK' in response or b'Done' in response:
                print("  [OK] Radar CLI is responding")
                ser.close()
                return True
            else:
                print("  [WARN] Response doesn't look like radar CLI")
        else:
            print("  [ERROR] No response from CLI port!")
            print("  The radar is not responding to commands.")
            print("  Try:")
            print("    1. Power cycle the radar (unplug and replug USB)")
            print("    2. Check if ports are swapped (try the other port)")
            print("    3. Verify firmware is flashed correctly")
            ser.close()
            return False

        ser.close()
        return True
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def test_data_port(port, baud=921600, duration=5):
    """Test data port for incoming data."""
    print(f"\n=== Testing Data Port: {port} @ {baud} for {duration}s ===")
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
        time.sleep(0.1)
        ser.reset_input_buffer()

        total_bytes = 0
        magic_count = 0
        start = time.time()
        buffer = bytearray()

        print("  Listening for data...")
        while time.time() - start < duration:
            available = ser.in_waiting
            if available:
                data = ser.read(available)
                total_bytes += len(data)
                buffer.extend(data)

                # Count magic words
                while True:
                    idx = buffer.find(MAGIC_WORD)
                    if idx == -1:
                        buffer = buffer[-8:]  # Keep last 8 bytes
                        break
                    magic_count += 1
                    buffer = buffer[idx + 8:]
            else:
                time.sleep(0.01)

        ser.close()

        print(f"  Total bytes received: {total_bytes}")
        print(f"  Magic words found: {magic_count}")

        if total_bytes == 0:
            print("  [ERROR] No data received on data port!")
            print("  Possible causes:")
            print("    - Sensor not started (config not sent or sensorStart missing)")
            print("    - Wrong port (CLI and data ports may be swapped)")
            print("    - Wrong baud rate")
        elif magic_count == 0:
            print("  [WARN] Data received but no valid frames found")
            print("  Possible causes:")
            print("    - Wrong baud rate (data corruption)")
            print("    - Different firmware with different magic word")
        else:
            fps = magic_count / duration
            print(f"  [OK] Receiving valid frames at ~{fps:.1f} fps")

        return total_bytes, magic_count

    except Exception as e:
        print(f"  [ERROR] {e}")
        return 0, 0

def test_config_send(cli_port, config_path, baud=115200):
    """Send config and check for errors."""
    print(f"\n=== Sending Config: {config_path} ===")
    try:
        ser = serial.Serial(cli_port, baud, timeout=1)
        time.sleep(0.1)
        ser.reset_input_buffer()

        errors = []
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('%'):
                    continue

                ser.write(f"{line}\n".encode())
                time.sleep(0.05)
                response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')

                if 'Error' in response or 'error' in response:
                    errors.append((line, response))
                    print(f"  [ERROR] {line}")
                    print(f"          {response.strip()}")
                else:
                    print(f"  [OK] {line}")

                time.sleep(0.02)

        ser.close()

        if errors:
            print(f"\n  {len(errors)} command(s) failed!")
        else:
            print("\n  All commands sent successfully")

        return len(errors) == 0

    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def main():
    print("IWR6843AOP Radar Diagnostics\n")

    # Step 1: List ports
    ports = list_ports()

    # Find likely radar ports - check for ttyACM, ttyUSB, or XDS devices
    radar_ports = []
    for p in ports:
        if 'ttyACM' in p.device or 'ttyUSB' in p.device or 'XDS' in p.description:
            radar_ports.append(p)

    # Sort by device name
    radar_ports.sort(key=lambda p: p.device)

    if len(radar_ports) < 2:
        print("\n[ERROR] Need at least 2 serial ports for radar (CLI + Data)")
        print("Check USB connection and permissions (dialout group)")
        print("\nFor IWR6843AOPEVM, you may need to connect BOTH USB ports:")
        print("  - One for CLI/power (CP2105)")
        print("  - One for data (XDS110)")
        sys.exit(1)

    # For CP2105: Enhanced port (usually ttyUSB0) is CLI, Standard port (ttyUSB1) is Data
    # For XDS/ACM: Lower number is CLI, higher is Data
    cli_port = radar_ports[0].device
    data_port = radar_ports[1].device

    # Check if this is a CP2105:
    # - Enhanced port supports higher baud (up to 2M) -> use for DATA (921600)
    # - Standard port limited to 460800 -> use for CLI (115200)
    for p in radar_ports:
        if 'Enhanced' in p.description:
            data_port = p.device  # High-speed data port
        elif 'Standard' in p.description:
            cli_port = p.device   # Low-speed CLI port
    print(f"\nUsing CLI: {cli_port}, Data: {data_port}")

    # Step 2: Test CLI port
    cli_ok = test_cli_port(cli_port)

    # If CLI didn't respond, try the other port
    if not cli_ok:
        print("\n--- Trying swapped ports ---")
        cli_port, data_port = data_port, cli_port
        print(f"Swapped: CLI: {cli_port}, Data: {data_port}")
        cli_ok = test_cli_port(cli_port)

        if not cli_ok:
            print("\n[ERROR] Radar not responding on either port!")
            print("\nTroubleshooting steps:")
            print("  1. Power cycle: Unplug USB, wait 5 seconds, replug")
            print("  2. Check cables: Try a different USB cable")
            print("  3. Check firmware: Reflash using TI UniFlash")
            print("  4. Check for ttyACM devices (may need second USB)")
            sys.exit(1)

    # Step 3: Check data port before config
    print("\n--- Before sending config ---")
    test_data_port(data_port, duration=2)

    # Step 4: Send config
    config_path = "configs/basic.cfg"
    if not test_config_send(cli_port, config_path):
        print("\n[WARN] Config had errors, but continuing...")

    # Step 5: Check data port after config
    print("\n--- After sending config ---")
    bytes_recv, frames = test_data_port(data_port, duration=5)

    # Also check if data comes on same port as CLI
    if bytes_recv == 0:
        print("\n--- Checking CLI port for data ---")
        b2, f2 = test_data_port(cli_port, baud=115200, duration=3)
        if f2 > 0:
            print("\nData found on CLI port! Use same port for both.")
            data_port = cli_port
            bytes_recv, frames = b2, f2

    # Summary
    print("\n=== Summary ===")
    if frames > 0:
        print("Radar is working!")
        print(f"  CLI port:  {cli_port} @ 115200")
        print(f"  Data port: {data_port} @ 921600")
        print("\nTry running: python example_basic.py")
    elif bytes_recv > 0:
        print("Data received but no valid frames. Check baud rate or firmware.")
    else:
        print("No data received. Possible issues:")
        print("  1. IWR6843AOPEVM may need BOTH USB ports connected")
        print("     (CP2105 for CLI, XDS110 for data)")
        print("  2. Wrong data port baud rate")
        print("  3. Hardware issue - test with TI's demo visualizer")

if __name__ == "__main__":
    main()
