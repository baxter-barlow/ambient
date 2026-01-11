#!/usr/bin/env python3
"""Test ChirpVitalsProcessor with live PHASE data from chirp firmware.

This script:
1. Configures sensor with chirp firmware in PHASE mode
2. Uses ChirpVitalsProcessor to extract vital signs
3. Displays heart rate and respiratory rate estimates
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ambient.sensor.config import SerialConfig
from ambient.sensor.radar import RadarSensor
from ambient.vitals.extractor import ChirpVitalsProcessor, VitalsConfig

CLI_PORT = "/dev/ttyUSB0"
DATA_PORT = "/dev/ttyUSB1"
CONFIG_FILE = Path(__file__).parent.parent / "configs" / "vital_signs_chirp.cfg"


def main():
    import builtins
    original_print = builtins.print
    def print(*args, **kwargs):
        kwargs.setdefault('flush', True)
        original_print(*args, **kwargs)

    print("Chirp Vital Signs Test")
    print("=" * 60)

    config = SerialConfig(cli_port=CLI_PORT, data_port=DATA_PORT)
    sensor = RadarSensor(config=config)

    # Initialize vitals processor (20 Hz sample rate, 10 sec window)
    vitals_config = VitalsConfig(sample_rate_hz=20.0, window_seconds=10.0)
    vitals_processor = ChirpVitalsProcessor(config=vitals_config)

    try:
        print(f"Connecting to {CLI_PORT} / {DATA_PORT}...", flush=True)
        sensor.connect()
        print("Connected", flush=True)

        # Send config (without sensorStart)
        print(f"\nLoading config from {CONFIG_FILE.name}")
        sensor.configure(CONFIG_FILE)
        time.sleep(0.2)

        # Configure target detection (sensitive settings)
        print("Configuring target detection (0.2-5.0m, SNR=5)")
        sensor.send_command("chirp target 0.2 5.0 5 4", timeout=0.2)
        time.sleep(0.1)

        # Enable PHASE output mode
        print("Enabling PHASE output mode")
        sensor.send_command("chirp mode 3 1 1", timeout=0.2)
        time.sleep(0.1)

        # Start sensor
        print("Starting sensor")
        sensor.send_command("sensorStart", timeout=0.2)
        sensor._running = True
        time.sleep(0.5)

        # Verify target detected
        response = sensor.send_command("chirp status", timeout=0.2)
        for line in response.strip().split('\n'):
            if 'target' in line.lower():
                print(f"  {line.strip()}")

        print("\nCollecting vital signs data...")
        print("-" * 60)
        print("HR = Heart Rate (BPM), RR = Respiratory Rate (BPM)")
        print("Quality = Signal quality (0-100%)")
        print("-" * 60)

        start_time = time.time()
        frame_count = 0
        vitals_count = 0
        last_display = start_time

        while time.time() - start_time < 60:  # Run for 60 seconds
            frame = sensor.read_frame(timeout=0.1)
            if frame:
                frame_count += 1

                # Process frame through vitals processor
                vitals = vitals_processor.process_frame(frame)

                if vitals is not None:
                    vitals_count += 1

                    # Display every second
                    now = time.time()
                    if now - last_display >= 1.0:
                        last_display = now
                        elapsed = now - start_time

                        hr_str = f"{vitals.heart_rate_bpm:5.1f}" if vitals.heart_rate_bpm is not None else "  ---"
                        rr_str = f"{vitals.respiratory_rate_bpm:5.1f}" if vitals.respiratory_rate_bpm is not None else "  ---"
                        qual = int(vitals.signal_quality * 100)

                        print(f"[{elapsed:5.1f}s] HR: {hr_str} BPM | "
                              f"RR: {rr_str} BPM | "
                              f"Quality: {qual:3d}% | "
                              f"Frames: {frame_count}")

        # Summary
        print("-" * 60)
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0

        print("\nResults:")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Frames: {frame_count} ({fps:.1f} FPS)")
        print(f"  Vitals extracted: {vitals_count}")

        # Get final vitals
        final_vitals = vitals_processor.get_current_vitals()
        if final_vitals:
            print("\nFinal estimates:")
            if final_vitals.heart_rate_bpm is not None:
                print(f"  Heart Rate: {final_vitals.heart_rate_bpm:.1f} BPM")
            if final_vitals.respiratory_rate_bpm is not None:
                print(f"  Respiratory Rate: {final_vitals.respiratory_rate_bpm:.1f} BPM")
            print(f"  Quality: {final_vitals.signal_quality * 100:.0f}%")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        print("\nStopping sensor...")
        sensor.stop()
        sensor.disconnect()
        print("Done")


if __name__ == "__main__":
    main()
