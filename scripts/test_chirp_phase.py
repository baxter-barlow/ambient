#!/usr/bin/env python3
"""Test chirp PHASE output with correct command sequence.

This script sends commands in the correct order:
1. Load config (without sensorStart)
2. Send chirp mode 3 1 1 (enable PHASE output)
3. Send sensorStart
4. Read and display PHASE TLV data
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ambient.sensor.config import SerialConfig
from ambient.sensor.radar import RadarSensor

CLI_PORT = "/dev/ttyUSB0"
DATA_PORT = "/dev/ttyUSB1"
CONFIG_FILE = Path(__file__).parent.parent / "configs" / "vital_signs_chirp.cfg"


def main():
    print("Chirp PHASE Output Test")
    print("=" * 50)

    config = SerialConfig(cli_port=CLI_PORT, data_port=DATA_PORT)
    sensor = RadarSensor(config=config)

    try:
        print(f"Connecting to {CLI_PORT} / {DATA_PORT}...")
        sensor.connect()
        print("Connected")

        # Step 1: Send config (without sensorStart)
        print(f"\nStep 1: Loading config from {CONFIG_FILE.name}")
        sensor.configure(CONFIG_FILE)
        time.sleep(0.2)

        # Step 2: Configure target detection (sensitive settings)
        print("\nStep 2: Configuring target detection (0.2-5.0m, SNR=5, 4 bins)")
        response = sensor.send_command("chirp target 0.2 5.0 5 4", timeout=0.2)
        for line in response.strip().split('\n'):
            if 'target' in line.lower() or 'range' in line.lower():
                print(f"  {line.strip()}")
        time.sleep(0.1)

        # Step 3: Enable PHASE output mode
        print("\nStep 3: Enabling PHASE output (chirp mode 3 1 1)")
        response = sensor.send_command("chirp mode 3 1 1", timeout=0.2)
        print(f"  Response: {response.strip()}")
        time.sleep(0.1)

        # Check chirp status
        print("\nStep 4: Verifying chirp status")
        response = sensor.send_command("chirp status", timeout=0.2)
        for line in response.strip().split('\n'):
            if line.strip():
                print(f"  {line.strip()}")
        time.sleep(0.1)

        # Step 5: Start sensor
        print("\nStep 5: Starting sensor")
        response = sensor.send_command("sensorStart", timeout=0.2)
        print(f"  Response: {response.strip()}")
        sensor._running = True
        time.sleep(0.5)

        # Verify sensor is running
        response = sensor.send_command("chirp status", timeout=0.2)
        for line in response.strip().split('\n'):
            if 'state' in line.lower() or 'target' in line.lower():
                print(f"  {line.strip()}")

        # Step 6: Read frames and look for PHASE TLV
        print("\nStep 6: Reading frames (15 seconds)...")
        print("-" * 50)

        start_time = time.time()
        frame_count = 0
        phase_count = 0
        tlv_types_seen = set()
        last_print = start_time

        while time.time() - start_time < 15:
            # Print progress every second if no frames
            if frame_count == 0 and time.time() - last_print > 1.0:
                elapsed = time.time() - start_time
                print(f"  Waiting for frames... ({elapsed:.0f}s)")
                last_print = time.time()
            frame = sensor.read_frame(timeout=0.1)
            if frame:
                frame_count += 1

                # Track all TLV types
                if frame.range_profile is not None:
                    tlv_types_seen.add("range_profile")
                if frame.detected_points is not None:
                    tlv_types_seen.add("detected_points")
                if frame.range_doppler_heatmap is not None:
                    tlv_types_seen.add("range_doppler")
                if frame.chirp_phase is not None:
                    tlv_types_seen.add("chirp_phase")
                    phase_count += 1
                    phase = frame.chirp_phase
                    if phase.bins:
                        print(f"Frame {frame_count}: PHASE bins={phase.num_bins} "
                              f"center={phase.center_bin} "
                              f"phase[0]={phase.bins[0].phase:.2f}")
                if frame.chirp_target_iq is not None:
                    tlv_types_seen.add("chirp_target_iq")
                if frame.chirp_presence is not None:
                    tlv_types_seen.add("chirp_presence")
                if frame.chirp_motion is not None:
                    tlv_types_seen.add("chirp_motion")
                if frame.chirp_target_info is not None:
                    tlv_types_seen.add("chirp_target_info")

                # Progress indicator
                if frame_count % 50 == 0:
                    elapsed = time.time() - start_time
                    print(f"  ... {frame_count} frames, {phase_count} with phase "
                          f"({elapsed:.1f}s)")

        # Summary
        print("-" * 50)
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0

        print("\nResults:")
        print(f"  Total frames: {frame_count}")
        print(f"  Frames with PHASE: {phase_count}")
        print(f"  Frame rate: {fps:.1f} FPS")
        print(f"  TLV types seen: {sorted(tlv_types_seen)}")

        if phase_count == 0:
            print("\nWARNING: No PHASE TLVs received!")
            print("Check that chirp firmware supports mode 3 (PHASE)")
        else:
            print(f"\nSUCCESS: Received {phase_count} PHASE TLVs")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        print("\nStopping sensor...")
        sensor.stop()
        sensor.disconnect()
        print("Done")


if __name__ == "__main__":
    main()
