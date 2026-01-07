#!/usr/bin/env python3
"""
Example: Vital signs monitoring with chirp firmware

This script demonstrates how to extract heart rate and respiratory rate
from a radar running chirp firmware with PHASE output mode (TLV 0x0520).

Requirements:
    - IWR6843 flashed with chirp firmware
    - chirp configured for PHASE output mode:
        chirpOutputMode 3 0 0  (PHASE mode)

Usage:
    python example_chirp_vitals.py --config configs/vital_signs.cfg
    python example_chirp_vitals.py --cli-port /dev/ttyACM0 --data-port /dev/ttyACM1
"""

import argparse
import signal
import sys
import time
from pathlib import Path

from ambient.sensor import RadarSensor, SerialConfig
from ambient.vitals import ChirpVitalsProcessor, VitalsConfig


def main():
    parser = argparse.ArgumentParser(
        description="Vital signs monitoring with chirp firmware"
    )
    parser.add_argument("--cli-port", help="CLI serial port (e.g., /dev/ttyACM0)")
    parser.add_argument("--data-port", help="Data serial port (e.g., /dev/ttyACM1)")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/vital_signs.cfg"),
        help="Path to chirp config file",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Duration to run (seconds, 0=infinite)",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=20.0,
        help="Expected frame rate (Hz)",
    )
    args = parser.parse_args()

    # Setup signal handler for clean exit
    stop_flag = {"stop": False}

    def signal_handler(signum, frame):
        print("\nStopping...")
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Configure sensor
    serial_config = SerialConfig(
        cli_port=args.cli_port or "",
        data_port=args.data_port or "",
    )

    # Configure vitals processor
    vitals_config = VitalsConfig(
        sample_rate_hz=args.sample_rate,
        window_seconds=10.0,
    )
    processor = ChirpVitalsProcessor(vitals_config)

    # Connect and run
    sensor = RadarSensor(serial_config)

    try:
        print("Connecting to radar...")
        sensor.connect()
        print(f"Connected!")

        # Check firmware
        fw_info = sensor.detect_firmware()
        print(f"Firmware: {fw_info.get('raw', 'unknown')}")

        # Send configuration
        if args.config.exists():
            print(f"Sending configuration: {args.config}")
            sensor.configure(args.config)
            print("Configuration sent!")
        else:
            print(f"Warning: Config file not found: {args.config}")
            print("Make sure chirp is configured for PHASE output mode")

        # Start sensor
        print("\nStarting sensor...")
        sensor.start()
        time.sleep(0.5)

        # Display header
        print("\n" + "=" * 70)
        print(f"{'Frame':>6} | {'HR (BPM)':>12} | {'RR (BPM)':>12} | {'Quality':>8} | Status")
        print("=" * 70)

        start_time = time.time()
        frame_count = 0
        chirp_frames = 0

        # Main loop
        while not stop_flag["stop"]:
            # Check duration
            elapsed = time.time() - start_time
            if args.duration > 0 and elapsed >= args.duration:
                break

            # Read frame
            frame = sensor.read_frame(timeout=0.1)
            if not frame:
                continue

            frame_count += 1

            # Process chirp PHASE TLV if present
            if frame.chirp_phase:
                chirp_frames += 1
                vitals = processor.process_chirp_phase(frame.chirp_phase)

                # Build status string
                status_parts = []
                if vitals.motion_detected:
                    status_parts.append("MOTION")
                if not processor.is_ready:
                    status_parts.append(f"buffering {processor.buffer_fullness*100:.0f}%")
                status = ", ".join(status_parts) if status_parts else "OK"

                # Format rates
                hr_str = f"{vitals.heart_rate_bpm:.1f}" if vitals.heart_rate_bpm else "---"
                rr_str = f"{vitals.respiratory_rate_bpm:.1f}" if vitals.respiratory_rate_bpm else "---"

                # Print update
                print(
                    f"{frame_count:6d} | "
                    f"{hr_str:>8} ± {vitals.heart_rate_confidence*100:3.0f}% | "
                    f"{rr_str:>8} ± {vitals.respiratory_rate_confidence*100:3.0f}% | "
                    f"{vitals.signal_quality*100:6.1f}% | "
                    f"{status}"
                )

                # Print valid readings more prominently
                if vitals.is_valid():
                    print(
                        f"  --> Valid reading: HR={vitals.heart_rate_bpm:.0f} BPM, "
                        f"RR={vitals.respiratory_rate_bpm:.1f} BPM"
                    )

            # Also check for chirp presence detection
            elif frame.chirp_presence:
                presence = frame.chirp_presence
                status = ["absent", "present", "motion"][presence.presence]
                print(
                    f"{frame_count:6d} | "
                    f"{'---':>12} | {'---':>12} | "
                    f"{presence.confidence:6d}% | "
                    f"PRESENCE: {status} @ {presence.range_m:.2f}m"
                )

        # Summary
        print("\n" + "=" * 70)
        elapsed = time.time() - start_time
        print(f"Received {frame_count} frames in {elapsed:.1f} seconds")
        print(f"Chirp PHASE frames: {chirp_frames}")
        if frame_count > 0:
            print(f"Average frame rate: {frame_count / elapsed:.1f} fps")

    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        print("Stopping sensor...")
        sensor.stop()
        sensor.disconnect()
        print("Done.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
