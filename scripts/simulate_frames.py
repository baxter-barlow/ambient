#!/usr/bin/env python3
"""Simulate radar frame ingestion for load testing without hardware.

This script generates synthetic radar frames and pushes them through
the processing pipeline and WebSocket broadcast system. Useful for:
- Stress testing the acquisition loop
- Testing backpressure and drop policies
- Profiling performance under load
- Testing dashboard behavior with high frame rates

Usage:
	python scripts/simulate_frames.py --fps 20 --duration 60
	python scripts/simulate_frames.py --config load_profiles/stress.json
	python scripts/simulate_frames.py --fps 100 --include-doppler

Environment:
	AMBIENT_API_HOST: API host (default: localhost)
	AMBIENT_API_PORT: API port (default: 8000)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ambient.processing.pipeline import ProcessingPipeline
from ambient.sensor.frame import DetectedPoint, FrameHeader, RadarFrame
from ambient.vitals.extractor import VitalsExtractor, VitalSigns

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class LoadProfile:
	"""Configuration for load testing."""

	fps: float = 20.0  # Target frames per second
	duration_seconds: float = 60.0  # Test duration
	range_bins: int = 256  # Number of range bins
	include_doppler: bool = False  # Include range-doppler heatmap
	doppler_size: int = 64  # Doppler heatmap size (doppler_size x range_bins)
	include_points: bool = True  # Include detected points
	max_points: int = 5  # Maximum detected points per frame
	include_vitals: bool = True  # Generate vitals estimates
	vitals_rate_hz: float = 1.0  # Vitals update rate
	broadcast_to_ws: bool = True  # Broadcast to WebSocket
	ws_url: str = "ws://localhost:8000/ws/sensor"
	simulate_motion: bool = False  # Simulate motion events
	motion_probability: float = 0.1  # Probability of motion per frame
	jitter_percent: float = 10.0  # Frame timing jitter (0-100%)

	@classmethod
	def from_json(cls, path: str | Path) -> LoadProfile:
		"""Load profile from JSON file."""
		with open(path) as f:
			data = json.load(f)
		return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

	def to_json(self) -> str:
		"""Serialize to JSON."""
		return json.dumps(self.__dict__, indent=2)


@dataclass
class SimulationStats:
	"""Statistics from simulation run."""

	frames_generated: int = 0
	frames_processed: int = 0
	frames_broadcast: int = 0
	vitals_generated: int = 0
	errors: int = 0
	start_time: float = 0.0
	end_time: float = 0.0
	frame_times: list[float] = field(default_factory=list)
	broadcast_times: list[float] = field(default_factory=list)

	@property
	def duration(self) -> float:
		return self.end_time - self.start_time

	@property
	def actual_fps(self) -> float:
		if self.duration <= 0:
			return 0.0
		return self.frames_generated / self.duration

	@property
	def avg_frame_time_ms(self) -> float:
		if not self.frame_times:
			return 0.0
		return sum(self.frame_times) / len(self.frame_times) * 1000

	@property
	def p95_frame_time_ms(self) -> float:
		if not self.frame_times:
			return 0.0
		sorted_times = sorted(self.frame_times)
		idx = int(len(sorted_times) * 0.95)
		return sorted_times[min(idx, len(sorted_times) - 1)] * 1000

	def summary(self) -> dict[str, Any]:
		return {
			"frames_generated": self.frames_generated,
			"frames_processed": self.frames_processed,
			"frames_broadcast": self.frames_broadcast,
			"vitals_generated": self.vitals_generated,
			"errors": self.errors,
			"duration_seconds": round(self.duration, 2),
			"actual_fps": round(self.actual_fps, 2),
			"avg_frame_time_ms": round(self.avg_frame_time_ms, 3),
			"p95_frame_time_ms": round(self.p95_frame_time_ms, 3),
		}


class FrameGenerator:
	"""Generates synthetic radar frames with realistic data patterns."""

	def __init__(self, profile: LoadProfile):
		self.profile = profile
		self._frame_number = 0
		self._phase_offset = 0.0
		self._target_range_bin = 50  # Simulated subject at ~1m

	def generate(self) -> RadarFrame:
		"""Generate a single synthetic frame."""
		self._frame_number += 1
		timestamp = time.time()

		# Create header
		header = FrameHeader(
			version=0x0102,
			packet_length=1024,
			platform=0x6843,
			frame_number=self._frame_number,
			time_cpu_cycles=int(timestamp * 1e6) % (2**32),
			num_detected_obj=random.randint(0, self.profile.max_points),
			num_tlvs=3,
		)

		# Generate range profile with target peak
		range_profile = self._generate_range_profile()

		# Generate range-doppler heatmap if enabled
		range_doppler = None
		if self.profile.include_doppler:
			range_doppler = self._generate_range_doppler()

		# Generate detected points
		detected_points = []
		if self.profile.include_points:
			detected_points = self._generate_points(header.num_detected_obj)

		return RadarFrame(
			header=header,
			detected_points=detected_points,
			range_profile=range_profile,
			range_doppler_heatmap=range_doppler,
			timestamp=timestamp,
		)

	def _generate_range_profile(self) -> np.ndarray:
		"""Generate range profile with target at known bin."""
		# Base noise floor
		profile = np.random.rand(self.profile.range_bins).astype(np.float32) * 10

		# Add target peak with breathing modulation
		breathing_freq = 0.25  # 15 BPM
		heart_freq = 1.0  # 60 BPM
		t = time.time()

		# Phase modulation from breathing and heartbeat
		breathing = 2.0 * np.sin(2 * np.pi * breathing_freq * t)
		heartbeat = 0.3 * np.sin(2 * np.pi * heart_freq * t)
		self._phase_offset = breathing + heartbeat

		# Target peak
		target_amplitude = 80 + 10 * np.sin(2 * np.pi * 0.1 * t)  # Slow variation
		profile[self._target_range_bin] = target_amplitude
		profile[self._target_range_bin - 1] = target_amplitude * 0.5
		profile[self._target_range_bin + 1] = target_amplitude * 0.5

		return profile

	def _generate_range_doppler(self) -> np.ndarray:
		"""Generate range-doppler heatmap."""
		heatmap = np.random.rand(
			self.profile.doppler_size, self.profile.range_bins
		).astype(np.float32) * 5

		# Add stationary target (zero Doppler)
		center_doppler = self.profile.doppler_size // 2
		heatmap[center_doppler, self._target_range_bin] = 50
		heatmap[center_doppler - 1 : center_doppler + 2, self._target_range_bin] = 30

		return heatmap

	def _generate_points(self, num_points: int) -> list[DetectedPoint]:
		"""Generate detected points around target location."""
		points = []
		for i in range(num_points):
			# Points clustered around target
			x = 0.1 + random.gauss(0, 0.05)  # ~1m range
			y = 1.0 + random.gauss(0, 0.1)
			z = random.gauss(0, 0.02)
			velocity = random.gauss(0, 0.01)  # Small velocities for breathing
			snr = random.uniform(10, 30)
			points.append(DetectedPoint(x=x, y=y, z=z, velocity=velocity, snr=snr))
		return points


class Simulator:
	"""Main simulation runner."""

	def __init__(self, profile: LoadProfile):
		self.profile = profile
		self.generator = FrameGenerator(profile)
		self.pipeline = ProcessingPipeline()
		self.extractor = VitalsExtractor()
		self.stats = SimulationStats()
		self._ws_client = None
		self._running = False

	async def run(self) -> SimulationStats:
		"""Run the simulation."""
		logger.info(f"Starting simulation: {self.profile.fps} FPS for {self.profile.duration_seconds}s")
		logger.info(f"Profile: doppler={self.profile.include_doppler}, points={self.profile.include_points}")

		self._running = True
		self.stats = SimulationStats()
		self.stats.start_time = time.time()

		frame_interval = 1.0 / self.profile.fps
		end_time = self.stats.start_time + self.profile.duration_seconds
		last_vitals_time = 0.0
		vitals_interval = 1.0 / self.profile.vitals_rate_hz

		# Connect to WebSocket if enabled
		if self.profile.broadcast_to_ws:
			await self._connect_ws()

		try:
			while self._running and time.time() < end_time:
				frame_start = time.perf_counter()

				# Generate frame
				frame = self.generator.generate()
				self.stats.frames_generated += 1

				# Process frame
				try:
					processed = self.pipeline.process(frame)
					self.stats.frames_processed += 1
				except Exception as e:
					logger.error(f"Processing error: {e}")
					self.stats.errors += 1
					continue

				# Generate vitals at lower rate
				vitals = None
				now = time.time()
				if self.profile.include_vitals and (now - last_vitals_time) >= vitals_interval:
					try:
						vitals = self.extractor.process_frame(processed)
						self.stats.vitals_generated += 1
						last_vitals_time = now
					except Exception as e:
						logger.error(f"Vitals error: {e}")

				# Broadcast if connected
				if self._ws_client:
					broadcast_start = time.perf_counter()
					try:
						await self._broadcast_frame(frame, processed, vitals)
						self.stats.frames_broadcast += 1
						self.stats.broadcast_times.append(time.perf_counter() - broadcast_start)
					except Exception as e:
						logger.error(f"Broadcast error: {e}")
						self.stats.errors += 1

				# Record timing
				frame_time = time.perf_counter() - frame_start
				self.stats.frame_times.append(frame_time)

				# Apply jitter and sleep
				jitter = random.uniform(-1, 1) * (self.profile.jitter_percent / 100)
				sleep_time = max(0, frame_interval - frame_time + (frame_interval * jitter))
				if sleep_time > 0:
					await asyncio.sleep(sleep_time)

				# Log progress every 5 seconds
				if self.stats.frames_generated % int(self.profile.fps * 5) == 0:
					elapsed = time.time() - self.stats.start_time
					logger.info(
						f"Progress: {self.stats.frames_generated} frames, "
						f"{elapsed:.1f}s elapsed, "
						f"{self.stats.actual_fps:.1f} FPS"
					)

		except asyncio.CancelledError:
			logger.info("Simulation cancelled")
		finally:
			self._running = False
			self.stats.end_time = time.time()
			await self._disconnect_ws()

		return self.stats

	async def _connect_ws(self):
		"""Connect to WebSocket for broadcasting."""
		try:
			import websockets
			self._ws_client = await websockets.connect(self.profile.ws_url)
			logger.info(f"Connected to WebSocket: {self.profile.ws_url}")
		except Exception as e:
			logger.warning(f"Could not connect to WebSocket: {e}")
			self._ws_client = None

	async def _disconnect_ws(self):
		"""Disconnect WebSocket."""
		if self._ws_client:
			try:
				await self._ws_client.close()
			except Exception:
				pass
			self._ws_client = None

	async def _broadcast_frame(self, frame: RadarFrame, processed, vitals: VitalSigns | None):
		"""Broadcast frame data via WebSocket."""
		if not self._ws_client:
			return

		# Build frame message
		frame_data = {
			"type": "sensor_frame",
			"timestamp": time.time(),
			"payload": {
				"frame_number": frame.header.frame_number if frame.header else 0,
				"timestamp": frame.timestamp,
				"range_profile": frame.range_profile.tolist() if frame.range_profile is not None else [],
				"detected_points": [
					{"x": p.x, "y": p.y, "z": p.z, "velocity": p.velocity, "snr": p.snr}
					for p in frame.detected_points
				],
			},
		}

		if self.profile.include_doppler and frame.range_doppler_heatmap is not None:
			frame_data["payload"]["range_doppler"] = frame.range_doppler_heatmap.tolist()

		if processed and processed.phase_data is not None:
			phase = processed.phase_data
			if hasattr(phase, "ndim") and phase.ndim > 0:
				frame_data["payload"]["phase"] = float(phase[0]) if phase.size > 0 else 0.0
			else:
				frame_data["payload"]["phase"] = float(phase)

		await self._ws_client.send(json.dumps(frame_data))

		# Broadcast vitals if available
		if vitals:
			vitals_data = {
				"type": "vitals",
				"timestamp": time.time(),
				"payload": {
					"heart_rate_bpm": vitals.heart_rate_bpm,
					"heart_rate_confidence": vitals.heart_rate_confidence,
					"respiratory_rate_bpm": vitals.respiratory_rate_bpm,
					"respiratory_rate_confidence": vitals.respiratory_rate_confidence,
					"signal_quality": vitals.signal_quality,
					"motion_detected": vitals.motion_detected,
					"source": "simulated",
				},
			}
			await self._ws_client.send(json.dumps(vitals_data))

	def stop(self):
		"""Stop the simulation."""
		self._running = False


def create_example_profiles():
	"""Create example load profile configs."""
	profiles_dir = Path(__file__).parent.parent / "load_profiles"
	profiles_dir.mkdir(exist_ok=True)

	# Standard profile
	standard = LoadProfile(fps=20, duration_seconds=60)
	(profiles_dir / "standard.json").write_text(standard.to_json())

	# Stress profile
	stress = LoadProfile(
		fps=100,
		duration_seconds=30,
		include_doppler=True,
		doppler_size=64,
		jitter_percent=20,
	)
	(profiles_dir / "stress.json").write_text(stress.to_json())

	# Light profile
	light = LoadProfile(
		fps=10,
		duration_seconds=120,
		include_doppler=False,
		include_points=False,
	)
	(profiles_dir / "light.json").write_text(light.to_json())

	# Sustained profile
	sustained = LoadProfile(
		fps=20,
		duration_seconds=300,  # 5 minutes
		include_doppler=True,
	)
	(profiles_dir / "sustained.json").write_text(sustained.to_json())

	logger.info(f"Created example profiles in {profiles_dir}")


async def main():
	parser = argparse.ArgumentParser(description="Simulate radar frames for load testing")
	parser.add_argument("--fps", type=float, default=20, help="Frames per second")
	parser.add_argument("--duration", type=float, default=60, help="Duration in seconds")
	parser.add_argument("--config", type=str, help="Load profile JSON file")
	parser.add_argument("--include-doppler", action="store_true", help="Include range-doppler")
	parser.add_argument("--no-ws", action="store_true", help="Disable WebSocket broadcast")
	parser.add_argument("--ws-url", type=str, default="ws://localhost:8000/ws/sensor")
	parser.add_argument("--create-profiles", action="store_true", help="Create example profiles")
	parser.add_argument("--output", type=str, help="Output stats to JSON file")

	args = parser.parse_args()

	if args.create_profiles:
		create_example_profiles()
		return

	# Load or create profile
	if args.config:
		profile = LoadProfile.from_json(args.config)
	else:
		profile = LoadProfile(
			fps=args.fps,
			duration_seconds=args.duration,
			include_doppler=args.include_doppler,
			broadcast_to_ws=not args.no_ws,
			ws_url=args.ws_url,
		)

	# Run simulation
	simulator = Simulator(profile)
	stats = await simulator.run()

	# Print results
	logger.info("Simulation complete")
	summary = stats.summary()
	print("\n" + "=" * 50)
	print("SIMULATION RESULTS")
	print("=" * 50)
	for key, value in summary.items():
		print(f"  {key}: {value}")
	print("=" * 50)

	# Save to file if requested
	if args.output:
		Path(args.output).write_text(json.dumps(summary, indent=2))
		logger.info(f"Stats written to {args.output}")


if __name__ == "__main__":
	asyncio.run(main())
