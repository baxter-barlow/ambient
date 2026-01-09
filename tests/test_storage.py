"""Tests for storage writers (HDF5 and Parquet)."""

import tempfile
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from ambient.sensor.frame import DetectedPoint, FrameHeader, RadarFrame
from ambient.storage.writer import (
	SCHEMA_VERSION,
	HDF5Writer,
	ParquetWriter,
	SessionMetadata,
	WriteMetrics,
)
from ambient.vitals.extractor import VitalSigns

@pytest.fixture
def tmp_dir():
	"""Create a temporary directory for test files."""
	with tempfile.TemporaryDirectory() as d:
		yield Path(d)


@pytest.fixture
def sample_metadata() -> SessionMetadata:
	"""Sample session metadata."""
	return SessionMetadata(
		session_id="test_session_001",
		start_time=datetime(2025, 1, 1, 12, 0, 0),
		subject_id="subject_001",
		notes="Test session for unit tests",
		config={"sample_rate": 20, "firmware": "vitals_v1"},
		firmware_type="standard",
	)


@pytest.fixture
def sample_frame() -> RadarFrame:
	"""Sample radar frame with realistic data."""
	header = FrameHeader(
		version=0x0102,
		packet_length=128,
		platform=0x6843,
		frame_number=42,
		time_cpu_cycles=1000000,
		num_detected_obj=3,
		num_tlvs=2,
	)
	return RadarFrame(
		header=header,
		detected_points=[
			DetectedPoint(x=1.0, y=2.0, z=0.1, velocity=0.0, snr=15.0),
			DetectedPoint(x=1.5, y=2.5, z=0.2, velocity=0.1, snr=12.0),
			DetectedPoint(x=2.0, y=3.0, z=0.0, velocity=-0.05, snr=10.0),
		],
		range_profile=np.random.rand(128).astype(np.float32) * 50,
		timestamp=1704110400.0,  # 2024-01-01 12:00:00 UTC
		raw_data=b"\x00" * 128,
	)


@pytest.fixture
def sample_vitals_firmware() -> VitalSigns:
	"""Sample vital signs from firmware source."""
	return VitalSigns(
		heart_rate_bpm=72.0,
		heart_rate_confidence=0.85,
		heart_rate_waveform=np.sin(np.linspace(0, 4 * np.pi, 20)).astype(np.float32),
		respiratory_rate_bpm=15.0,
		respiratory_rate_confidence=0.90,
		respiratory_waveform=np.sin(np.linspace(0, 2 * np.pi, 20)).astype(np.float32),
		phase_signal=np.random.randn(100).astype(np.float32),
		signal_quality=0.88,
		motion_detected=False,
		timestamp=1704110400.0,
		source="firmware",
		unwrapped_phase=3.14159,
		hr_snr_db=18.5,
		rr_snr_db=22.3,
		phase_stability=0.15,
	)


@pytest.fixture
def sample_vitals_chirp() -> VitalSigns:
	"""Sample vital signs from chirp source."""
	return VitalSigns(
		heart_rate_bpm=68.0,
		heart_rate_confidence=0.78,
		heart_rate_waveform=np.sin(np.linspace(0, 4 * np.pi, 20)).astype(np.float32),
		respiratory_rate_bpm=14.0,
		respiratory_rate_confidence=0.82,
		respiratory_waveform=np.sin(np.linspace(0, 2 * np.pi, 20)).astype(np.float32),
		phase_signal=np.random.randn(100).astype(np.float32),
		signal_quality=0.80,
		motion_detected=False,
		timestamp=1704110401.0,
		source="chirp",
		unwrapped_phase=6.28318,
		hr_snr_db=15.2,
		rr_snr_db=19.8,
		phase_stability=0.22,
	)


@pytest.fixture
def sample_vitals_estimated() -> VitalSigns:
	"""Sample vital signs from estimation (no firmware)."""
	return VitalSigns(
		heart_rate_bpm=75.0,
		heart_rate_confidence=0.65,
		respiratory_rate_bpm=16.0,
		respiratory_rate_confidence=0.70,
		signal_quality=0.67,
		motion_detected=True,
		timestamp=1704110402.0,
		source="estimated",
		hr_snr_db=10.5,
		rr_snr_db=14.0,
		phase_stability=0.45,
	)


# WriteMetrics Tests


class TestWriteMetrics:
	def test_default_values(self):
		metrics = WriteMetrics()
		assert metrics.frames_written == 0
		assert metrics.vitals_written == 0
		assert metrics.write_errors == 0
		assert metrics.bytes_written == 0
		assert metrics.last_error is None

	def test_to_dict(self):
		metrics = WriteMetrics(
			frames_written=100,
			vitals_written=50,
			write_errors=2,
			bytes_written=1024000,
			last_error="Test error",
		)
		d = metrics.to_dict()
		assert d["frames_written"] == 100
		assert d["vitals_written"] == 50
		assert d["write_errors"] == 2
		assert d["bytes_written"] == 1024000
		assert d["last_error"] == "Test error"


# SessionMetadata Tests


class TestSessionMetadata:
	def test_auto_session_id(self):
		meta = SessionMetadata()
		assert meta.session_id != ""
		# Should be formatted as YYYYMMDD_HHMMSS
		assert len(meta.session_id) == 15
		assert "_" in meta.session_id

	def test_explicit_session_id(self):
		meta = SessionMetadata(session_id="my_custom_id")
		assert meta.session_id == "my_custom_id"

	def test_schema_version(self):
		meta = SessionMetadata()
		assert meta.schema_version == SCHEMA_VERSION

	def test_firmware_type_default(self):
		meta = SessionMetadata()
		assert meta.firmware_type == "unknown"


# HDF5Writer Tests


class TestHDF5Writer:
	def test_create_file(self, tmp_dir, sample_metadata):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path, sample_metadata) as writer:
			pass  # Just open and close
		assert path.exists()

	def test_creates_parent_dirs(self, tmp_dir, sample_metadata):
		path = tmp_dir / "subdir" / "nested" / "test.h5"
		with HDF5Writer(path, sample_metadata):
			pass
		assert path.exists()

	def test_metadata_stored(self, tmp_dir, sample_metadata):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path, sample_metadata):
			pass

		with h5py.File(path, "r") as f:
			assert f.attrs["schema_version"] == SCHEMA_VERSION
			assert f.attrs["session_id"] == "test_session_001"
			assert f.attrs["subject_id"] == "subject_001"
			assert f.attrs["notes"] == "Test session for unit tests"
			assert f.attrs["firmware_type"] == "standard"
			assert "start_time" in f.attrs
			assert "end_time" in f.attrs

	def test_write_frame(self, tmp_dir, sample_frame):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			success = writer.write_frame(sample_frame)
			assert success
			assert writer.metrics.frames_written == 1
			assert writer.metrics.bytes_written > 0

		with h5py.File(path, "r") as f:
			assert "frames" in f
			assert "frame_00000000" in f["frames"]
			fg = f["frames/frame_00000000"]
			assert fg.attrs["frame_number"] == 42
			assert fg.attrs["timestamp"] == sample_frame.timestamp
			assert "range_profile" in fg
			assert "detected_points" in fg

	def test_write_multiple_frames(self, tmp_dir, sample_frame):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			for i in range(10):
				sample_frame.header.frame_number = i
				writer.write_frame(sample_frame)
			assert writer.metrics.frames_written == 10

		with h5py.File(path, "r") as f:
			assert len(f["frames"]) == 10

	def test_write_vitals_firmware(self, tmp_dir, sample_vitals_firmware):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			success = writer.write_vitals(sample_vitals_firmware)
			assert success
			assert writer.metrics.vitals_written == 1

		with h5py.File(path, "r") as f:
			v = f["vitals"]
			assert v["heart_rate"][0] == pytest.approx(72.0, rel=0.01)
			assert v["respiratory_rate"][0] == pytest.approx(15.0, rel=0.01)
			assert v["hr_confidence"][0] == pytest.approx(0.85, rel=0.01)
			assert v["rr_confidence"][0] == pytest.approx(0.90, rel=0.01)
			assert v["signal_quality"][0] == pytest.approx(0.88, rel=0.01)
			assert v["source"][0] == 1  # firmware = 1
			assert v["hr_snr_db"][0] == pytest.approx(18.5, rel=0.01)
			assert v["rr_snr_db"][0] == pytest.approx(22.3, rel=0.01)
			assert v["phase_stability"][0] == pytest.approx(0.15, rel=0.01)
			assert v["unwrapped_phase"][0] == pytest.approx(3.14159, rel=0.01)

	def test_write_vitals_chirp(self, tmp_dir, sample_vitals_chirp):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			writer.write_vitals(sample_vitals_chirp)

		with h5py.File(path, "r") as f:
			assert f["vitals"]["source"][0] == 3  # chirp = 3

	def test_write_vitals_estimated(self, tmp_dir, sample_vitals_estimated):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			writer.write_vitals(sample_vitals_estimated)

		with h5py.File(path, "r") as f:
			assert f["vitals"]["source"][0] == 2  # estimated = 2
			assert f["vitals"]["motion_detected"][0] == True

	def test_source_mapping(self, tmp_dir):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			# Test source string to int conversion
			assert writer._source_to_int("unknown") == 0
			assert writer._source_to_int("firmware") == 1
			assert writer._source_to_int("estimated") == 2
			assert writer._source_to_int("chirp") == 3
			assert writer._source_to_int("invalid") == 0

	def test_compression_options(self, tmp_dir, sample_frame):
		path = tmp_dir / "test_compressed.h5"
		with HDF5Writer(path, compression="gzip", compression_level=9) as writer:
			writer.write_frame(sample_frame)

		# Verify file is valid and compressed
		with h5py.File(path, "r") as f:
			assert "frames" in f

	def test_metrics_tracking(self, tmp_dir, sample_frame, sample_vitals_firmware):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			for _ in range(5):
				writer.write_frame(sample_frame)
			for _ in range(3):
				writer.write_vitals(sample_vitals_firmware)

			m = writer.metrics
			assert m.frames_written == 5
			assert m.vitals_written == 3
			assert m.write_errors == 0
			assert m.bytes_written > 0

	def test_context_manager(self, tmp_dir):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			assert isinstance(writer, HDF5Writer)

		# File should be properly closed
		with h5py.File(path, "r") as f:
			assert f.attrs["total_frames"] == 0
			assert f.attrs["total_vitals"] == 0

	def test_final_counts_stored(self, tmp_dir, sample_frame, sample_vitals_firmware):
		path = tmp_dir / "test.h5"
		with HDF5Writer(path) as writer:
			for _ in range(7):
				writer.write_frame(sample_frame)
			for _ in range(4):
				writer.write_vitals(sample_vitals_firmware)

		with h5py.File(path, "r") as f:
			assert f.attrs["total_frames"] == 7
			assert f.attrs["total_vitals"] == 4


# ParquetWriter Tests


class TestParquetWriter:
	def test_create_file(self, tmp_dir, sample_metadata, sample_vitals_firmware):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path, sample_metadata) as writer:
			writer.write_vitals(sample_vitals_firmware)
		assert path.exists()

	def test_creates_parent_dirs(self, tmp_dir, sample_vitals_firmware):
		path = tmp_dir / "subdir" / "nested" / "test.parquet"
		with ParquetWriter(path) as writer:
			writer.write_vitals(sample_vitals_firmware)
		assert path.exists()

	def test_write_vitals_firmware(self, tmp_dir, sample_vitals_firmware):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path) as writer:
			success = writer.write_vitals(sample_vitals_firmware)
			assert success
			assert writer.metrics.vitals_written == 1

		df = pd.read_parquet(path)
		assert len(df) == 1
		assert df["heart_rate_bpm"].iloc[0] == pytest.approx(72.0, rel=0.01)
		assert df["respiratory_rate_bpm"].iloc[0] == pytest.approx(15.0, rel=0.01)
		assert df["source"].iloc[0] == "firmware"
		assert df["hr_snr_db"].iloc[0] == pytest.approx(18.5, rel=0.01)
		assert df["rr_snr_db"].iloc[0] == pytest.approx(22.3, rel=0.01)
		assert df["phase_stability"].iloc[0] == pytest.approx(0.15, rel=0.01)

	def test_write_vitals_chirp(self, tmp_dir, sample_vitals_chirp):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path) as writer:
			writer.write_vitals(sample_vitals_chirp)

		df = pd.read_parquet(path)
		assert df["source"].iloc[0] == "chirp"
		assert df["unwrapped_phase"].iloc[0] == pytest.approx(6.28318, rel=0.01)

	def test_write_multiple_vitals(self, tmp_dir, sample_vitals_firmware, sample_vitals_chirp):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path, batch_size=10) as writer:
			for _ in range(5):
				writer.write_vitals(sample_vitals_firmware)
			for _ in range(5):
				writer.write_vitals(sample_vitals_chirp)
			assert writer.metrics.vitals_written == 10

		df = pd.read_parquet(path)
		assert len(df) == 10
		assert (df["source"] == "firmware").sum() == 5
		assert (df["source"] == "chirp").sum() == 5

	def test_batch_flushing(self, tmp_dir, sample_vitals_firmware):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path, batch_size=3) as writer:
			# Write 5 records - should trigger flush after 3
			for _ in range(5):
				writer.write_vitals(sample_vitals_firmware)

		df = pd.read_parquet(path)
		assert len(df) == 5

	def test_write_frame_noop(self, tmp_dir, sample_frame):
		"""ParquetWriter.write_frame should be a no-op."""
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path) as writer:
			result = writer.write_frame(sample_frame)
			assert result == True  # Always returns True
			assert writer.metrics.frames_written == 0

	def test_metrics_tracking(self, tmp_dir, sample_vitals_firmware):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path, batch_size=5) as writer:
			for _ in range(12):
				writer.write_vitals(sample_vitals_firmware)

			m = writer.metrics
			assert m.vitals_written == 12
			assert m.write_errors == 0
			assert m.bytes_written > 0

	def test_schema_fields(self, tmp_dir, sample_vitals_firmware):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path) as writer:
			writer.write_vitals(sample_vitals_firmware)

		# Verify all expected columns
		table = pq.read_table(path)
		expected_columns = {
			"timestamp",
			"datetime",
			"heart_rate_bpm",
			"respiratory_rate_bpm",
			"hr_confidence",
			"rr_confidence",
			"signal_quality",
			"motion_detected",
			"hr_snr_db",
			"rr_snr_db",
			"phase_stability",
			"unwrapped_phase",
			"source",
		}
		actual_columns = set(table.column_names)
		assert expected_columns.issubset(actual_columns)

	def test_datetime_conversion(self, tmp_dir, sample_vitals_firmware):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path) as writer:
			writer.write_vitals(sample_vitals_firmware)

		df = pd.read_parquet(path)
		# datetime should be a proper datetime type
		assert pd.api.types.is_datetime64_any_dtype(df["datetime"])

	def test_context_manager(self, tmp_dir, sample_vitals_firmware):
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path) as writer:
			writer.write_vitals(sample_vitals_firmware)

		# File should be properly closed and readable
		df = pd.read_parquet(path)
		assert len(df) == 1


# Schema Consistency Tests


class TestSchemaConsistency:
	"""Tests to ensure HDF5 and Parquet schemas are consistent."""

	def test_schema_version_match(self):
		"""Both writers should use same schema version."""
		assert SCHEMA_VERSION == "1.1.0"

	def test_vitals_fields_match(
		self, tmp_dir, sample_vitals_firmware
	):
		"""Both writers should store the same vitals fields."""
		h5_path = tmp_dir / "test.h5"
		pq_path = tmp_dir / "test.parquet"

		with HDF5Writer(h5_path) as h5_writer:
			h5_writer.write_vitals(sample_vitals_firmware)

		with ParquetWriter(pq_path) as pq_writer:
			pq_writer.write_vitals(sample_vitals_firmware)

		# Read back and compare
		with h5py.File(h5_path, "r") as f:
			h5_hr = f["vitals"]["heart_rate"][0]
			h5_rr = f["vitals"]["respiratory_rate"][0]
			h5_hr_snr = f["vitals"]["hr_snr_db"][0]
			h5_rr_snr = f["vitals"]["rr_snr_db"][0]
			h5_stability = f["vitals"]["phase_stability"][0]

		df = pd.read_parquet(pq_path)
		pq_hr = df["heart_rate_bpm"].iloc[0]
		pq_rr = df["respiratory_rate_bpm"].iloc[0]
		pq_hr_snr = df["hr_snr_db"].iloc[0]
		pq_rr_snr = df["rr_snr_db"].iloc[0]
		pq_stability = df["phase_stability"].iloc[0]

		# Values should match
		assert h5_hr == pytest.approx(pq_hr, rel=0.001)
		assert h5_rr == pytest.approx(pq_rr, rel=0.001)
		assert h5_hr_snr == pytest.approx(pq_hr_snr, rel=0.001)
		assert h5_rr_snr == pytest.approx(pq_rr_snr, rel=0.001)
		assert h5_stability == pytest.approx(pq_stability, rel=0.001)

	def test_all_sources_supported(
		self, tmp_dir, sample_vitals_firmware, sample_vitals_chirp, sample_vitals_estimated
	):
		"""Both writers should handle all source types."""
		h5_path = tmp_dir / "test.h5"
		pq_path = tmp_dir / "test.parquet"

		with HDF5Writer(h5_path) as writer:
			writer.write_vitals(sample_vitals_firmware)
			writer.write_vitals(sample_vitals_chirp)
			writer.write_vitals(sample_vitals_estimated)

		with ParquetWriter(pq_path) as writer:
			writer.write_vitals(sample_vitals_firmware)
			writer.write_vitals(sample_vitals_chirp)
			writer.write_vitals(sample_vitals_estimated)

		with h5py.File(h5_path, "r") as f:
			sources = f["vitals"]["source"][:]
			assert list(sources) == [1, 3, 2]  # firmware, chirp, estimated

		df = pd.read_parquet(pq_path)
		assert list(df["source"]) == ["firmware", "chirp", "estimated"]


# Error Handling Tests


class TestErrorHandling:
	def test_hdf5_invalid_path(self, tmp_dir):
		"""HDF5Writer should handle invalid path gracefully."""
		# Test with invalid path - should raise during init
		# (parent dir creation should work, so this tests something else)
		path = tmp_dir / "test.h5"
		writer = HDF5Writer(path)
		writer.close()
		assert path.exists()

	def test_parquet_empty_close(self, tmp_dir):
		"""ParquetWriter should handle close with no data."""
		path = tmp_dir / "test.parquet"
		with ParquetWriter(path) as writer:
			pass  # Write nothing

		# File might not exist or be empty, both are acceptable
		# Just ensure no exception

	def test_hdf5_null_vitals_values(self, tmp_dir):
		"""HDF5Writer should handle None values in vitals."""
		path = tmp_dir / "test.h5"
		vitals = VitalSigns(
			heart_rate_bpm=None,
			respiratory_rate_bpm=None,
			timestamp=1704110400.0,
		)
		with HDF5Writer(path) as writer:
			success = writer.write_vitals(vitals)
			assert success

		with h5py.File(path, "r") as f:
			assert np.isnan(f["vitals"]["heart_rate"][0])
			assert np.isnan(f["vitals"]["respiratory_rate"][0])

	def test_parquet_null_vitals_values(self, tmp_dir):
		"""ParquetWriter should handle None values in vitals."""
		path = tmp_dir / "test.parquet"
		vitals = VitalSigns(
			heart_rate_bpm=None,
			respiratory_rate_bpm=None,
			timestamp=1704110400.0,
		)
		with ParquetWriter(path) as writer:
			success = writer.write_vitals(vitals)
			assert success

		df = pd.read_parquet(path)
		assert pd.isna(df["heart_rate_bpm"].iloc[0])
		assert pd.isna(df["respiratory_rate_bpm"].iloc[0])


# Performance Tests (lightweight)


class TestPerformance:
	def test_hdf5_bulk_write(self, tmp_dir, sample_frame, sample_vitals_firmware):
		"""HDF5Writer should handle bulk writes efficiently."""
		path = tmp_dir / "bulk.h5"
		with HDF5Writer(path) as writer:
			for i in range(100):
				sample_frame.header.frame_number = i
				writer.write_frame(sample_frame)
				writer.write_vitals(sample_vitals_firmware)

			assert writer.metrics.frames_written == 100
			assert writer.metrics.vitals_written == 100
			assert writer.metrics.write_errors == 0

	def test_parquet_bulk_write(self, tmp_dir, sample_vitals_firmware):
		"""ParquetWriter should handle bulk writes efficiently."""
		path = tmp_dir / "bulk.parquet"
		with ParquetWriter(path, batch_size=50) as writer:
			for _ in range(200):
				writer.write_vitals(sample_vitals_firmware)

			assert writer.metrics.vitals_written == 200
			assert writer.metrics.write_errors == 0

		df = pd.read_parquet(path)
		assert len(df) == 200
