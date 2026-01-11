#!/usr/bin/env python3
"""Minimal vital signs monitoring.

Connects to radar and prints heart rate and respiratory rate.
"""
from ambient import ProcessingPipeline, RadarSensor, VitalsExtractor

sensor = RadarSensor()
sensor.connect()
sensor.configure("configs/vital_signs.cfg")
sensor.start()

pipeline = ProcessingPipeline()
extractor = VitalsExtractor()

print("Monitoring vital signs... (Ctrl+C to stop)")
print("HR (BPM) | RR (BPM) | Quality")
print("-" * 35)

try:
	for frame in sensor.stream():
		processed = pipeline.process(frame)
		vitals = extractor.process_frame(processed)
		if vitals.is_valid():
			print(f"{vitals.heart_rate_bpm:>7.1f} | {vitals.respiratory_rate_bpm:>7.1f} | {vitals.quality_summary()}")
except KeyboardInterrupt:
	pass
finally:
	sensor.stop()
	sensor.disconnect()
