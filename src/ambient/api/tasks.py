"""Background tasks for sensor acquisition."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from ambient.config import get_config
from ambient.utils.profiler import get_profiler
from ambient.vitals.extractor import ChirpVitalsProcessor
from ambient.vitals.extractor import VitalsConfig as ExtractorVitalsConfig
from ambient.vitals.extractor import VitalSigns as VitalSignsData

from .schemas import DetectedPoint, VitalSigns

if TYPE_CHECKING:
	from numpy.typing import NDArray

	from .state import AppState
	from .ws.manager import ConnectionManager

logger = logging.getLogger(__name__)

# Environment variable for debug logging (once per session)
AMBIENT_DEBUG = os.environ.get("AMBIENT_DEBUG", "").lower() == "true"


@dataclass
class StreamingConfig:
	"""Configuration for streaming behavior."""

	max_heatmap_size: int = 64  # Max rows/cols for range_doppler
	max_waveform_samples: int = 200  # Max samples for waveforms
	max_phase_signal_samples: int = 200  # Max samples for phase_signal
	vitals_interval_hz: float = 1.0  # Vitals broadcast rate
	include_range_doppler: bool = True  # Include range_doppler in frames
	include_waveforms: bool = True  # Include waveforms in vitals


def _init_streaming_config() -> StreamingConfig:
	"""Initialize streaming config from AppConfig."""
	from ambient.config import get_config
	app_config = get_config()
	return StreamingConfig(
		max_heatmap_size=app_config.streaming.max_heatmap_size,
		max_waveform_samples=app_config.streaming.max_waveform_samples,
		max_phase_signal_samples=app_config.streaming.max_phase_signal_samples,
		vitals_interval_hz=app_config.streaming.vitals_interval_hz,
		include_range_doppler=app_config.streaming.include_range_doppler,
		include_waveforms=app_config.streaming.include_waveforms,
	)


# Global streaming config (initialized from AppConfig)
streaming_config = _init_streaming_config()


def _create_extractor_config() -> ExtractorVitalsConfig:
	"""Create extractor VitalsConfig from centralized AppConfig."""
	app_config = get_config()
	vitals_cfg = app_config.vitals
	return ExtractorVitalsConfig(
		sample_rate_hz=vitals_cfg.sample_rate_hz,
		window_seconds=vitals_cfg.window_seconds,
		hr_freq_min_hz=vitals_cfg.hr_freq_min_hz,
		hr_freq_max_hz=vitals_cfg.hr_freq_max_hz,
		rr_freq_min_hz=vitals_cfg.rr_freq_min_hz,
		rr_freq_max_hz=vitals_cfg.rr_freq_max_hz,
		motion_threshold=vitals_cfg.motion_threshold,
	)


class FrameRateTracker:
	"""Track frame rate from incoming frame timestamps."""

	def __init__(self, window_size: int = 100, tolerance: float = 0.15):
		self._timestamps: deque[float] = deque(maxlen=window_size)
		self._tolerance = tolerance
		self._last_warning_time = 0.0
		self._warning_interval = 30.0  # Only warn every 30s

	def record(self, timestamp: float) -> None:
		"""Record frame timestamp."""
		self._timestamps.append(timestamp)

	@property
	def measured_rate(self) -> float | None:
		"""Calculate measured frame rate from timestamps."""
		if len(self._timestamps) < 10:
			return None
		dt = self._timestamps[-1] - self._timestamps[0]
		if dt <= 0:
			return None
		return (len(self._timestamps) - 1) / dt

	def check_rate(self, configured_rate: float) -> float:
		"""Check measured rate against configured rate.

		Returns the rate to use for vitals processing (measured if mismatch, else configured).
		"""
		measured = self.measured_rate
		if measured is None:
			return configured_rate

		# Calculate relative error
		relative_error = abs(measured - configured_rate) / configured_rate

		if relative_error > self._tolerance:
			now = time.time()
			if now - self._last_warning_time > self._warning_interval:
				logger.warning(
					f"Frame rate mismatch: configured={configured_rate:.1f}Hz, "
					f"measured={measured:.1f}Hz (error={relative_error:.1%}). "
					f"Using measured rate for vitals."
				)
				self._last_warning_time = now
			return measured

		return configured_rate


def downsample_array(arr: NDArray, max_samples: int) -> NDArray:
	"""Downsample 1D array to max_samples using decimation."""
	if len(arr) <= max_samples:
		return arr
	step = len(arr) // max_samples
	return arr[::step][:max_samples]


def downsample_heatmap(heatmap: NDArray, max_size: int) -> NDArray:
	"""Downsample 2D heatmap to max_size x max_size."""
	result = heatmap
	if result.shape[0] > max_size:
		step = result.shape[0] // max_size
		result = result[::step, :]
	if result.shape[1] > max_size:
		step = result.shape[1] // max_size
		result = result[:, ::step]
	return result[:max_size, :max_size]


def frame_to_dict(frame, processed=None, config: StreamingConfig | None = None) -> dict:
	"""Convert RadarFrame to serializable dict with size limiting."""
	cfg = config or streaming_config

	detected = []
	for pt in frame.detected_points:
		detected.append(DetectedPoint(
			x=float(pt.x),
			y=float(pt.y),
			z=float(pt.z),
			velocity=float(pt.velocity),
			snr=float(pt.snr) if hasattr(pt, "snr") else 0.0,
		).model_dump())

	# Detect chirp firmware (has chirp-specific TLVs)
	is_chirp = frame.chirp_phase is not None or frame.chirp_complex_fft is not None

	# Derive range_profile: prefer I/Q for chirp firmware, fall back to TLV 2
	range_profile = []
	range_profile_source = None  # 'tlv2', 'iq', or None
	if is_chirp and frame.chirp_complex_fft is not None and len(frame.chirp_complex_fft.iq_data) > 0:
		# Chirp firmware: use I/Q data for range profile (magnitude in dB)
		magnitudes = np.abs(frame.chirp_complex_fft.iq_data)
		range_profile = (20 * np.log10(magnitudes + 1)).tolist()
		range_profile_source = 'iq'
	elif frame.range_profile is not None and len(frame.range_profile) > 0:
		# Standard firmware: use TLV 2
		range_profile = frame.range_profile.tolist()
		range_profile_source = 'tlv2'

	result = {
		"frame_number": frame.header.frame_number if frame.header else 0,
		"timestamp": frame.timestamp,
		"range_profile": range_profile,
		"range_profile_source": range_profile_source,
		"detected_points": detected,
		"is_chirp_firmware": is_chirp,
	}

	# Include range_doppler with size limiting (TLV 5 only, not available with chirp)
	if cfg.include_range_doppler and frame.range_doppler_heatmap is not None:
		heatmap = downsample_heatmap(frame.range_doppler_heatmap, cfg.max_heatmap_size)
		result["range_doppler"] = heatmap.tolist()

	if processed and processed.phase_data is not None:
		# Handle both scalar and array phase_data
		pd = processed.phase_data
		if hasattr(pd, 'ndim') and pd.ndim > 0:
			result["phase"] = float(pd[0]) if pd.size > 0 else 0.0
		else:
			result["phase"] = float(pd)

	return result


def vitals_to_dict(vitals, config: StreamingConfig | None = None) -> dict:
	"""Convert VitalSigns to serializable dict with size limiting."""
	cfg = config or streaming_config

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

	# Add waveforms with size limiting if enabled
	if cfg.include_waveforms:
		if vitals.respiratory_waveform is not None:
			waveform = downsample_array(vitals.respiratory_waveform, cfg.max_waveform_samples)
			result.breathing_waveform = waveform.tolist()
		if vitals.heart_rate_waveform is not None:
			waveform = downsample_array(vitals.heart_rate_waveform, cfg.max_waveform_samples)
			result.heart_waveform = waveform.tolist()

	# Add phase signal with size limiting
	if vitals.phase_signal is not None:
		phase_sig = downsample_array(vitals.phase_signal, cfg.max_phase_signal_samples)
		result.phase_signal = phase_sig.tolist()

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
	last_status_broadcast = 0.0
	status_interval = 1.0  # Broadcast device status at 1 Hz
	vitals_interval = 1.0 / streaming_config.vitals_interval_hz
	profiler = get_profiler()
	app_config = get_config()
	configured_sample_rate = app_config.vitals.sample_rate_hz

	# Frame rate tracking for reconciliation
	frame_rate_tracker = FrameRateTracker(window_size=100, tolerance=0.15)

	# Fallback ChirpVitalsProcessor for when chirp_phase data is present
	# but initial chirp detection failed (extractor is VitalsExtractor)
	chirp_vitals_fallback: ChirpVitalsProcessor | None = None

	# Debug logging state (once per session)
	debug_logged = False

	logger.info(
		f"Starting acquisition loop (vitals_interval={vitals_interval:.2f}s, "
		f"max_heatmap={streaming_config.max_heatmap_size})"
	)

	try:
		while device.state.value == "streaming":
			try:
				frame = sensor.read_frame(timeout=0.1)
				if frame is None:
					await asyncio.sleep(0.01)
					continue

				device.record_frame()
				profiler.frame_start()
				frame_rate_tracker.record(time.time())

				# Debug logging (once per session when AMBIENT_DEBUG is set)
				if AMBIENT_DEBUG and not debug_logged:
					rp_len = len(frame.range_profile) if frame.range_profile is not None else 0
					cfft_len = len(frame.chirp_complex_fft.iq_data) if frame.chirp_complex_fft else 0
					has_phase = frame.chirp_phase is not None
					is_chirp = has_phase or frame.chirp_complex_fft is not None
					logger.info(
						f"Frame TLVs: range_profile={rp_len}, chirp_complex_fft={cfft_len}, "
						f"chirp_phase={'yes' if has_phase else 'no'}, is_chirp={is_chirp}"
					)
					debug_logged = True

				# Process frame
				with profiler.measure("pipeline"):
					processed = pipeline.process(frame)

				# Use firmware vital signs if available, otherwise fall back to estimation
				vitals: VitalSignsData | None = None
				with profiler.measure("vitals"):
					if frame.vital_signs is not None:
						vitals = VitalSignsData.from_firmware(frame.vital_signs, frame.timestamp)
					elif frame.chirp_phase is not None:
						# Use ChirpVitalsProcessor for chirp phase data
						if isinstance(extractor, ChirpVitalsProcessor):
							vitals = extractor.process_frame(frame)
							# Debug: log vitals state periodically
							if AMBIENT_DEBUG and device._frame_count % 100 == 0:
								buf_full = extractor.buffer_fullness
								motion = vitals.motion_detected if vitals else "N/A"
								hr = vitals.heart_rate_bpm if vitals else None
								hr_conf = vitals.heart_rate_confidence if vitals else 0
								rr = vitals.respiratory_rate_bpm if vitals else None
								rr_conf = vitals.respiratory_rate_confidence if vitals else 0
								quality = vitals.signal_quality if vitals else 0
								logger.info(
									f"Vitals debug: buffer={buf_full:.0%}, motion={motion}, "
									f"HR={hr}({hr_conf:.0%}), RR={rr}({rr_conf:.0%}), quality={quality:.0%}"
								)
						else:
							# Chirp phase present but extractor is VitalsExtractor
							# Create fallback processor on first use with configured sample rate
							if chirp_vitals_fallback is None:
								extractor_config = _create_extractor_config()
								chirp_vitals_fallback = ChirpVitalsProcessor(config=extractor_config)
								logger.info(
									f"Created fallback ChirpVitalsProcessor for chirp_phase data "
									f"(sample_rate={extractor_config.sample_rate_hz}Hz)"
								)
							vitals = chirp_vitals_fallback.process_frame(frame)
					elif isinstance(extractor, ChirpVitalsProcessor):
						# ChirpVitalsProcessor but no chirp_phase in this frame - skip vitals
						vitals = None
					else:
						# VitalsExtractor expects ProcessedFrame
						vitals = extractor.process_frame(processed)

				# Write to recording if active
				with profiler.measure("recording"):
					if state.recording.is_recording:
						state.recording.write_frame(frame)
						if vitals and vitals.is_valid():
							state.recording.write_vitals(vitals)

				# Broadcast frame data
				with profiler.measure("broadcast"):
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

					# Broadcast device status at 1 Hz for live dashboard updates
					if (now - last_status_broadcast) >= status_interval:
						# Check frame rate reconciliation and apply to vitals processor
						effective_rate = frame_rate_tracker.check_rate(configured_sample_rate)
						if effective_rate != configured_sample_rate:
							# Apply measured rate to active processor
							if isinstance(extractor, ChirpVitalsProcessor):
								extractor.update_sample_rate(effective_rate)
							elif chirp_vitals_fallback is not None:
								chirp_vitals_fallback.update_sample_rate(effective_rate)

						status = device.get_status()
						status_msg = {
							"type": "device_state",
							"timestamp": now,
							"payload": status.model_dump(mode="json"),
						}
						await ws_manager.broadcast("sensor", status_msg)
						last_status_broadcast = now

				profiler.frame_complete()

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
		# Log fps summary when debug is enabled
		if AMBIENT_DEBUG:
			measured = frame_rate_tracker.measured_rate
			if measured is not None:
				logger.info(
					f"Session fps summary: measured={measured:.1f}Hz, "
					f"configured={configured_sample_rate:.1f}Hz"
				)
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
