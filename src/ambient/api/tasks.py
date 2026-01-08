"""Background tasks for sensor acquisition."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from ambient.vitals.extractor import VitalSigns as VitalSignsData

from .schemas import DetectedPoint, VitalSigns

if TYPE_CHECKING:
	from .state import AppState
	from .ws.manager import ConnectionManager

logger = logging.getLogger(__name__)


def frame_to_dict(frame, processed=None) -> dict:
	"""Convert RadarFrame to serializable dict."""
	detected = []
	for pt in frame.detected_points:
		detected.append(DetectedPoint(
			x=float(pt.x),
			y=float(pt.y),
			z=float(pt.z),
			velocity=float(pt.velocity),
			snr=float(pt.snr) if hasattr(pt, "snr") else 0.0,
		).model_dump())

	result = {
		"frame_number": frame.header.frame_number if frame.header else 0,
		"timestamp": frame.timestamp,
		"range_profile": frame.range_profile.tolist() if frame.range_profile is not None else [],
		"detected_points": detected,
	}

	if frame.range_doppler_heatmap is not None:
		# Downsample if too large
		heatmap = frame.range_doppler_heatmap
		if heatmap.shape[0] > 64:
			heatmap = heatmap[::heatmap.shape[0]//64, :]
		if heatmap.shape[1] > 64:
			heatmap = heatmap[:, ::heatmap.shape[1]//64]
		result["range_doppler"] = heatmap.tolist()

	if processed and processed.phase_data is not None:
		# Handle both scalar and array phase_data
		pd = processed.phase_data
		if hasattr(pd, 'ndim') and pd.ndim > 0:
			result["phase"] = float(pd[0]) if pd.size > 0 else 0.0
		else:
			result["phase"] = float(pd)

	return result


def vitals_to_dict(vitals) -> dict:
	"""Convert VitalSigns to serializable dict."""
	result = VitalSigns(
		heart_rate_bpm=vitals.heart_rate_bpm,
		heart_rate_confidence=vitals.heart_rate_confidence,
		respiratory_rate_bpm=vitals.respiratory_rate_bpm,
		respiratory_rate_confidence=vitals.respiratory_rate_confidence,
		signal_quality=vitals.signal_quality,
		motion_detected=vitals.motion_detected,
		source=getattr(vitals, 'source', 'estimated'),
		unwrapped_phase=getattr(vitals, 'unwrapped_phase', None),
		# Enhanced quality metrics
		hr_snr_db=getattr(vitals, 'hr_snr_db', 0.0),
		rr_snr_db=getattr(vitals, 'rr_snr_db', 0.0),
		phase_stability=getattr(vitals, 'phase_stability', 0.0),
	)
	# Add waveforms if available
	if vitals.respiratory_waveform is not None:
		result.breathing_waveform = vitals.respiratory_waveform.tolist()
	if vitals.heart_rate_waveform is not None:
		result.heart_waveform = vitals.heart_rate_waveform.tolist()
	return result.model_dump()


async def acquisition_loop(state: AppState, ws_manager: ConnectionManager):
	"""Main acquisition loop running in background."""
	device = state.device
	sensor = device.sensor
	pipeline = device.pipeline
	extractor = device.extractor

	if not sensor or not pipeline or not extractor:
		logger.error("Acquisition started without sensor/pipeline/extractor")
		return

	last_vitals_broadcast = 0.0
	vitals_interval = 1.0  # Broadcast vitals at 1 Hz

	logger.info("Starting acquisition loop")

	try:
		while device.state.value == "streaming":
			try:
				frame = sensor.read_frame(timeout=0.1)
				if frame is None:
					await asyncio.sleep(0.01)
					continue

				device.record_frame()

				# Process frame
				processed = pipeline.process(frame)

				# Use firmware vital signs if available, otherwise fall back to estimation
				if frame.vital_signs is not None:
					vitals = VitalSignsData.from_firmware(frame.vital_signs, frame.timestamp)
				else:
					vitals = extractor.process_frame(processed)

				# Write to recording if active
				if state.recording.is_recording:
					state.recording.write_frame(frame)
					if vitals and vitals.is_valid():
						state.recording.write_vitals(vitals)

				# Broadcast frame data
				frame_msg = {
					"type": "sensor_frame",
					"timestamp": time.time(),
					"payload": frame_to_dict(frame, processed),
				}
				await ws_manager.broadcast("sensor", frame_msg)

				# Broadcast vitals at lower rate
				now = time.time()
				if vitals and (now - last_vitals_broadcast) >= vitals_interval:
					vitals_msg = {
						"type": "vitals",
						"timestamp": now,
						"payload": vitals_to_dict(vitals),
					}
					await ws_manager.broadcast("sensor", vitals_msg)
					last_vitals_broadcast = now

				# Yield to event loop
				await asyncio.sleep(0)

			except Exception as e:
				logger.error(f"Frame processing error: {e}")
				device.record_drop()
				await asyncio.sleep(0.01)

	except asyncio.CancelledError:
		logger.info("Acquisition loop cancelled")
		raise
	except Exception as e:
		logger.error(f"Acquisition loop error: {e}")
	finally:
		logger.info("Acquisition loop stopped")


async def start_acquisition(state: AppState, ws_manager: ConnectionManager) -> asyncio.Task:
	"""Start acquisition task."""
	task = asyncio.create_task(acquisition_loop(state, ws_manager))
	state.device._acquisition_task = task
	return task


async def stop_acquisition(state: AppState):
	"""Stop acquisition task."""
	if state.device._acquisition_task:
		state.device._acquisition_task.cancel()
		try:
			await state.device._acquisition_task
		except asyncio.CancelledError:
			pass
		state.device._acquisition_task = None
