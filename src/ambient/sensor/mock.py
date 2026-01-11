"""Mock radar sensor for testing without hardware.

Generates realistic synthetic radar data including:
- Range profile with simulated targets
- Vital signs with breathing and heart rate patterns
- Detected points with noise

Enable with AMBIENT_MOCK_RADAR=true environment variable.
"""
from __future__ import annotations

import logging
import math
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from threading import Event, Thread

import numpy as np
from numpy.typing import NDArray

from .frame import (
    DetectedPoint,
    FrameHeader,
    RadarFrame,
    VitalSignsTLV,
)

logger = logging.getLogger(__name__)


def is_mock_enabled() -> bool:
    """Check if mock mode is enabled via environment variable."""
    return os.environ.get("AMBIENT_MOCK_RADAR", "").lower() in ("true", "1", "yes")


@dataclass
class MockConfig:
    """Configuration for mock radar data generation."""
    frame_rate_hz: float = 20.0
    num_range_bins: int = 256
    max_range_m: float = 5.0

    # Target simulation
    target_range_m: float = 1.5  # Primary target distance
    target_range_variation_m: float = 0.02  # Slight movement

    # Vital signs simulation
    heart_rate_bpm: float = 72.0
    heart_rate_variation_bpm: float = 5.0
    breathing_rate_bpm: float = 14.0
    breathing_rate_variation_bpm: float = 2.0

    # Signal quality
    snr_db: float = 15.0
    noise_floor_db: float = 30.0

    # Motion simulation (occasional motion artifacts)
    motion_probability: float = 0.02  # 2% chance per frame


class MockRadarSensor:
    """Mock radar sensor that generates synthetic data.

    Implements the same interface as RadarSensor for drop-in testing.
    Generates realistic vital signs data with breathing and heart rate.

    Usage:
        sensor = MockRadarSensor()
        sensor.connect()
        for frame in sensor.stream(max_frames=100):
            process(frame)
        sensor.disconnect()
    """

    def __init__(self, config: MockConfig | None = None):
        self._config = config or MockConfig()
        self._connected = False
        self._running = False
        self._frame_count = 0
        self._start_time = 0.0
        self._stop_event = Event()
        self._stream_thread: Thread | None = None
        self._callbacks: list[Callable[[RadarFrame], None]] = []

        # Phase accumulators for vital signs simulation
        self._breathing_phase = 0.0
        self._heart_phase = 0.0
        self._last_frame_time = 0.0

        # Add some randomness to vital signs
        self._hr_offset = np.random.uniform(-5, 5)
        self._rr_offset = np.random.uniform(-2, 2)

        logger.info("MockRadarSensor initialized (synthetic data mode)")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_running(self) -> bool:
        return self._running

    @staticmethod
    def find_ports() -> dict[str, str]:
        """Return mock ports."""
        return {"cli": "mock://cli", "data": "mock://data"}

    def connect(self) -> None:
        """Simulate connection."""
        if self._connected:
            return
        self._connected = True
        self._start_time = time.time()
        self._last_frame_time = self._start_time
        logger.info("MockRadarSensor connected (synthetic data mode)")

    def disconnect(self) -> None:
        """Simulate disconnection."""
        self.stop()
        self._connected = False
        logger.info("MockRadarSensor disconnected")

    def configure(self, config) -> None:
        """Accept configuration (no-op for mock)."""
        logger.info("MockRadarSensor: configuration accepted (ignored in mock mode)")

    def start(self) -> None:
        """Start generating frames."""
        if not self._connected:
            raise RuntimeError("Not connected")
        self._running = True
        self._frame_count = 0
        self._stop_event.clear()
        logger.info("MockRadarSensor started")

    def stop(self) -> None:
        """Stop generating frames."""
        self._running = False
        self._stop_event.set()
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=2.0)
        self._stream_thread = None
        logger.info("MockRadarSensor stopped")

    def get_version(self) -> str:
        """Return mock firmware version."""
        return "MockRadar v1.0.0 (Vital Signs Demo)\nmmWave SDK 3.5.0"

    def detect_firmware(self) -> dict:
        """Return mock firmware info."""
        return {
            "type": "vital_signs",
            "version": "1.0.0",
            "raw": self.get_version(),
        }

    def send_command(self, cmd: str, timeout: float = 0.1) -> str:
        """Simulate command response."""
        if cmd == "version":
            return self.get_version()
        elif cmd == "sensorStart":
            return "Done\n"
        elif cmd == "sensorStop":
            return "Done\n"
        return f"Mock response for: {cmd}\n"

    def read_frame(self, timeout: float = 1.0) -> RadarFrame | None:
        """Generate a synthetic radar frame."""
        if not self._running:
            return None

        # Calculate frame timing
        now = time.time()
        frame_period = 1.0 / self._config.frame_rate_hz
        elapsed = now - self._last_frame_time

        if elapsed < frame_period:
            time.sleep(frame_period - elapsed)
            now = time.time()

        self._last_frame_time = now
        self._frame_count += 1

        return self._generate_frame()

    def _generate_frame(self) -> RadarFrame:
        """Generate a complete synthetic radar frame."""
        now = time.time()
        dt = 1.0 / self._config.frame_rate_hz

        # Update phase accumulators
        hr_hz = (self._config.heart_rate_bpm + self._hr_offset) / 60.0
        rr_hz = (self._config.breathing_rate_bpm + self._rr_offset) / 60.0

        self._breathing_phase += 2 * math.pi * rr_hz * dt
        self._heart_phase += 2 * math.pi * hr_hz * dt

        # Generate range profile
        range_profile = self._generate_range_profile()

        # Generate detected points
        detected_points = self._generate_detected_points()

        # Generate vital signs
        vital_signs = self._generate_vital_signs()

        # Check for random motion event
        if np.random.random() < self._config.motion_probability:
            vital_signs = self._add_motion_artifact(vital_signs)

        # Create frame header
        header = FrameHeader(
            version=0x0305,
            packet_length=1024,
            platform=0x1443,
            frame_number=self._frame_count,
            time_cpu_cycles=int((now - self._start_time) * 200_000_000),
            num_detected_obj=len(detected_points),
            num_tlvs=3,
            _raw_data=bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07]),
        )

        return RadarFrame(
            header=header,
            detected_points=detected_points,
            range_profile=range_profile,
            vital_signs=vital_signs,
            timestamp=now,
        )

    def _generate_range_profile(self) -> NDArray[np.float32]:
        """Generate synthetic range profile with target peak."""
        num_bins = self._config.num_range_bins
        profile = np.random.normal(
            self._config.noise_floor_db,
            3.0,
            num_bins
        ).astype(np.float32)

        # Add target peak
        target_bin = int(
            self._config.target_range_m / self._config.max_range_m * num_bins
        )
        target_bin = max(0, min(num_bins - 1, target_bin))

        # Target with breathing modulation
        breathing_mod = 0.5 * math.sin(self._breathing_phase)
        peak_db = self._config.noise_floor_db + self._config.snr_db + breathing_mod

        # Add peak with some spread
        for offset in range(-2, 3):
            idx = target_bin + offset
            if 0 <= idx < num_bins:
                attenuation = 3.0 * abs(offset)
                profile[idx] = max(profile[idx], peak_db - attenuation)

        return profile

    def _generate_detected_points(self) -> list[DetectedPoint]:
        """Generate synthetic detected points."""
        # Primary target
        target_range = self._config.target_range_m
        target_range += self._config.target_range_variation_m * math.sin(
            self._breathing_phase * 0.5
        )

        points = [
            DetectedPoint(
                x=0.0,
                y=target_range,
                z=0.0,
                velocity=0.001 * math.cos(self._breathing_phase),
                snr=self._config.snr_db + np.random.normal(0, 1),
                noise=self._config.noise_floor_db,
            )
        ]

        # Occasionally add noise points
        if np.random.random() < 0.3:
            noise_range = np.random.uniform(0.5, 4.0)
            noise_angle = np.random.uniform(-0.5, 0.5)
            points.append(
                DetectedPoint(
                    x=noise_range * math.sin(noise_angle),
                    y=noise_range * math.cos(noise_angle),
                    z=np.random.uniform(-0.2, 0.2),
                    velocity=np.random.uniform(-0.1, 0.1),
                    snr=np.random.uniform(5, 10),
                    noise=self._config.noise_floor_db,
                )
            )

        return points

    def _generate_vital_signs(self) -> VitalSignsTLV:
        """Generate synthetic vital signs data."""
        # Calculate current rates with slight variation
        current_hr = self._config.heart_rate_bpm + self._hr_offset
        current_hr += np.random.normal(0, 0.5)

        current_rr = self._config.breathing_rate_bpm + self._rr_offset
        current_rr += np.random.normal(0, 0.2)

        # Generate waveforms
        waveform_size = 20
        t = np.linspace(0, 1, waveform_size)

        # Breathing waveform (sine wave)
        breathing_waveform = np.sin(
            2 * math.pi * t + self._breathing_phase
        ).astype(np.float32)
        breathing_waveform += np.random.normal(0, 0.05, waveform_size).astype(np.float32)

        # Heart waveform (faster oscillation with harmonics)
        heart_waveform = (
            0.7 * np.sin(2 * math.pi * t * 5 + self._heart_phase) +
            0.3 * np.sin(2 * math.pi * t * 10 + self._heart_phase * 2)
        ).astype(np.float32)
        heart_waveform += np.random.normal(0, 0.1, waveform_size).astype(np.float32)

        # Phase value (combined breathing and heart)
        unwrapped_phase = (
            0.8 * math.sin(self._breathing_phase) +
            0.2 * math.sin(self._heart_phase)
        )

        return VitalSignsTLV(
            range_bin_index=int(
                self._config.target_range_m / self._config.max_range_m * 256
            ),
            breathing_deviation=0.15 + np.random.uniform(-0.02, 0.02),
            heart_deviation=0.02 + np.random.uniform(-0.005, 0.005),
            breathing_rate=max(8, min(25, current_rr)),
            heart_rate=max(50, min(120, current_hr)),
            breathing_confidence=0.85 + np.random.uniform(-0.1, 0.1),
            heart_confidence=0.75 + np.random.uniform(-0.15, 0.1),
            breathing_waveform=breathing_waveform,
            heart_waveform=heart_waveform,
            unwrapped_phase=unwrapped_phase,
            patient_id=0,
        )

    def _add_motion_artifact(self, vitals: VitalSignsTLV) -> VitalSignsTLV:
        """Add motion artifact to vital signs (simulates patient movement)."""
        # During motion, confidence drops and readings become unreliable
        return VitalSignsTLV(
            range_bin_index=vitals.range_bin_index,
            breathing_deviation=0.005,  # Low deviation indicates motion/absence
            heart_deviation=0.0,
            breathing_rate=vitals.breathing_rate,
            heart_rate=vitals.heart_rate,
            breathing_confidence=0.2,
            heart_confidence=0.1,
            breathing_waveform=vitals.breathing_waveform * 0.1,
            heart_waveform=vitals.heart_waveform * 0.1,
            unwrapped_phase=vitals.unwrapped_phase,
            patient_id=vitals.patient_id,
        )

    def stream(
        self, max_frames: int | None = None, duration: float | None = None
    ) -> Iterator[RadarFrame]:
        """Generator that yields synthetic frames."""
        if not self._connected:
            raise RuntimeError("Not connected")

        start = time.time()
        count = 0

        while self._running:
            frame = self.read_frame(timeout=0.1)
            if frame:
                yield frame
                count += 1

                if max_frames and count >= max_frames:
                    break

            if duration and (time.time() - start) >= duration:
                break

    def stream_async(
        self,
        callback: Callable[[RadarFrame], None],
        max_frames: int | None = None,
    ):
        """Start streaming in a background thread."""
        if self._stream_thread and self._stream_thread.is_alive():
            raise RuntimeError("Already streaming")

        self._callbacks = [callback] if callback is not None else []
        self._stop_event.clear()

        def run():
            count = 0
            while not self._stop_event.is_set() and self._running:
                frame = self.read_frame(timeout=0.1)
                if frame:
                    for cb in self._callbacks:
                        try:
                            cb(frame)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

                    count += 1
                    if max_frames and count >= max_frames:
                        break

        self._stream_thread = Thread(target=run, daemon=True)
        self._stream_thread.start()

    def set_callbacks(
        self,
        on_disconnect: Callable[[], None] | None = None,
        on_reconnect: Callable[[], None] | None = None,
    ):
        """Set callbacks (no-op for mock, connection is always stable)."""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.disconnect()


def get_sensor(mock: bool | None = None):
    """Get appropriate sensor based on configuration.

    Args:
        mock: Force mock mode if True, force real if False,
              check environment if None.

    Returns:
        MockRadarSensor if mock mode, RadarSensor otherwise.
    """
    use_mock = mock if mock is not None else is_mock_enabled()

    if use_mock:
        logger.info("Using MockRadarSensor (AMBIENT_MOCK_RADAR=true)")
        return MockRadarSensor()
    else:
        from .radar import RadarSensor
        return RadarSensor()
