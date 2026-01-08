#!/usr/bin/env python3
"""Record radar data and vital signs to file.

Usage: python examples/recording_session.py [duration_seconds] [output_file]
Default: 60 seconds, data/session_{timestamp}.h5
"""
import sys
import time
from datetime import datetime
from pathlib import Path

from ambient import RadarSensor, ProcessingPipeline, VitalsExtractor
from ambient.storage import HDF5Writer

# Parse arguments
duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
output = sys.argv[2] if len(sys.argv) > 2 else None

if output is None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = f"data/session_{timestamp}.h5"

Path(output).parent.mkdir(parents=True, exist_ok=True)

# Initialize
sensor = RadarSensor()
pipeline = ProcessingPipeline()
extractor = VitalsExtractor()
writer = HDF5Writer(output)

sensor.connect()
sensor.configure("configs/vital_signs.cfg")
sensor.start()

print(f"Recording to {output} for {duration}s...")
print("Frame | HR | RR | Quality")
print("-" * 40)

start = time.time()
frame_count = 0

try:
    for frame in sensor.stream(duration=duration):
        frame_count += 1

        # Process and extract vitals
        processed = pipeline.process(frame)
        vitals = extractor.process_frame(processed)

        # Write to file
        writer.write_frame(frame)
        if vitals.is_valid():
            writer.write_vitals(vitals)

        # Print progress every second
        elapsed = time.time() - start
        if frame_count % 20 == 0:
            hr = vitals.heart_rate_bpm or 0
            rr = vitals.respiratory_rate_bpm or 0
            print(f"{frame_count:5d} | {hr:5.1f} | {rr:4.1f} | {vitals.quality_summary()}")

except KeyboardInterrupt:
    print("\nRecording interrupted")
finally:
    sensor.stop()
    sensor.disconnect()
    writer.close()

    elapsed = time.time() - start
    print(f"\nRecorded {frame_count} frames in {elapsed:.1f}s")
    print(f"Output: {output}")
