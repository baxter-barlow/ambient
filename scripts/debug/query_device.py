#!/usr/bin/env python3
"""Query device info and test data output configurations."""
import os
import stat
import sys
import time
from pathlib import Path

import serial

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ambient.sensor.ports import find_ti_radar_ports, get_default_ports


def query(ser, cmd, wait=0.2):
	"""Send command and return response."""
	ser.reset_input_buffer()
	ser.write(f"{cmd}\n".encode())
	time.sleep(wait)
	return ser.read(ser.in_waiting).decode("utf-8", errors="ignore")


def main():
	print("=== Device Query ===\n")

	# Auto-detect ports
	ports = find_ti_radar_ports()
	if ports:
		cli_port = ports["cli"]
		data_port = ports["data"]
		print(f"Detected ports: CLI={cli_port}, Data={data_port}")
	else:
		cli_port, data_port = get_default_ports()
		print(f"Could not auto-detect, using defaults: CLI={cli_port}, Data={data_port}")

	ser = serial.Serial(cli_port, 115200, timeout=1)
	time.sleep(0.1)

	print("Version:")
	print(query(ser, "version", 0.3))

	print("\nSensor status:")
	print(query(ser, "sensorStop", 0.2))

	print("\nQuery commands:")
	for cmd in ["queryDemoStatus", "getStats", "status", "sensorStatus"]:
		resp = query(ser, cmd, 0.2)
		if resp.strip() and "Error" not in resp and "Unknown" not in resp:
			print(f"  {cmd}: {resp.strip()[:100]}")

	print("\n=== Data Output Modes ===\n")

	query(ser, "sensorStop")
	query(ser, "flushCfg")

	print("Minimal config...")
	for cmd in [
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
	]:
		resp = query(ser, cmd, 0.05)
		if "Error" in resp:
			print(f"  ERROR: {cmd}")

	print("\nguiMonitor configs:")
	for gui in [
		"guiMonitor -1 1 0 0 0 0 0",
		"guiMonitor -1 1 1 0 0 0 1",
		"guiMonitor 0 1 0 0 0 0 0",
		"guiMonitor 0 1 1 1 1 1 1",
	]:
		resp = query(ser, gui, 0.05)
		status = "OK" if "Error" not in resp else "ERROR"
		print(f"  [{status}] {gui}")

	print("\nCFAR config:")
	for cmd in ["cfarCfg -1 0 2 8 4 3 0 15 1", "cfarCfg -1 1 0 4 2 3 1 15 1"]:
		resp = query(ser, cmd, 0.05)
		status = "OK" if "Error" not in resp else "ERROR"
		print(f"  [{status}] {cmd}")

	print("\nAdditional configs:")
	for cmd in [
		"multiObjBeamForming -1 1 0.5",
		"clutterRemoval -1 0",
		"calibDcRangeSig -1 0 -5 8 256",
		"extendedMaxVelocity -1 0",
		"lvdsStreamCfg -1 0 0 0",
		"compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0",
		"measureRangeBiasAndRxChanPhase 0 1.5 0.2",
		"analogMonitor 0 0",
		"aoaFovCfg -1 -90 90 -90 90",
	]:
		resp = query(ser, cmd, 0.05)
		if "Error" in resp:
			print(f"  ERROR: {cmd}")

	print("\nStarting sensor...")
	resp = query(ser, "sensorStart", 0.3)
	print(f"Response: {resp.strip()[:200]}")

	print("\n=== CLI port data check ===")
	time.sleep(1)

	for _ in range(5):
		data = ser.read(ser.in_waiting)
		if data:
			print(f"Received {len(data)} bytes")
			print(f"Hex: {data[:50].hex()}")
			if b"\x02\x01\x04\x03\x06\x05\x08\x07" in data:
				print("MAGIC WORD FOUND!")
			break
		time.sleep(0.5)
	else:
		print("No data on CLI port")

	ser.close()

	print("\n=== Port permissions ===")
	for port in [cli_port, data_port]:
		try:
			st = os.stat(port)
			print(f"{port}: {stat.filemode(st.st_mode)}")
		except OSError as e:
			print(f"{port}: {e}")


if __name__ == "__main__":
	main()
