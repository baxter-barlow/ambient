#!/usr/bin/env python3
"""Room presence detector.

Detects if someone is present in the sensor's field of view.
"""
import time
from collections import deque

from ambient import ProcessingPipeline, RadarSensor

MOTION_THRESHOLD = 0.1  # m/s minimum velocity
PRESENCE_WINDOW = 5.0   # seconds to average
MIN_POINTS = 2          # minimum detections for presence

sensor = RadarSensor()
sensor.connect()
sensor.configure("configs/vital_signs.cfg")
sensor.start()

pipeline = ProcessingPipeline()
presence_history: deque[bool] = deque(maxlen=100)

print("Presence Detection Active (Ctrl+C to stop)")
print("=" * 40)

last_state = None
last_print = 0.0

try:
	for frame in sensor.stream():
		now = time.time()

		significant = [
			p for p in frame.detected_points
			if abs(p.velocity) > MOTION_THRESHOLD or p.range < 3.0
		]
		presence_history.append(len(significant) >= MIN_POINTS)

		if len(presence_history) >= 20:
			ratio = sum(presence_history) / len(presence_history)
			is_present = ratio > 0.3

			if is_present != last_state:
				status = "PRESENT" if is_present else "ABSENT"
				print(f"[{time.strftime('%H:%M:%S')}] {status}")
				last_state = is_present
			elif now - last_print > 10:
				status = "present" if is_present else "absent"
				print(f"[{time.strftime('%H:%M:%S')}] Still {status} ({ratio*100:.0f}%)")
				last_print = now

except KeyboardInterrupt:
	pass
finally:
	sensor.stop()
	sensor.disconnect()
	print("\nStopped")
