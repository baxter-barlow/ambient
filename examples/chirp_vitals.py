#!/usr/bin/env python3
"""Vital signs with chirp firmware.

Extracts heart rate and respiratory rate from chirp PHASE output (TLV 0x0520).
Requires chirp firmware with PHASE mode: chirpOutputMode 3 0 0
"""
import argparse
import signal
import sys
import time
from pathlib import Path

from ambient.sensor import RadarSensor, SerialConfig
from ambient.vitals import ChirpVitalsProcessor, VitalsConfig


def main():
	parser = argparse.ArgumentParser(description="Vital signs with chirp firmware")
	parser.add_argument("--cli-port", help="CLI serial port")
	parser.add_argument("--data-port", help="Data serial port")
	parser.add_argument("--config", type=Path, default=Path("configs/vital_signs.cfg"))
	parser.add_argument("--duration", type=float, default=60.0, help="Seconds (0=infinite)")
	parser.add_argument("--sample-rate", type=float, default=20.0, help="Frame rate Hz")
	args = parser.parse_args()

	stop = {"flag": False}

	def on_signal(signum, frame):
		print("\nStopping...")
		stop["flag"] = True

	signal.signal(signal.SIGINT, on_signal)
	signal.signal(signal.SIGTERM, on_signal)

	config = SerialConfig(cli_port=args.cli_port or "", data_port=args.data_port or "")
	processor = ChirpVitalsProcessor(VitalsConfig(sample_rate_hz=args.sample_rate))
	sensor = RadarSensor(config)

	try:
		print("Connecting...")
		sensor.connect()
		print(f"Firmware: {sensor.detect_firmware().get('raw', 'unknown')}")

		if args.config.exists():
			sensor.configure(args.config)
			print(f"Config: {args.config}")
		else:
			print(f"Warning: {args.config} not found")

		sensor.start()
		time.sleep(0.5)

		print("\n" + "=" * 70)
		print(f"{'Frame':>6} | {'HR (BPM)':>12} | {'RR (BPM)':>12} | {'Quality':>8} | Status")
		print("=" * 70)

		start = time.time()
		frames = chirp_frames = 0

		while not stop["flag"]:
			if args.duration > 0 and time.time() - start >= args.duration:
				break

			frame = sensor.read_frame(timeout=0.1)
			if not frame:
				continue

			frames += 1

			if frame.chirp_phase:
				chirp_frames += 1
				v = processor.process_chirp_phase(frame.chirp_phase)

				status = []
				if v.motion_detected:
					status.append("MOTION")
				if not processor.is_ready:
					status.append(f"buffering {processor.buffer_fullness*100:.0f}%")

				hr = f"{v.heart_rate_bpm:.1f}" if v.heart_rate_bpm else "---"
				rr = f"{v.respiratory_rate_bpm:.1f}" if v.respiratory_rate_bpm else "---"

				print(
					f"{frames:6d} | {hr:>8} ± {v.heart_rate_confidence*100:3.0f}% | "
					f"{rr:>8} ± {v.respiratory_rate_confidence*100:3.0f}% | "
					f"{v.signal_quality*100:6.1f}% | {', '.join(status) or 'OK'}"
				)

				if v.is_valid():
					print(f"  --> HR={v.heart_rate_bpm:.0f} RR={v.respiratory_rate_bpm:.1f}")

			elif frame.chirp_presence:
				p = frame.chirp_presence
				state = ["absent", "present", "motion"][p.presence]
				print(f"{frames:6d} | {'---':>12} | {'---':>12} | {p.confidence:6d}% | {state} @ {p.range_m:.2f}m")

		elapsed = time.time() - start
		print("\n" + "=" * 70)
		print(f"Frames: {frames} ({chirp_frames} chirp) in {elapsed:.1f}s = {frames/elapsed:.1f} fps")

	except KeyboardInterrupt:
		pass
	except Exception as e:
		print(f"Error: {e}", file=sys.stderr)
		return 1
	finally:
		sensor.stop()
		sensor.disconnect()

	return 0


if __name__ == "__main__":
	sys.exit(main())
