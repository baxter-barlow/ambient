"""Data writers for radar and vital signs."""

from __future__ import annotations

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
import structlog

if TYPE_CHECKING:
	from ambient.sensor.frame import RadarFrame
	from ambient.vitals.extractor import VitalSigns

logger = structlog.get_logger(__name__)


@dataclass
class SessionMetadata:
	session_id: str = ""
	start_time: datetime = field(default_factory=datetime.now)
	subject_id: str = ""
	notes: str = ""
	config: dict[str, Any] = field(default_factory=dict)

	def __post_init__(self) -> None:
		if not self.session_id:
			self.session_id = self.start_time.strftime("%Y%m%d_%H%M%S")


class DataWriter(ABC):
	@abstractmethod
	def write_frame(self, frame: RadarFrame) -> None:
		pass

	@abstractmethod
	def write_vitals(self, vitals: VitalSigns) -> None:
		pass

	@abstractmethod
	def close(self) -> None:
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

		self.path.parent.mkdir(parents=True, exist_ok=True)
		self._file = h5py.File(self.path, "w")
		self._setup_groups()
		self._frame_count = 0
		self._vitals_count = 0

		logger.info("hdf5_writer_init", path=str(self.path))

	def _setup_groups(self) -> None:
		self._file.attrs["session_id"] = self.metadata.session_id
		self._file.attrs["start_time"] = self.metadata.start_time.isoformat()
		self._file.attrs["subject_id"] = self.metadata.subject_id
		self._file.attrs["notes"] = self.metadata.notes

		self._frames_group = self._file.create_group("frames")
		self._vitals_group = self._file.create_group("vitals")

		self._vitals_ds = {
			"timestamp": self._create_ds(self._vitals_group, "timestamp", np.float64),
			"heart_rate": self._create_ds(self._vitals_group, "heart_rate", np.float32),
			"respiratory_rate": self._create_ds(self._vitals_group, "respiratory_rate", np.float32),
			"hr_confidence": self._create_ds(self._vitals_group, "hr_confidence", np.float32),
			"rr_confidence": self._create_ds(self._vitals_group, "rr_confidence", np.float32),
			"signal_quality": self._create_ds(self._vitals_group, "signal_quality", np.float32),
		}

	def _create_ds(self, group: h5py.Group, name: str, dtype: Any) -> h5py.Dataset:
		opts = {"compression_opts": self.compression_level} if self.compression == "gzip" else {}
		return group.create_dataset(
			name, shape=(0,), maxshape=(None,), dtype=dtype,
			chunks=(1000,), compression=self.compression, **opts
		)

	def write_frame(self, frame: RadarFrame) -> None:
		fg = self._frames_group.create_group(f"frame_{self._frame_count:08d}")
		fg.attrs["frame_number"] = frame.header.frame_number if frame.header else 0
		fg.attrs["timestamp"] = frame.timestamp
		fg.attrs["num_detected"] = frame.header.num_detected_obj if frame.header else 0

		if frame.raw_data:
			fg.create_dataset("raw", data=np.frombuffer(frame.raw_data, dtype=np.uint8), compression=self.compression)
		if frame.range_profile is not None:
			fg.create_dataset("range_profile", data=frame.range_profile, compression=self.compression)
		if frame.detected_points:
			pts = np.array(
				[(p.x, p.y, p.z, p.velocity, p.snr) for p in frame.detected_points],
				dtype=[("x", np.float32), ("y", np.float32), ("z", np.float32), ("velocity", np.float32), ("snr", np.float32)]
			)
			fg.create_dataset("detected_points", data=pts)

		self._frame_count += 1

	def write_vitals(self, vitals: VitalSigns) -> None:
		for ds in self._vitals_ds.values():
			ds.resize((self._vitals_count + 1,))

		self._vitals_ds["timestamp"][self._vitals_count] = vitals.timestamp
		self._vitals_ds["heart_rate"][self._vitals_count] = vitals.heart_rate_bpm if vitals.heart_rate_bpm else np.nan
		self._vitals_ds["respiratory_rate"][self._vitals_count] = vitals.respiratory_rate_bpm if vitals.respiratory_rate_bpm else np.nan
		self._vitals_ds["hr_confidence"][self._vitals_count] = vitals.heart_rate_confidence
		self._vitals_ds["rr_confidence"][self._vitals_count] = vitals.respiratory_rate_confidence
		self._vitals_ds["signal_quality"][self._vitals_count] = vitals.signal_quality
		self._vitals_count += 1

	def close(self) -> None:
		self._file.attrs["end_time"] = datetime.now().isoformat()
		self._file.attrs["total_frames"] = self._frame_count
		self._file.attrs["total_vitals"] = self._vitals_count
		self._file.close()
		logger.info("hdf5_writer_closed", frames=self._frame_count, vitals=self._vitals_count)


class ParquetWriter(DataWriter):
	"""Parquet writer for vitals time series. Best for pandas analysis."""

	def __init__(self, path: str | Path, metadata: SessionMetadata | None = None, batch_size: int = 1000) -> None:
		self.path = Path(path)
		self.metadata = metadata or SessionMetadata()
		self.batch_size = batch_size
		self.path.parent.mkdir(parents=True, exist_ok=True)

		self._buffer: list[dict[str, Any]] = []
		self._writer: pq.ParquetWriter | None = None
		self._schema = pa.schema([
			("timestamp", pa.float64()),
			("datetime", pa.timestamp("us")),
			("heart_rate_bpm", pa.float32()),
			("respiratory_rate_bpm", pa.float32()),
			("hr_confidence", pa.float32()),
			("rr_confidence", pa.float32()),
			("signal_quality", pa.float32()),
			("motion_detected", pa.bool_()),
		])
		logger.info("parquet_writer_init", path=str(self.path))

	def write_frame(self, frame: RadarFrame) -> None:
		pass  # use HDF5 for raw frames

	def write_vitals(self, vitals: VitalSigns) -> None:
		self._buffer.append({
			"timestamp": vitals.timestamp,
			"datetime": datetime.fromtimestamp(vitals.timestamp) if vitals.timestamp else None,
			"heart_rate_bpm": vitals.heart_rate_bpm,
			"respiratory_rate_bpm": vitals.respiratory_rate_bpm,
			"hr_confidence": vitals.heart_rate_confidence,
			"rr_confidence": vitals.respiratory_rate_confidence,
			"signal_quality": vitals.signal_quality,
			"motion_detected": vitals.motion_detected,
		})
		if len(self._buffer) >= self.batch_size:
			self._flush()

	def _flush(self) -> None:
		if not self._buffer:
			return
		table = pa.Table.from_pandas(pd.DataFrame(self._buffer), schema=self._schema)
		if self._writer is None:
			self._writer = pq.ParquetWriter(self.path, self._schema, compression="snappy")
		self._writer.write_table(table)
		self._buffer.clear()

	def close(self) -> None:
		self._flush()
		if self._writer:
			self._writer.close()
		logger.info("parquet_writer_closed", path=str(self.path))
