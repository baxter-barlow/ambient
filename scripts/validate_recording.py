#!/usr/bin/env python3
"""Recording validation script with schema and integrity checks.

Validates HDF5 and Parquet recording files for:
- Schema compliance
- Timestamp monotonicity and gaps
- Data type and range validation
- Frame sequence integrity
- Metadata presence

Usage:
	python scripts/validate_recording.py data/recording.h5
	python scripts/validate_recording.py data/vitals.parquet --verbose
	python scripts/validate_recording.py data/*.h5 --summary
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# Schema version expected
EXPECTED_SCHEMA_VERSION = "1.1.0"

# Expected HDF5 vitals datasets
REQUIRED_VITALS_DATASETS = {
	"timestamp",
	"heart_rate",
	"respiratory_rate",
	"hr_confidence",
	"rr_confidence",
	"signal_quality",
	"motion_detected",
}

OPTIONAL_VITALS_DATASETS = {
	"hr_snr_db",
	"rr_snr_db",
	"phase_stability",
	"unwrapped_phase",
	"source",
}

# Expected Parquet columns
REQUIRED_PARQUET_COLUMNS = {
	"timestamp",
	"heart_rate_bpm",
	"respiratory_rate_bpm",
	"hr_confidence",
	"rr_confidence",
	"signal_quality",
	"motion_detected",
}

# Valid data ranges
DATA_RANGES = {
	"heart_rate": (20.0, 250.0),
	"heart_rate_bpm": (20.0, 250.0),
	"respiratory_rate": (4.0, 60.0),
	"respiratory_rate_bpm": (4.0, 60.0),
	"hr_confidence": (0.0, 1.0),
	"rr_confidence": (0.0, 1.0),
	"signal_quality": (0.0, 1.0),
}


@dataclass
class ValidationIssue:
	"""A single validation issue found in the recording."""

	level: str  # error, warning, info
	category: str  # schema, data, timestamp, sequence, metadata
	message: str
	details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
	"""Complete validation result for a recording file."""

	path: Path
	format: str  # hdf5, parquet
	valid: bool = True
	issues: list[ValidationIssue] = field(default_factory=list)

	# Metadata
	schema_version: str | None = None
	session_id: str | None = None
	start_time: str | None = None
	end_time: str | None = None
	firmware_type: str | None = None

	# Stats
	num_frames: int = 0
	num_vitals: int = 0
	duration_seconds: float = 0.0
	timestamp_range: tuple[float, float] = (0.0, 0.0)

	def add_error(self, category: str, message: str, **details: Any) -> None:
		self.issues.append(ValidationIssue("error", category, message, details))
		self.valid = False

	def add_warning(self, category: str, message: str, **details: Any) -> None:
		self.issues.append(ValidationIssue("warning", category, message, details))

	def add_info(self, category: str, message: str, **details: Any) -> None:
		self.issues.append(ValidationIssue("info", category, message, details))

	@property
	def error_count(self) -> int:
		return sum(1 for i in self.issues if i.level == "error")

	@property
	def warning_count(self) -> int:
		return sum(1 for i in self.issues if i.level == "warning")

	def to_dict(self) -> dict[str, Any]:
		return {
			"path": str(self.path),
			"format": self.format,
			"valid": self.valid,
			"errors": self.error_count,
			"warnings": self.warning_count,
			"schema_version": self.schema_version,
			"session_id": self.session_id,
			"num_frames": self.num_frames,
			"num_vitals": self.num_vitals,
			"duration_seconds": round(self.duration_seconds, 2),
			"issues": [
				{
					"level": i.level,
					"category": i.category,
					"message": i.message,
					**i.details,
				}
				for i in self.issues
			],
		}


class RecordingValidator:
	"""Validates recording files for integrity and schema compliance."""

	def __init__(self, verbose: bool = False) -> None:
		self.verbose = verbose

	def validate(self, path: Path) -> ValidationResult:
		"""Validate a recording file."""
		if not path.exists():
			result = ValidationResult(path=path, format="unknown")
			result.add_error("file", f"File not found: {path}")
			return result

		suffix = path.suffix.lower()
		if suffix in (".h5", ".hdf5"):
			return self._validate_hdf5(path)
		elif suffix in (".parquet", ".pq"):
			return self._validate_parquet(path)
		else:
			result = ValidationResult(path=path, format="unknown")
			result.add_error("file", f"Unsupported format: {suffix}")
			return result

	def _validate_hdf5(self, path: Path) -> ValidationResult:
		"""Validate HDF5 recording file."""
		result = ValidationResult(path=path, format="hdf5")

		try:
			with h5py.File(path, "r") as f:
				# Validate metadata
				self._validate_hdf5_metadata(f, result)

				# Validate frames group
				self._validate_hdf5_frames(f, result)

				# Validate vitals group
				self._validate_hdf5_vitals(f, result)

		except OSError as e:
			result.add_error("file", f"Cannot open HDF5 file: {e}")

		return result

	def _validate_hdf5_metadata(self, f: h5py.File, result: ValidationResult) -> None:
		"""Validate HDF5 file metadata."""
		attrs = dict(f.attrs)

		# Check schema version
		schema_version = attrs.get("schema_version", "")
		result.schema_version = schema_version if schema_version else None
		if not schema_version:
			result.add_warning("metadata", "Missing schema_version attribute")
		elif schema_version != EXPECTED_SCHEMA_VERSION:
			result.add_info(
				"metadata",
				f"Schema version mismatch: expected {EXPECTED_SCHEMA_VERSION}, got {schema_version}",
			)

		# Check required metadata
		result.session_id = attrs.get("session_id", "")
		if not result.session_id:
			result.add_warning("metadata", "Missing session_id")

		result.start_time = attrs.get("start_time", "")
		if not result.start_time:
			result.add_warning("metadata", "Missing start_time")

		result.end_time = attrs.get("end_time", "")
		result.firmware_type = attrs.get("firmware_type", "unknown")

		# Get counts from metadata
		result.num_frames = attrs.get("total_frames", 0)
		result.num_vitals = attrs.get("total_vitals", 0)

	def _validate_hdf5_frames(self, f: h5py.File, result: ValidationResult) -> None:
		"""Validate HDF5 frames group."""
		if "frames" not in f:
			result.add_info("schema", "No frames group present")
			return

		frames_group = f["frames"]
		frame_names = sorted(frames_group.keys())
		actual_frame_count = len(frame_names)

		# Check frame count matches metadata
		if result.num_frames != actual_frame_count:
			result.add_warning(
				"data",
				f"Frame count mismatch: metadata says {result.num_frames}, found {actual_frame_count}",
			)
			result.num_frames = actual_frame_count

		if not frame_names:
			return

		# Validate frame sequence and timestamps
		timestamps: list[float] = []
		frame_numbers: list[int] = []
		sequence_gaps: list[tuple[int, int]] = []
		prev_frame_num = -1

		for name in frame_names:
			frame = frames_group[name]
			frame_num = frame.attrs.get("frame_number", 0)
			timestamp = frame.attrs.get("timestamp", 0.0)

			frame_numbers.append(frame_num)
			timestamps.append(timestamp)

			# Check sequence
			if prev_frame_num >= 0 and frame_num != prev_frame_num + 1:
				gap = frame_num - prev_frame_num - 1
				if gap > 0:
					sequence_gaps.append((prev_frame_num, frame_num))
			prev_frame_num = frame_num

		# Report sequence gaps
		if sequence_gaps:
			total_missing = sum(b - a - 1 for a, b in sequence_gaps)
			result.add_warning(
				"sequence",
				f"Found {len(sequence_gaps)} gaps in frame sequence, {total_missing} frames missing",
				gaps=sequence_gaps[:10],  # First 10 gaps
			)

		# Check timestamp monotonicity
		self._check_timestamps(timestamps, "frame", result)

		# Set time range
		if timestamps:
			result.timestamp_range = (min(timestamps), max(timestamps))
			result.duration_seconds = max(timestamps) - min(timestamps)

	def _validate_hdf5_vitals(self, f: h5py.File, result: ValidationResult) -> None:
		"""Validate HDF5 vitals group."""
		if "vitals" not in f:
			result.add_info("schema", "No vitals group present")
			return

		vitals_group = f["vitals"]
		present_datasets = set(vitals_group.keys())

		# Check required datasets
		missing = REQUIRED_VITALS_DATASETS - present_datasets
		if missing:
			result.add_error("schema", f"Missing required vitals datasets: {missing}")

		# Check data lengths match
		lengths = {name: len(vitals_group[name]) for name in present_datasets}
		unique_lengths = set(lengths.values())
		if len(unique_lengths) > 1:
			result.add_error(
				"data",
				"Vitals datasets have inconsistent lengths",
				lengths=lengths,
			)

		# Validate timestamp dataset
		if "timestamp" in present_datasets:
			timestamps = vitals_group["timestamp"][:]
			self._check_timestamps(list(timestamps), "vitals", result)

			actual_vitals = len(timestamps)
			if result.num_vitals != actual_vitals:
				result.add_warning(
					"data",
					f"Vitals count mismatch: metadata says {result.num_vitals}, found {actual_vitals}",
				)
				result.num_vitals = actual_vitals

			# Update duration if no frames
			if not result.duration_seconds and len(timestamps) > 0:
				result.timestamp_range = (float(timestamps[0]), float(timestamps[-1]))
				result.duration_seconds = float(timestamps[-1]) - float(timestamps[0])

		# Validate data ranges
		for dataset_name, (min_val, max_val) in DATA_RANGES.items():
			if dataset_name in present_datasets:
				self._check_data_range(
					vitals_group[dataset_name][:], dataset_name, min_val, max_val, result
				)

	def _validate_parquet(self, path: Path) -> ValidationResult:
		"""Validate Parquet recording file."""
		result = ValidationResult(path=path, format="parquet")

		try:
			# Read metadata
			pf = pq.read_metadata(path)
			result.num_vitals = pf.num_rows

			# Check file metadata
			if pf.schema.pandas_metadata:
				# Schema info from pandas metadata
				pass

			# Read the full table for validation
			df = pd.read_parquet(path)
			present_columns = set(df.columns)

			# Check required columns
			missing = REQUIRED_PARQUET_COLUMNS - present_columns
			if missing:
				result.add_error("schema", f"Missing required columns: {missing}")

			# Validate timestamps
			if "timestamp" in present_columns:
				timestamps = df["timestamp"].tolist()
				self._check_timestamps(timestamps, "vitals", result)

				if timestamps:
					result.timestamp_range = (min(timestamps), max(timestamps))
					result.duration_seconds = max(timestamps) - min(timestamps)

			# Validate data ranges
			for col, (min_val, max_val) in DATA_RANGES.items():
				if col in present_columns:
					self._check_data_range(df[col].values, col, min_val, max_val, result)

			# Try to get metadata from parquet schema
			schema = pq.read_schema(path)
			if schema.metadata:
				meta = schema.metadata
				result.schema_version = meta.get(b"schema_version", b"").decode() or None
				result.session_id = meta.get(b"session_id", b"").decode() or None
				result.start_time = meta.get(b"start_time", b"").decode() or None
				result.firmware_type = meta.get(b"firmware_type", b"").decode() or None

		except Exception as e:
			result.add_error("file", f"Cannot read Parquet file: {e}")

		return result

	def _check_timestamps(
		self, timestamps: list[float], context: str, result: ValidationResult
	) -> None:
		"""Check timestamp monotonicity and detect gaps."""
		if len(timestamps) < 2:
			return

		non_monotonic = 0
		large_gaps = 0
		max_gap = 0.0

		for i in range(1, len(timestamps)):
			dt = timestamps[i] - timestamps[i - 1]

			if dt < 0:
				non_monotonic += 1
			elif dt > 5.0:  # Gap > 5 seconds
				large_gaps += 1
				max_gap = max(max_gap, dt)

		if non_monotonic > 0:
			result.add_error(
				"timestamp",
				f"Non-monotonic timestamps in {context}: {non_monotonic} occurrences",
			)

		if large_gaps > 0:
			result.add_warning(
				"timestamp",
				f"Large gaps (>5s) in {context} timestamps: {large_gaps} gaps, max {max_gap:.2f}s",
			)

	def _check_data_range(
		self,
		data: np.ndarray,
		name: str,
		min_val: float,
		max_val: float,
		result: ValidationResult,
	) -> None:
		"""Check data values are within expected range."""
		# Filter out NaN values
		valid_data = data[~np.isnan(data)]
		if len(valid_data) == 0:
			return

		below_min = np.sum(valid_data < min_val)
		above_max = np.sum(valid_data > max_val)

		if below_min > 0 or above_max > 0:
			actual_min = float(np.min(valid_data))
			actual_max = float(np.max(valid_data))
			result.add_warning(
				"data",
				f"{name}: {below_min} values below {min_val}, {above_max} above {max_val}",
				actual_range=(actual_min, actual_max),
			)


def print_result(result: ValidationResult, verbose: bool = False) -> None:
	"""Print validation result to console."""
	status = "VALID" if result.valid else "INVALID"
	status_color = "\033[92m" if result.valid else "\033[91m"
	reset = "\033[0m"

	print(f"\n{status_color}[{status}]{reset} {result.path}")
	print(f"  Format: {result.format}")
	print(f"  Schema version: {result.schema_version or 'unknown'}")
	print(f"  Session: {result.session_id or 'unknown'}")
	print(f"  Frames: {result.num_frames}, Vitals: {result.num_vitals}")
	print(f"  Duration: {result.duration_seconds:.2f}s")

	if result.issues:
		print(f"  Issues: {result.error_count} errors, {result.warning_count} warnings")

		if verbose or result.error_count > 0:
			for issue in result.issues:
				level_color = {
					"error": "\033[91m",
					"warning": "\033[93m",
					"info": "\033[94m",
				}.get(issue.level, "")
				print(f"    {level_color}[{issue.level.upper()}]{reset} [{issue.category}] {issue.message}")
				if verbose and issue.details:
					for k, v in issue.details.items():
						print(f"      {k}: {v}")


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Validate recording files for schema and data integrity"
	)
	parser.add_argument(
		"files",
		nargs="+",
		type=Path,
		help="Recording files to validate (.h5, .hdf5, .parquet, .pq)",
	)
	parser.add_argument(
		"-v", "--verbose",
		action="store_true",
		help="Show detailed validation output",
	)
	parser.add_argument(
		"--summary",
		action="store_true",
		help="Show only summary, no individual file details",
	)
	parser.add_argument(
		"--json",
		action="store_true",
		help="Output results as JSON",
	)

	args = parser.parse_args()
	validator = RecordingValidator(verbose=args.verbose)

	results: list[ValidationResult] = []
	for path in args.files:
		# Handle glob patterns passed through shell
		if path.exists():
			result = validator.validate(path)
			results.append(result)
		else:
			# Try as glob pattern
			import glob
			matched = glob.glob(str(path))
			for p in matched:
				result = validator.validate(Path(p))
				results.append(result)

	if not results:
		print("No files to validate")
		return 1

	if args.json:
		import json
		output = {
			"validated_at": datetime.now().isoformat(),
			"files": [r.to_dict() for r in results],
			"summary": {
				"total": len(results),
				"valid": sum(1 for r in results if r.valid),
				"invalid": sum(1 for r in results if not r.valid),
			},
		}
		print(json.dumps(output, indent=2))
	elif args.summary:
		valid = sum(1 for r in results if r.valid)
		invalid = sum(1 for r in results if not r.valid)
		total_frames = sum(r.num_frames for r in results)
		total_vitals = sum(r.num_vitals for r in results)
		total_duration = sum(r.duration_seconds for r in results)

		print("\nValidation Summary")
		print(f"  Files: {len(results)} ({valid} valid, {invalid} invalid)")
		print(f"  Total frames: {total_frames}")
		print(f"  Total vitals: {total_vitals}")
		print(f"  Total duration: {total_duration:.2f}s ({total_duration/3600:.2f}h)")

		if invalid > 0:
			print("\n  Invalid files:")
			for r in results:
				if not r.valid:
					print(f"    - {r.path}: {r.error_count} errors")
	else:
		for result in results:
			print_result(result, args.verbose)

	# Return 0 if all valid, 1 if any invalid
	return 0 if all(r.valid for r in results) else 1


if __name__ == "__main__":
	sys.exit(main())
