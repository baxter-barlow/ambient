#!/usr/bin/env python3
"""Replay recorded HDF5/Parquet files through the processing pipeline.

This script reads stored recordings and replays them through the
processing pipeline and WebSocket broadcast system. Useful for:
- Testing processing changes on real data
- Debugging issues from recorded sessions
- Demonstrating the system without hardware
- Benchmarking processing performance

Usage:
	python scripts/replay_recording.py data/session_20240101_120000.h5
	python scripts/replay_recording.py data/vitals.parquet --speed 2.0
	python scripts/replay_recording.py data/session.h5 --no-ws --validate

Environment:
	AMBIENT_API_HOST: API host (default: localhost)
	AMBIENT_API_PORT: API port (default: 8000)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ambient.storage.reader import DataReader, StoredFrame
from ambient.storage.writer import SCHEMA_VERSION
from ambient.processing.pipeline import ProcessingPipeline
from ambient.vitals.extractor import VitalsExtractor
from ambient.sensor.frame import DetectedPoint, FrameHeader, RadarFrame

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ReplayStats:
	"""Statistics from replay session."""

	frames_read: int = 0
	frames_processed: int = 0
	frames_broadcast: int = 0
	vitals_read: int = 0
	errors: int = 0
	start_time: float = 0.0
	end_time: float = 0.0
	processing_times: list[float] = field(default_factory=list)
	recording_duration: float = 0.0

	@property
	def duration(self) -> float:
		return self.end_time - self.start_time

	@property
	def speed_ratio(self) -> float:
		if self.duration <= 0 or self.recording_duration <= 0:
			return 0.0
		return self.recording_duration / self.duration

	@property
	def avg_processing_ms(self) -> float:
		if not self.processing_times:
			return 0.0
		return sum(self.processing_times) / len(self.processing_times) * 1000

	def summary(self) -> dict[str, Any]:
		return {
			"frames_read": self.frames_read,
			"frames_processed": self.frames_processed,
			"frames_broadcast": self.frames_broadcast,
			"vitals_read": self.vitals_read,
			"errors": self.errors,
			"replay_duration_seconds": round(self.duration, 2),
			"recording_duration_seconds": round(self.recording_duration, 2),
			"speed_ratio": round(self.speed_ratio, 2),
			"avg_processing_ms": round(self.avg_processing_ms, 3),
		}


def stored_frame_to_radar_frame(stored: StoredFrame) -> RadarFrame:
	"""Convert StoredFrame to RadarFrame for processing."""
	header = FrameHeader(
		version=0x0102,
		packet_length=1024,
		platform=0x6843,
		frame_number=stored.frame_number,
		time_cpu_cycles=int(stored.timestamp * 1e6) % (2**32),
		num_detected_obj=len(stored.detected_points) if stored.detected_points else 0,
		num_tlvs=2,
	)

	detected_points = []
	if stored.detected_points:
		for pt in stored.detected_points:
			# pt is tuple (x, y, z, velocity, snr) or similar
			if len(pt) >= 4:
				detected_points.append(DetectedPoint(
					x=float(pt[0]),
					y=float(pt[1]),
					z=float(pt[2]),
					velocity=float(pt[3]),
					snr=float(pt[4]) if len(pt) > 4 else 0.0,
				))

	return RadarFrame(
		header=header,
		detected_points=detected_points,
		range_profile=stored.range_profile,
		timestamp=stored.timestamp,
		raw_data=stored.raw_data or b"",
	)


class Replayer:
	"""Replays recorded data through the pipeline."""

	def __init__(
		self,
		path: Path,
		speed: float = 1.0,
		broadcast: bool = True,
		ws_url: str = "ws://localhost:8000/ws/sensor",
		validate_only: bool = False,
	):
		self.path = path
		self.speed = speed
		self.broadcast = broadcast
		self.ws_url = ws_url
		self.validate_only = validate_only

		self.reader = DataReader(path)
		self.pipeline = ProcessingPipeline()
		self.extractor = VitalsExtractor()
		self.stats = ReplayStats()
		self._ws_client = None
		self._running = False

	async def run(self) -> ReplayStats:
		"""Run the replay."""
		logger.info(f"Replaying: {self.path}")
		logger.info(f"Metadata: {self.reader.metadata}")

		self._running = True
		self.stats = ReplayStats()
		self.stats.start_time = time.time()

		# Get recording time range
		try:
			time_range = self.reader.get_time_range()
			self.stats.recording_duration = time_range[1] - time_range[0]
			logger.info(f"Recording duration: {self.stats.recording_duration:.1f}s")
		except Exception:
			pass

		if self.validate_only:
			return await self._validate()

		# Connect to WebSocket if enabled
		if self.broadcast:
			await self._connect_ws()

		try:
			if self.reader.num_frames > 0:
				await self._replay_frames()
			else:
				await self._replay_vitals_only()
		except asyncio.CancelledError:
			logger.info("Replay cancelled")
		finally:
			self._running = False
			self.stats.end_time = time.time()
			await self._disconnect_ws()
			self.reader.close()

		return self.stats

	async def _validate(self) -> ReplayStats:
		"""Validate recording without processing."""
		logger.info("Validating recording...")

		errors = []

		# Check metadata
		meta = self.reader.metadata
		if meta.get("format") == "hdf5":
			if not meta.get("session_id"):
				errors.append("Missing session_id")
			if not meta.get("start_time"):
				errors.append("Missing start_time")

		# Check frames
		frame_count = 0
		for frame in self.reader.iter_frames():
			frame_count += 1
			if frame.timestamp <= 0:
				errors.append(f"Frame {frame_count}: invalid timestamp")
			self.stats.frames_read += 1

		# Check vitals
		try:
			df = self.reader.get_vitals_dataframe()
			self.stats.vitals_read = len(df)
			required_cols = ["timestamp", "heart_rate", "respiratory_rate"]
			for col in required_cols:
				if col not in df.columns:
					errors.append(f"Missing column: {col}")
		except Exception as e:
			errors.append(f"Vitals read error: {e}")

		self.stats.end_time = time.time()
		self.stats.errors = len(errors)

		if errors:
			logger.error("Validation failed:")
			for err in errors:
				logger.error(f"  - {err}")
		else:
			logger.info("Validation passed")

		return self.stats

	async def _replay_frames(self):
		"""Replay HDF5 frames."""
		logger.info(f"Replaying {self.reader.num_frames} frames at {self.speed}x speed")

		prev_timestamp = None
		for stored in self.reader.iter_frames():
			if not self._running:
				break

			self.stats.frames_read += 1

			# Convert to RadarFrame
			frame = stored_frame_to_radar_frame(stored)

			# Calculate delay based on timestamp delta
			if prev_timestamp is not None and self.speed > 0:
				delta = frame.timestamp - prev_timestamp
				sleep_time = delta / self.speed
				if sleep_time > 0:
					await asyncio.sleep(sleep_time)
			prev_timestamp = frame.timestamp

			# Process frame
			proc_start = time.perf_counter()
			try:
				processed = self.pipeline.process(frame)
				self.stats.frames_processed += 1
				self.stats.processing_times.append(time.perf_counter() - proc_start)
			except Exception as e:
				logger.error(f"Processing error frame {frame.header.frame_number}: {e}")
				self.stats.errors += 1
				continue

			# Broadcast if connected
			if self._ws_client:
				try:
					await self._broadcast_frame(frame, processed)
					self.stats.frames_broadcast += 1
				except Exception as e:
					logger.error(f"Broadcast error: {e}")
					self.stats.errors += 1

			# Log progress
			if self.stats.frames_read % 100 == 0:
				elapsed = time.time() - self.stats.start_time
				logger.info(
					f"Progress: {self.stats.frames_read}/{self.reader.num_frames} "
					f"frames, {elapsed:.1f}s elapsed"
				)

	async def _replay_vitals_only(self):
		"""Replay Parquet vitals-only recording."""
		logger.info("Replaying vitals-only recording")

		df = self.reader.get_vitals_dataframe()
		if df.empty:
			logger.warning("No vitals data found")
			return

		prev_timestamp = None
		for _, row in df.iterrows():
			if not self._running:
				break

			self.stats.vitals_read += 1
			timestamp = row.get("timestamp", 0)

			# Calculate delay
			if prev_timestamp is not None and self.speed > 0:
				delta = timestamp - prev_timestamp
				sleep_time = delta / self.speed
				if sleep_time > 0:
					await asyncio.sleep(sleep_time)
			prev_timestamp = timestamp

			# Broadcast if connected
			if self._ws_client:
				try:
					await self._broadcast_vitals(row.to_dict())
					self.stats.frames_broadcast += 1
				except Exception as e:
					logger.error(f"Broadcast error: {e}")
					self.stats.errors += 1

			if self.stats.vitals_read % 50 == 0:
				logger.info(f"Progress: {self.stats.vitals_read}/{len(df)} vitals")

	async def _connect_ws(self):
		"""Connect to WebSocket."""
		try:
			import websockets
			self._ws_client = await websockets.connect(self.ws_url)
			logger.info(f"Connected to WebSocket: {self.ws_url}")
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

	async def _broadcast_frame(self, frame: RadarFrame, processed):
		"""Broadcast frame via WebSocket."""
		if not self._ws_client:
			return

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

		if processed and processed.phase_data is not None:
			phase = processed.phase_data
			if hasattr(phase, "ndim") and phase.ndim > 0:
				frame_data["payload"]["phase"] = float(phase[0]) if phase.size > 0 else 0.0
			else:
				frame_data["payload"]["phase"] = float(phase)

		await self._ws_client.send(json.dumps(frame_data))

	async def _broadcast_vitals(self, vitals: dict):
		"""Broadcast vitals via WebSocket."""
		if not self._ws_client:
			return

		# Map column names
		vitals_data = {
			"type": "vitals",
			"timestamp": time.time(),
			"payload": {
				"heart_rate_bpm": vitals.get("heart_rate") or vitals.get("heart_rate_bpm"),
				"heart_rate_confidence": vitals.get("hr_confidence", 0.8),
				"respiratory_rate_bpm": vitals.get("respiratory_rate") or vitals.get("respiratory_rate_bpm"),
				"respiratory_rate_confidence": vitals.get("rr_confidence", 0.8),
				"signal_quality": vitals.get("signal_quality", 0.7),
				"motion_detected": vitals.get("motion_detected", False),
				"source": "replay",
				"hr_snr_db": vitals.get("hr_snr_db", 0),
				"rr_snr_db": vitals.get("rr_snr_db", 0),
				"phase_stability": vitals.get("phase_stability", 0),
			},
		}

		await self._ws_client.send(json.dumps(vitals_data))

	def stop(self):
		"""Stop replay."""
		self._running = False


def validate_recording(path: Path) -> dict[str, Any]:
	"""Quick validation of a recording file."""
	result = {
		"path": str(path),
		"exists": path.exists(),
		"valid": False,
		"errors": [],
		"warnings": [],
		"info": {},
	}

	if not path.exists():
		result["errors"].append("File not found")
		return result

	try:
		reader = DataReader(path)
		meta = reader.metadata
		result["info"]["metadata"] = meta
		result["info"]["num_frames"] = reader.num_frames

		# Check schema version
		schema_version = meta.get("schema_version", "unknown")
		if schema_version != SCHEMA_VERSION:
			result["warnings"].append(
				f"Schema version mismatch: file={schema_version}, current={SCHEMA_VERSION}"
			)

		# Check time range
		try:
			time_range = reader.get_time_range()
			result["info"]["time_range"] = time_range
			result["info"]["duration_seconds"] = time_range[1] - time_range[0]
		except Exception:
			pass

		# Check vitals
		try:
			df = reader.get_vitals_dataframe()
			result["info"]["vitals_count"] = len(df)
			if len(df) > 0:
				result["info"]["vitals_columns"] = list(df.columns)
		except Exception as e:
			result["warnings"].append(f"Could not read vitals: {e}")

		reader.close()
		result["valid"] = len(result["errors"]) == 0

	except Exception as e:
		result["errors"].append(str(e))

	return result


async def main():
	parser = argparse.ArgumentParser(description="Replay recorded data through pipeline")
	parser.add_argument("path", type=Path, help="Recording file (HDF5 or Parquet)")
	parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier")
	parser.add_argument("--no-ws", action="store_true", help="Disable WebSocket broadcast")
	parser.add_argument("--ws-url", type=str, default="ws://localhost:8000/ws/sensor")
	parser.add_argument("--validate", action="store_true", help="Validate only, no replay")
	parser.add_argument("--output", type=str, help="Output stats to JSON file")

	args = parser.parse_args()

	if not args.path.exists():
		logger.error(f"File not found: {args.path}")
		sys.exit(1)

	if args.validate:
		result = validate_recording(args.path)
		print(json.dumps(result, indent=2, default=str))
		sys.exit(0 if result["valid"] else 1)

	replayer = Replayer(
		path=args.path,
		speed=args.speed,
		broadcast=not args.no_ws,
		ws_url=args.ws_url,
	)

	stats = await replayer.run()

	# Print results
	logger.info("Replay complete")
	summary = stats.summary()
	print("\n" + "=" * 50)
	print("REPLAY RESULTS")
	print("=" * 50)
	for key, value in summary.items():
		print(f"  {key}: {value}")
	print("=" * 50)

	if args.output:
		Path(args.output).write_text(json.dumps(summary, indent=2))
		logger.info(f"Stats written to {args.output}")


if __name__ == "__main__":
	asyncio.run(main())
