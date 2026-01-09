"""Data writers for radar and vital signs."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import h5py
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
	from ambient.sensor.frame import RadarFrame
	from ambient.vitals.extractor import VitalSigns

logger = logging.getLogger(__name__)

# Schema version for compatibility checking
SCHEMA_VERSION = "1.1.0"


@dataclass
class SessionMetadata:
	session_id: str = ""
	start_time: datetime = field(default_factory=datetime.now)
	subject_id: str = ""
	notes: str = ""
	config: dict[str, Any] = field(default_factory=dict)
	firmware_type: str = "unknown"  # standard, chirp, unknown
	schema_version: str = SCHEMA_VERSION

	def __post_init__(self) -> None:
		if not self.session_id:
			self.session_id = self.start_time.strftime("%Y%m%d_%H%M%S")


@dataclass
class WriteMetrics:
	"""Metrics for tracking write performance."""

	frames_written: int = 0
	vitals_written: int = 0
	write_errors: int = 0
	bytes_written: int = 0
	last_error: str | None = None

	def to_dict(self) -> dict[str, Any]:
		return {
			"frames_written": self.frames_written,
			"vitals_written": self.vitals_written,
			"write_errors": self.write_errors,
			"bytes_written": self.bytes_written,
			"last_error": self.last_error,
		}


class DataWriter(ABC):
	@abstractmethod
	def write_frame(self, frame: RadarFrame) -> bool:
		"""Write frame. Returns True on success."""
		pass

	@abstractmethod
	def write_vitals(self, vitals: VitalSigns) -> bool:
		"""Write vitals. Returns True on success."""
		pass

	@abstractmethod
	def close(self) -> None:
		pass

	@property
	@abstractmethod
	def metrics(self) -> WriteMetrics:
		pass

	def __enter__(self) -> DataWriter:
		return self

	def __exit__(self, exc_type, exc_val, exc_tb) -> None:
		self.close()


class HDF5Writer(DataWriter):
	"""HDF5 writer for raw frames + vitals. Supports compression and streaming."""

	def __init__(
		self,
		path: str | Path,
		metadata: SessionMetadata | None = None,
		compression: str = "gzip",
		compression_level: int = 4,
	) -> None:
		self.path = Path(path)
		self.metadata = metadata or SessionMetadata()
		self.compression = compression
		self.compression_level = compression_level
		self._metrics = WriteMetrics()

		self.path.parent.mkdir(parents=True, exist_ok=True)
		self._file = h5py.File(self.path, "w")
		self._setup_groups()

		logger.info(f"HDF5Writer initialized: {self.path}")

	def _setup_groups(self) -> None:
		# Store metadata including schema version
		self._file.attrs["schema_version"] = self.metadata.schema_version
		self._file.attrs["session_id"] = self.metadata.session_id
		self._file.attrs["start_time"] = self.metadata.start_time.isoformat()
		self._file.attrs["subject_id"] = self.metadata.subject_id
		self._file.attrs["notes"] = self.metadata.notes
		self._file.attrs["firmware_type"] = self.metadata.firmware_type

		self._frames_group = self._file.create_group("frames")
		self._vitals_group = self._file.create_group("vitals")

		# Extended vitals schema with quality metrics
		self._vitals_ds = {
			"timestamp": self._create_ds(self._vitals_group, "timestamp", np.float64),
			"heart_rate": self._create_ds(self._vitals_group, "heart_rate", np.float32),
			"respiratory_rate": self._create_ds(self._vitals_group, "respiratory_rate", np.float32),
			"hr_confidence": self._create_ds(self._vitals_group, "hr_confidence", np.float32),
			"rr_confidence": self._create_ds(self._vitals_group, "rr_confidence", np.float32),
			"signal_quality": self._create_ds(self._vitals_group, "signal_quality", np.float32),
			"motion_detected": self._create_ds(self._vitals_group, "motion_detected", np.bool_),
			# Enhanced quality metrics
			"hr_snr_db": self._create_ds(self._vitals_group, "hr_snr_db", np.float32),
			"rr_snr_db": self._create_ds(self._vitals_group, "rr_snr_db", np.float32),
			"phase_stability": self._create_ds(self._vitals_group, "phase_stability", np.float32),
			"unwrapped_phase": self._create_ds(self._vitals_group, "unwrapped_phase", np.float32),
		}

		# Source field stored as int (0=unknown, 1=firmware, 2=estimated, 3=chirp)
		self._vitals_ds["source"] = self._create_ds(self._vitals_group, "source", np.int8)

	def _create_ds(self, group: h5py.Group, name: str, dtype: Any) -> h5py.Dataset:
		opts = {"compression_opts": self.compression_level} if self.compression == "gzip" else {}
		return group.create_dataset(
			name, shape=(0,), maxshape=(None,), dtype=dtype,
			chunks=(1000,), compression=self.compression, **opts
		)

	def _source_to_int(self, source: str) -> int:
		"""Convert source string to int for storage."""
		mapping = {"unknown": 0, "firmware": 1, "estimated": 2, "chirp": 3}
		return mapping.get(source, 0)

	@property
	def metrics(self) -> WriteMetrics:
		return self._metrics

	def write_frame(self, frame: RadarFrame) -> bool:
		try:
			fg = self._frames_group.create_group(f"frame_{self._metrics.frames_written:08d}")
			fg.attrs["frame_number"] = frame.header.frame_number if frame.header else 0
			fg.attrs["timestamp"] = frame.timestamp
			fg.attrs["num_detected"] = frame.header.num_detected_obj if frame.header else 0

			bytes_written = 0
			if frame.raw_data:
				raw_arr = np.frombuffer(frame.raw_data, dtype=np.uint8)
				fg.create_dataset("raw", data=raw_arr, compression=self.compression)
				bytes_written += len(frame.raw_data)

			if frame.range_profile is not None:
				fg.create_dataset("range_profile", data=frame.range_profile, compression=self.compression)
				bytes_written += frame.range_profile.nbytes

			if frame.detected_points:
				pts = np.array(
					[(p.x, p.y, p.z, p.velocity, getattr(p, "snr", 0.0)) for p in frame.detected_points],
					dtype=[("x", np.float32), ("y", np.float32), ("z", np.float32), ("velocity", np.float32), ("snr", np.float32)]
				)
				fg.create_dataset("detected_points", data=pts)
				bytes_written += pts.nbytes

			self._metrics.frames_written += 1
			self._metrics.bytes_written += bytes_written
			return True

		except Exception as e:
			self._metrics.write_errors += 1
			self._metrics.last_error = str(e)
			logger.error(f"HDF5 write_frame error: {e}")
			return False

	def write_vitals(self, vitals: VitalSigns) -> bool:
		try:
			idx = self._metrics.vitals_written
			for ds in self._vitals_ds.values():
				ds.resize((idx + 1,))

			self._vitals_ds["timestamp"][idx] = vitals.timestamp
			self._vitals_ds["heart_rate"][idx] = vitals.heart_rate_bpm if vitals.heart_rate_bpm else np.nan
			self._vitals_ds["respiratory_rate"][idx] = vitals.respiratory_rate_bpm if vitals.respiratory_rate_bpm else np.nan
			self._vitals_ds["hr_confidence"][idx] = vitals.heart_rate_confidence
			self._vitals_ds["rr_confidence"][idx] = vitals.respiratory_rate_confidence
			self._vitals_ds["signal_quality"][idx] = vitals.signal_quality
			self._vitals_ds["motion_detected"][idx] = vitals.motion_detected

			# Enhanced metrics
			self._vitals_ds["hr_snr_db"][idx] = getattr(vitals, "hr_snr_db", 0.0)
			self._vitals_ds["rr_snr_db"][idx] = getattr(vitals, "rr_snr_db", 0.0)
			self._vitals_ds["phase_stability"][idx] = getattr(vitals, "phase_stability", 0.0)
			self._vitals_ds["unwrapped_phase"][idx] = getattr(vitals, "unwrapped_phase", None) or np.nan
			self._vitals_ds["source"][idx] = self._source_to_int(getattr(vitals, "source", "unknown"))

			self._metrics.vitals_written += 1
			return True

		except Exception as e:
			self._metrics.write_errors += 1
			self._metrics.last_error = str(e)
			logger.error(f"HDF5 write_vitals error: {e}")
			return False

	def close(self) -> None:
		try:
			self._file.attrs["end_time"] = datetime.now().isoformat()
			self._file.attrs["total_frames"] = self._metrics.frames_written
			self._file.attrs["total_vitals"] = self._metrics.vitals_written
			self._file.close()
			logger.info(
				f"HDF5Writer closed: frames={self._metrics.frames_written}, "
				f"vitals={self._metrics.vitals_written}, errors={self._metrics.write_errors}"
			)
		except Exception as e:
			logger.error(f"HDF5 close error: {e}")


class ParquetWriter(DataWriter):
	"""Parquet writer for vitals time series. Best for pandas analysis."""

	def __init__(
		self,
		path: str | Path,
		metadata: SessionMetadata | None = None,
		batch_size: int = 1000
	) -> None:
		self.path = Path(path)
		self.metadata = metadata or SessionMetadata()
		self.batch_size = batch_size
		self._metrics = WriteMetrics()
		self.path.parent.mkdir(parents=True, exist_ok=True)

		self._buffer: list[dict[str, Any]] = []
		self._writer: pq.ParquetWriter | None = None

		# Extended schema with quality metrics
		self._schema = pa.schema([
			("timestamp", pa.float64()),
			("datetime", pa.timestamp("us")),
			("heart_rate_bpm", pa.float32()),
			("respiratory_rate_bpm", pa.float32()),
			("hr_confidence", pa.float32()),
			("rr_confidence", pa.float32()),
			("signal_quality", pa.float32()),
			("motion_detected", pa.bool_()),
			# Enhanced quality metrics
			("hr_snr_db", pa.float32()),
			("rr_snr_db", pa.float32()),
			("phase_stability", pa.float32()),
			("unwrapped_phase", pa.float32()),
			("source", pa.string()),
		])

		# Build metadata for parquet file
		self._file_metadata = {
			b"schema_version": self.metadata.schema_version.encode(),
			b"session_id": self.metadata.session_id.encode(),
			b"start_time": self.metadata.start_time.isoformat().encode(),
			b"firmware_type": self.metadata.firmware_type.encode(),
		}

		logger.info(f"ParquetWriter initialized: {self.path}")

	@property
	def metrics(self) -> WriteMetrics:
		return self._metrics

	def write_frame(self, frame: RadarFrame) -> bool:
		# Parquet writer is for vitals only
		return True

	def write_vitals(self, vitals: VitalSigns) -> bool:
		try:
			# Safely get timestamp for datetime conversion
			ts = vitals.timestamp
			dt = None
			if ts and ts > 0:
				try:
					dt = datetime.fromtimestamp(ts)
				except (ValueError, OSError):
					pass

			self._buffer.append({
				"timestamp": ts,
				"datetime": dt,
				"heart_rate_bpm": vitals.heart_rate_bpm,
				"respiratory_rate_bpm": vitals.respiratory_rate_bpm,
				"hr_confidence": vitals.heart_rate_confidence,
				"rr_confidence": vitals.respiratory_rate_confidence,
				"signal_quality": vitals.signal_quality,
				"motion_detected": vitals.motion_detected,
				# Enhanced quality metrics
				"hr_snr_db": getattr(vitals, "hr_snr_db", 0.0),
				"rr_snr_db": getattr(vitals, "rr_snr_db", 0.0),
				"phase_stability": getattr(vitals, "phase_stability", 0.0),
				"unwrapped_phase": getattr(vitals, "unwrapped_phase", None),
				"source": getattr(vitals, "source", "unknown"),
			})

			self._metrics.vitals_written += 1

			if len(self._buffer) >= self.batch_size:
				return self._flush()

			return True

		except Exception as e:
			self._metrics.write_errors += 1
			self._metrics.last_error = str(e)
			logger.error(f"ParquetWriter write_vitals error: {e}")
			return False

	def _flush(self) -> bool:
		if not self._buffer:
			return True

		try:
			df = pd.DataFrame(self._buffer)
			table = pa.Table.from_pandas(df, schema=self._schema, preserve_index=False)

			if self._writer is None:
				self._writer = pq.ParquetWriter(
					self.path,
					self._schema,
					compression="snappy",
					coerce_timestamps="us",
				)
				# Write metadata
				self._writer.writer.add_key_value_metadata(self._file_metadata)

			self._writer.write_table(table)
			self._metrics.bytes_written += table.nbytes
			self._buffer.clear()
			return True

		except Exception as e:
			self._metrics.write_errors += 1
			self._metrics.last_error = str(e)
			logger.error(f"ParquetWriter flush error: {e}")
			return False

	def close(self) -> None:
		try:
			self._flush()
			if self._writer:
				self._writer.close()
			logger.info(
				f"ParquetWriter closed: vitals={self._metrics.vitals_written}, "
				f"errors={self._metrics.write_errors}"
			)
		except Exception as e:
			logger.error(f"ParquetWriter close error: {e}")
