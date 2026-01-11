#!/usr/bin/env python3
"""Debug TLV types in radar frames."""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ambient.sensor.config import SerialConfig
from ambient.sensor.frame import (
    HEADER_SIZE,
    TLV_CHIRP_COMPLEX_RANGE_FFT,
    TLV_CHIRP_MOTION_STATUS,
    TLV_CHIRP_PHASE_OUTPUT,
    TLV_CHIRP_PRESENCE,
    TLV_CHIRP_TARGET_INFO,
    TLV_CHIRP_TARGET_IQ,
)
from ambient.sensor.radar import RadarSensor

TLV_NAMES = {
    1: "detected_points",
    2: "range_profile",
    3: "noise_profile",
    4: "azimuth_static",
    5: "range_doppler",
    6: "stats",
    7: "detected_points_side",
    8: "azimuth_elevation",
    9: "temperature",
    TLV_CHIRP_COMPLEX_RANGE_FFT: "chirp_raw_iq",
    TLV_CHIRP_TARGET_IQ: "chirp_target_iq",
    TLV_CHIRP_PHASE_OUTPUT: "chirp_phase",
    TLV_CHIRP_PRESENCE: "chirp_presence",
    TLV_CHIRP_MOTION_STATUS: "chirp_motion",
    TLV_CHIRP_TARGET_INFO: "chirp_target_info",
}

CLI_PORT = "/dev/ttyUSB0"
DATA_PORT = "/dev/ttyUSB1"
CONFIG_FILE = Path(__file__).parent.parent / "configs" / "vital_signs_chirp.cfg"


def parse_tlv_types(raw_data: bytes) -> list[tuple[int, int]]:
    """Extract TLV types and lengths from raw frame data."""
    tlvs = []
    if len(raw_data) < HEADER_SIZE:
        return tlvs

    # Parse header
    offset = HEADER_SIZE
    num_tlvs = struct.unpack_from("<H", raw_data, 44)[0]

    for _ in range(num_tlvs):
        if offset + 8 > len(raw_data):
            break
        tlv_type, tlv_len = struct.unpack_from("<II", raw_data, offset)
        tlvs.append((tlv_type, tlv_len))
        offset += 8 + tlv_len

    return tlvs


def main():
    print("TLV Type Debug")
    print("=" * 60)

    config = SerialConfig(cli_port=CLI_PORT, data_port=DATA_PORT)
    sensor = RadarSensor(config=config)

    try:
        print(f"Connecting to {CLI_PORT} / {DATA_PORT}...")
        sensor.connect()
        print("Connected")

        # Send config
        print(f"\nLoading config from {CONFIG_FILE.name}")
        sensor.configure(CONFIG_FILE)
        time.sleep(0.2)

        # Enable PHASE mode
        print("\nEnabling PHASE output (chirp mode 3 1 1)")
        response = sensor.send_command("chirp mode 3 1 1", timeout=0.2)
        print(f"  {response.strip().split(chr(10))[1] if chr(10) in response else response.strip()}")
        time.sleep(0.1)

        # Start sensor
        print("\nStarting sensor")
        sensor.send_command("sensorStart", timeout=0.2)
        sensor._running = True
        time.sleep(0.5)

        # Read frames and analyze TLVs
        print("\nReading frames (10 seconds)...")
        print("-" * 60)

        start_time = time.time()
        frame_count = 0
        tlv_histogram = {}

        while time.time() - start_time < 10:
            frame = sensor.read_frame(timeout=0.1)
            if frame:
                frame_count += 1

                # Parse raw TLV types
                tlvs = parse_tlv_types(frame.raw_data)

                for tlv_type, tlv_len in tlvs:
                    name = TLV_NAMES.get(tlv_type, f"unknown_0x{tlv_type:04X}")
                    if name not in tlv_histogram:
                        tlv_histogram[name] = {"count": 0, "type": tlv_type}
                    tlv_histogram[name]["count"] += 1

                # Print first few frames in detail
                if frame_count <= 3:
                    print(f"\nFrame {frame_count}:")
                    print(f"  Raw size: {len(frame.raw_data)} bytes")
                    print(f"  TLVs ({len(tlvs)}):")
                    for tlv_type, tlv_len in tlvs:
                        name = TLV_NAMES.get(tlv_type, "unknown")
                        print(f"    0x{tlv_type:04X} ({name}): {tlv_len} bytes")

        # Summary
        print("\n" + "-" * 60)
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0

        print(f"\nResults ({frame_count} frames at {fps:.1f} FPS):")
        print("\nTLV Types seen:")
        for name, info in sorted(tlv_histogram.items(), key=lambda x: -x[1]["count"]):
            pct = info["count"] / frame_count * 100
            print(f"  0x{info['type']:04X} {name:25s}: {info['count']:4d} ({pct:5.1f}%)")

        # Check for PHASE
        if "chirp_phase" in tlv_histogram:
            print("\nSUCCESS: PHASE TLV is present!")
        else:
            print("\nWARNING: PHASE TLV (0x0520) not found!")
            print("Expected TLV types for mode 3: chirp_phase, chirp_motion, chirp_target_info")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        print("\nStopping sensor...")
        sensor.stop()
        sensor.disconnect()
        print("Done")


if __name__ == "__main__":
    main()
