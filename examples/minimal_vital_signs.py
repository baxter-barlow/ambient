#!/usr/bin/env python3
"""Minimal vital signs monitoring example.

Connects to radar sensor and prints heart rate and respiratory rate.
Usage: python examples/minimal_vital_signs.py
"""
from ambient import RadarSensor, ProcessingPipeline, VitalsExtractor

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
