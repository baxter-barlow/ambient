"""Pydantic schemas for API requests/responses."""
from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeviceState(str, Enum):
	DISCONNECTED = "disconnected"
	CONNECTING = "connecting"
	CONFIGURING = "configuring"
	STREAMING = "streaming"
	ERROR = "error"


class DeviceStatus(BaseModel):
	state: DeviceState
	cli_port: str | None = None
	data_port: str | None = None
	frame_rate: float = 0.0
	frame_count: int = 0
	dropped_frames: int = 0
	buffer_usage: float = 0.0
	error: str | None = None
	config_name: str | None = None


class ConnectRequest(BaseModel):
	cli_port: str = "/dev/ttyUSB0"
	data_port: str = "/dev/ttyUSB1"
	config: str | None = None  # config profile name or path


class PortVerifyRequest(BaseModel):
	cli_port: str
	data_port: str


class PortStatus(BaseModel):
	path: str
	status: str  # ok, warning, error, unknown
	details: str


class PortVerifyResult(BaseModel):
	cli_port: PortStatus
	data_port: PortStatus
	overall: str  # pass, warning, fail


class SerialPort(BaseModel):
	device: str
	description: str


class DetectedPoint(BaseModel):
	x: float
	y: float
	z: float
	velocity: float
	snr: float = 0.0


class SensorFrame(BaseModel):
	frame_number: int
	timestamp: float
	range_profile: list[float]
	range_doppler: list[list[float]] | None = None
	detected_points: list[DetectedPoint]
	phase: float | None = None


class VitalSigns(BaseModel):
	heart_rate_bpm: float | None = None
	heart_rate_confidence: float = 0.0
	respiratory_rate_bpm: float | None = None
	respiratory_rate_confidence: float = 0.0
	signal_quality: float = 0.0
	motion_detected: bool = False
	source: str = "estimated"  # "firmware", "estimated", or "chirp"
	breathing_waveform: list[float] | None = None
	heart_waveform: list[float] | None = None
	phase_signal: list[float] | None = None  # Raw phase signal for visualization
	unwrapped_phase: float | None = None
	# Enhanced quality metrics
	hr_snr_db: float = 0.0
	rr_snr_db: float = 0.0
	phase_stability: float = 0.0


class WSMessage(BaseModel):
	"""WebSocket message envelope."""
	type: str
	timestamp: float = Field(default_factory=time.time)
	payload: dict[str, Any]


# Recording schemas
class RecordingInfo(BaseModel):
	id: str
	name: str
	path: str
	format: str  # h5, parquet
	created: float
	duration: float | None = None
	frame_count: int = 0
	size_bytes: int = 0


class RecordingStartRequest(BaseModel):
	name: str
	format: str = "h5"  # h5 or parquet


class RecordingStatus(BaseModel):
	is_recording: bool
	recording_id: str | None = None
	name: str | None = None
	duration: float = 0.0
	frame_count: int = 0


# Config schemas
class ChirpParams(BaseModel):
	start_freq_ghz: float = 60.0
	bandwidth_mhz: float = 4000.0
	idle_time_us: float = 7.0
	ramp_end_time_us: float = 60.0
	adc_samples: int = 256
	sample_rate_ksps: int = 10000
	rx_gain_db: int = 30


class FrameParams(BaseModel):
	chirps_per_frame: int = 64
	frame_period_ms: float = 50.0  # 20 Hz


class ConfigProfile(BaseModel):
	name: str
	description: str = ""
	chirp: ChirpParams = Field(default_factory=ChirpParams)
	frame: FrameParams = Field(default_factory=FrameParams)


# Algorithm params
class AlgorithmParams(BaseModel):
	hr_low_hz: float = 0.8
	hr_high_hz: float = 3.0
	rr_low_hz: float = 0.1
	rr_high_hz: float = 0.6
	window_seconds: float = 10.0
	clutter_method: str = "mti"  # mti, moving_avg, none


class ParamPreset(BaseModel):
	name: str
	description: str = ""
	params: AlgorithmParams


# Test schemas
class TestModule(BaseModel):
	name: str
	path: str
	hardware_required: bool = False


class TestRunRequest(BaseModel):
	modules: list[str] = []  # empty = all
	include_hardware: bool = False


class TestResult(BaseModel):
	module: str
	passed: int
	failed: int
	skipped: int
	duration: float
	output: str


# Log schemas
class LogEntry(BaseModel):
	timestamp: float
	level: str
	logger: str
	message: str
	extra: dict[str, Any] = Field(default_factory=dict)
