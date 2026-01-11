"""Recording management API routes."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..schemas import RecordingInfo, RecordingStartRequest, RecordingStatus
from ..state import get_app_state

router = APIRouter(prefix="/api/recordings", tags=["recordings"])


def sanitize_recording_id(recording_id: str) -> str:
	"""Sanitize recording ID to prevent path traversal.

	Recording IDs typically have format: timestamp_name (e.g., 1234567890_session1)
	"""
	if not recording_id:
		raise HTTPException(status_code=400, detail="Recording ID cannot be empty")

	# Check for path traversal
	if '..' in recording_id or '/' in recording_id or '\\' in recording_id:
		raise HTTPException(status_code=400, detail="Invalid recording ID: path traversal not allowed")

	# Allow alphanumeric, underscore, hyphen only
	if not re.match(r'^[\w\-]+$', recording_id):
		raise HTTPException(status_code=400, detail="Invalid recording ID format")

	return recording_id


def get_recordings_dir() -> Path:
	return Path(os.environ.get("AMBIENT_DATA_DIR", "data"))


@router.get("", response_model=list[RecordingInfo])
async def list_recordings():
	"""List all recordings."""
	data_dir = get_recordings_dir()
	recordings = []

	if not data_dir.exists():
		return recordings

	for path in data_dir.glob("*.h5"):
		stat = path.stat()
		recordings.append(RecordingInfo(
			id=path.stem,
			name=path.stem.split("_", 1)[-1] if "_" in path.stem else path.stem,
			path=str(path),
			format="h5",
			created=stat.st_mtime,
			size_bytes=stat.st_size,
		))

	for path in data_dir.glob("*.parquet"):
		stat = path.stat()
		recordings.append(RecordingInfo(
			id=path.stem,
			name=path.stem.split("_", 1)[-1] if "_" in path.stem else path.stem,
			path=str(path),
			format="parquet",
			created=stat.st_mtime,
			size_bytes=stat.st_size,
		))

	return sorted(recordings, key=lambda r: r.created, reverse=True)


@router.get("/status", response_model=RecordingStatus)
async def get_recording_status():
	"""Get current recording status."""
	state = get_app_state()
	return state.recording.get_status()


@router.post("/start", response_model=RecordingStatus)
async def start_recording(request: RecordingStartRequest):
	"""Start a new recording."""
	state = get_app_state()

	if state.recording.is_recording:
		raise HTTPException(status_code=400, detail="Already recording")

	if state.device.state.value != "streaming":
		raise HTTPException(status_code=400, detail="Device must be streaming to record")

	try:
		state.recording.start(request.name, request.format)
		return state.recording.get_status()
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=RecordingStatus)
async def stop_recording():
	"""Stop current recording."""
	state = get_app_state()

	if not state.recording.is_recording:
		raise HTTPException(status_code=400, detail="Not recording")

	state.recording.stop()
	return state.recording.get_status()


@router.get("/{recording_id}")
async def get_recording(recording_id: str):
	"""Get recording details."""
	safe_id = sanitize_recording_id(recording_id)
	data_dir = get_recordings_dir()

	for ext in ["h5", "parquet"]:
		path = data_dir / f"{safe_id}.{ext}"
		if path.exists():
			stat = path.stat()
			return RecordingInfo(
				id=recording_id,
				name=recording_id.split("_", 1)[-1] if "_" in recording_id else recording_id,
				path=str(path),
				format=ext,
				created=stat.st_mtime,
				size_bytes=stat.st_size,
			)

	raise HTTPException(status_code=404, detail="Recording not found")


@router.delete("/{recording_id}")
async def delete_recording(recording_id: str):
	"""Delete a recording."""
	safe_id = sanitize_recording_id(recording_id)
	data_dir = get_recordings_dir()

	for ext in ["h5", "parquet"]:
		path = data_dir / f"{safe_id}.{ext}"
		if path.exists():
			path.unlink()
			return {"deleted": recording_id}

	raise HTTPException(status_code=404, detail="Recording not found")


def _cleanup_temp_file(path: str) -> None:
	"""Background task to clean up temporary files after response is sent."""
	try:
		Path(path).unlink(missing_ok=True)
	except Exception:
		pass  # Best effort cleanup


@router.get("/{recording_id}/export")
async def export_recording(
	recording_id: str,
	background_tasks: BackgroundTasks,
	format: str = "h5",
):
	"""Export recording in specified format."""
	safe_id = sanitize_recording_id(recording_id)
	data_dir = get_recordings_dir()

	# Find the recording
	source_path = None
	for ext in ["h5", "parquet"]:
		path = data_dir / f"{safe_id}.{ext}"
		if path.exists():
			source_path = path
			break

	if not source_path:
		raise HTTPException(status_code=404, detail="Recording not found")

	source_format = source_path.suffix[1:]

	# If requested format matches source, return directly
	if format == source_format or format not in ("h5", "parquet", "csv"):
		return FileResponse(
			source_path,
			filename=f"{recording_id}.{source_format}",
			media_type="application/octet-stream",
		)

	# Format conversion
	import tempfile

	from ambient.storage.reader import DataReader

	try:
		with DataReader(source_path) as reader:
			df = reader.get_vitals_dataframe()

			if format == "csv":
				# Export to CSV
				with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
					tmp_path = tmp.name
				df.to_csv(tmp_path, index=False)
				# Schedule cleanup after response is sent
				background_tasks.add_task(_cleanup_temp_file, tmp_path)
				return FileResponse(
					tmp_path,
					filename=f"{recording_id}.csv",
					media_type="text/csv",
				)
			elif format == "parquet" and source_format == "h5":
				# Convert H5 to Parquet
				with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
					tmp_path = tmp.name
				df.to_parquet(tmp_path)
				# Schedule cleanup after response is sent
				background_tasks.add_task(_cleanup_temp_file, tmp_path)
				return FileResponse(
					tmp_path,
					filename=f"{recording_id}.parquet",
					media_type="application/octet-stream",
				)
			else:
				# Unsupported conversion, return original
				return FileResponse(
					source_path,
					filename=f"{recording_id}.{source_format}",
					media_type="application/octet-stream",
				)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")
