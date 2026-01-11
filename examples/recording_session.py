#!/usr/bin/env python3
"""Record radar data and vital signs to HDF5.

Usage: python recording_session.py [duration] [output]
Default: 60 seconds, data/session_{timestamp}.h5
"""
import sys
import time
from datetime import datetime
from pathlib import Path

from ambient import ProcessingPipeline, RadarSensor, VitalsExtractor
from ambient.storage import HDF5Writer

duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
output = sys.argv[2] if len(sys.argv) > 2 else None

if output is None:
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	output = f"data/session_{timestamp}.h5"

Path(output).parent.mkdir(parents=True, exist_ok=True)

sensor = RadarSensor()
pipeline = ProcessingPipeline()
extractor = VitalsExtractor()
writer = HDF5Writer(output)

sensor.connect()
sensor.configure("configs/vital_signs.cfg")
sensor.start()

print(f"Recording to {output} for {duration}s...")
print("Frame | HR    | RR   | Quality")
print("-" * 40)

start = time.time()
frame_count = 0

try:
	for frame in sensor.stream(duration=duration):
		frame_count += 1
		processed = pipeline.process(frame)
		vitals = extractor.process_frame(processed)

		writer.write_frame(frame)
		if vitals.is_valid():
			writer.write_vitals(vitals)

		if frame_count % 20 == 0:
			hr = vitals.heart_rate_bpm or 0
			rr = vitals.respiratory_rate_bpm or 0
			print(f"{frame_count:5d} | {hr:5.1f} | {rr:4.1f} | {vitals.quality_summary()}")

except KeyboardInterrupt:
	print("\nInterrupted")
finally:
	sensor.stop()
	sensor.disconnect()
	writer.close()
	elapsed = time.time() - start
	print(f"\nRecorded {frame_count} frames in {elapsed:.1f}s to {output}")
