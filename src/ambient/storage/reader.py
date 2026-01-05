"""Data readers for stored radar and vital signs data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import h5py
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import structlog
from numpy.typing import NDArray

logger = structlog.get_logger(__name__)


@dataclass
class StoredFrame:
	frame_number: int
	timestamp: float
	raw_data: bytes | None = None
	range_profile: NDArray[np.float32] | None = None
	detected_points: list[tuple[float, ...]] | None = None


class DataReader:
	"""Read stored radar/vitals data. Supports HDF5 and Parquet."""

	def __init__(self, path: str | Path) -> None:
		self.path = Path(path)
		if not self.path.exists():
			raise FileNotFoundError(f"Not found: {self.path}")

		self._file: h5py.File | None = None
		self._parquet = False

		if self.path.suffix in [".parquet", ".pq"]:
			self._parquet = True
		elif self.path.suffix in [".h5", ".hdf5"]:
			self._file = h5py.File(self.path, "r")
		else:
			raise ValueError(f"Unsupported format: {self.path.suffix}")

		logger.info("data_reader_init", path=str(self.path))

	@property
	def metadata(self) -> dict[str, Any]:
		if self._parquet:
			pf = pq.read_metadata(self.path)
			return {"num_rows": pf.num_rows, "num_columns": pf.num_columns, "format": "parquet"}
		if self._file is None:
			return {}
		return {
			"session_id": self._file.attrs.get("session_id", ""),
			"start_time": self._file.attrs.get("start_time", ""),
			"end_time": self._file.attrs.get("end_time", ""),
			"subject_id": self._file.attrs.get("subject_id", ""),
			"notes": self._file.attrs.get("notes", ""),
			"total_frames": self._file.attrs.get("total_frames", 0),
			"total_vitals": self._file.attrs.get("total_vitals", 0),
			"format": "hdf5",
		}

	@property
	def num_frames(self) -> int:
		if self._parquet:
			return 0
		if self._file and "frames" in self._file:
			return len(self._file["frames"])
		return 0

	def get_vitals_dataframe(self) -> pd.DataFrame:
		if self._parquet:
			return pd.read_parquet(self.path)

		if self._file is None or "vitals" not in self._file:
			return pd.DataFrame()

		vg = self._file["vitals"]
		data = {key: vg[key][:] for key in vg.keys()}
		df = pd.DataFrame(data)
		if "timestamp" in df.columns:
			df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
		return df

	def get_vitals_array(self, key: str) -> NDArray:
		if self._parquet:
			return pd.read_parquet(self.path, columns=[key])[key].values
		if self._file is None or "vitals" not in self._file:
			return np.array([])
		return self._file["vitals"][key][:]

	def iter_frames(self) -> Iterator[StoredFrame]:
		if self._parquet or self._file is None:
			return
		fg = self._file.get("frames")
		if fg is None:
			return

		for name in sorted(fg.keys()):
			g = fg[name]
			frame = StoredFrame(
				frame_number=g.attrs.get("frame_number", 0),
				timestamp=g.attrs.get("timestamp", 0.0),
			)
			if "raw" in g:
				frame.raw_data = bytes(g["raw"][:])
			if "range_profile" in g:
				frame.range_profile = g["range_profile"][:]
			if "detected_points" in g:
				frame.detected_points = [tuple(p) for p in g["detected_points"][:]]
			yield frame

	def get_frame(self, index: int) -> StoredFrame | None:
		if self._parquet or self._file is None:
			return None
		fg = self._file.get("frames")
		if fg is None:
			return None

		name = f"frame_{index:08d}"
		if name not in fg:
			return None

		g = fg[name]
		frame = StoredFrame(
			frame_number=g.attrs.get("frame_number", 0),
			timestamp=g.attrs.get("timestamp", 0.0),
		)
		if "range_profile" in g:
			frame.range_profile = g["range_profile"][:]
		return frame

	def get_time_range(self) -> tuple[float, float]:
		if self._parquet:
			df = pd.read_parquet(self.path, columns=["timestamp"])
			return float(df["timestamp"].min()), float(df["timestamp"].max())
		if self._file is None or "vitals" not in self._file:
			return 0.0, 0.0
		ts = self._file["vitals"]["timestamp"][:]
		return (float(ts[0]), float(ts[-1])) if len(ts) else (0.0, 0.0)

	def close(self) -> None:
		if self._file:
			self._file.close()
			self._file = None

	def __enter__(self) -> DataReader:
		return self

	def __exit__(self, exc_type, exc_val, exc_tb) -> None:
		self.close()
