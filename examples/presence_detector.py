#!/usr/bin/env python3
"""Simple room presence detector using radar.

Detects if someone is present in the sensor's field of view.
Usage: python examples/presence_detector.py
"""
import time
from collections import deque

from ambient import RadarSensor, ProcessingPipeline

# Configuration
MOTION_THRESHOLD = 0.1  # Minimum velocity to consider as motion
PRESENCE_WINDOW = 5.0   # Seconds to average for presence decision
MIN_POINTS = 2          # Minimum detected points to confirm presence

sensor = RadarSensor()
sensor.connect()
sensor.configure("configs/vital_signs.cfg")
sensor.start()

pipeline = ProcessingPipeline()
presence_history = deque(maxlen=100)  # ~5 seconds at 20 Hz

print("Presence Detection Active (Ctrl+C to stop)")
print("=" * 40)

last_state = None
last_print = 0

try:
    for frame in sensor.stream():
        now = time.time()

        # Count significant detections
        significant_points = [
            p for p in frame.detected_points
            if abs(p.velocity) > MOTION_THRESHOLD or p.range < 3.0
        ]

        presence_history.append(len(significant_points) >= MIN_POINTS)

        # Calculate presence over window
        if len(presence_history) >= 20:  # At least 1 second of data
            presence_ratio = sum(presence_history) / len(presence_history)
            is_present = presence_ratio > 0.3

            # State change detection
            if is_present != last_state:
                status = "PRESENT" if is_present else "ABSENT"
                print(f"[{time.strftime('%H:%M:%S')}] Status: {status}")
                last_state = is_present

            # Periodic status update
            elif now - last_print > 10:
                status = "present" if is_present else "absent"
                print(f"[{time.strftime('%H:%M:%S')}] Still {status} ({presence_ratio*100:.0f}% confidence)")
                last_print = now

except KeyboardInterrupt:
    pass
finally:
    sensor.stop()
    sensor.disconnect()
    print("\nPresence detection stopped")
