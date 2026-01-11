#!/usr/bin/env python3
"""Test if data can be routed through CLI UART."""
import time

import serial

MAGIC = b"\x02\x01\x04\x03\x06\x05\x08\x07"
CLI_PORT = "/dev/ttyUSB0"


def send_cmd(ser, cmd, wait=0.1):
	"""Send command and return response."""
	ser.write(f"{cmd}\n".encode())
	time.sleep(wait)
	return ser.read(ser.in_waiting)


def main():
	print("=== Testing Data on CLI UART ===\n")

	ser = serial.Serial(CLI_PORT, 115200, timeout=1)
	time.sleep(0.2)
	ser.reset_input_buffer()
	ser.reset_output_buffer()

	ser.write(b"version\n")
	time.sleep(0.3)
	version = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
	print(f"Version:\n{version}")

	print("\nConfiguring...")
	send_cmd(ser, "sensorStop", 0.2)
	send_cmd(ser, "flushCfg", 0.1)

	for mode in [1, 2, 3]:
		resp = send_cmd(ser, f"dfeDataOutputMode {mode}")
		status = "OK" if b"Error" not in resp else resp.decode(errors="ignore").strip()
		print(f"  dfeDataOutputMode {mode}: {status}")

	send_cmd(ser, "dfeDataOutputMode 1")

	for cmd in [
		"channelCfg 15 7 0",
		"adcCfg 2 1",
		"adcbufCfg -1 0 1 1 1",
		"profileCfg 0 60 7 5 60 0 0 60 1 256 10000 0 0 30",
		"chirpCfg 0 0 0 0 0 0 0 1",
		"chirpCfg 1 1 0 0 0 0 0 2",
		"chirpCfg 2 2 0 0 0 0 0 4",
		"frameCfg 0 2 64 0 100 1 0",
		"lowPower 0 0",
		"guiMonitor -1 1 0 0 0 0 0",
		"cfarCfg -1 0 2 8 4 3 0 15 1",
		"cfarCfg -1 1 0 4 2 3 1 15 1",
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
		resp = send_cmd(ser, cmd, 0.03)
		if b"Error" in resp:
			print(f"  ERROR: {cmd}")

	print("\nStarting sensor...")
	resp = send_cmd(ser, "sensorStart", 0.5)
	print(f"Response: {resp[:100]}")

	print("\nReading CLI port for 30s...\n")

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

			if MAGIC in buffer:
				idx = buffer.find(MAGIC)
				magic_count += 1
				print(f"  [FRAME] Magic at offset {idx}, buf={len(buffer)}")
				buffer = buffer[idx + 8 :]

			text = data.decode("utf-8", errors="ignore")
			for line in text.split("\n"):
				if line.strip():
					text_lines += 1
					if text_lines <= 10:
						print(f"  [TEXT] {line.strip()[:80]}")

			if len(buffer) > 10000:
				buffer = buffer[-1000:]

		elapsed = time.time() - start
		if int(elapsed) % 5 == 0 and int(elapsed) > 0 and total_bytes > 0:
			print(f"  ... {elapsed:.0f}s: {total_bytes}B, {magic_count} frames")

	ser.close()

	print("\n=== Results ===")
	print(f"Bytes: {total_bytes}, Frames: {magic_count}, Text: {text_lines}")

	if total_bytes == 0:
		print("\nNo data on CLI UART - data UART not connected via USB")
	elif magic_count == 0:
		print("\nText only - radar outputting debug, not point cloud")
	else:
		print("\nFrames detected on CLI UART!")


if __name__ == "__main__":
	main()
