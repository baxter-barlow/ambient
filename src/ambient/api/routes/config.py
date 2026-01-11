"""Configuration management API routes."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ambient.sensor.config_parser import parse_config_content, parse_config_file

from ..schemas import ChirpParams, ConfigProfile, FrameParams, StreamingConfigUpdate
from ..state import get_app_state

router = APIRouter(prefix="/api/config", tags=["config"])

# Safe filename pattern - alphanumeric, underscore, hyphen, period only
SAFE_FILENAME_PATTERN = re.compile(r'^[\w\-\.]+$')


def sanitize_filename(filename: str) -> str:
	"""Sanitize a filename to prevent path traversal and other attacks.

	Raises HTTPException if filename is invalid.
	"""
	if not filename:
		raise HTTPException(status_code=400, detail="Filename cannot be empty")

	# Get just the filename (no path components)
	name = Path(filename).name

	# Check for path traversal attempts
	if '..' in name or '/' in name or '\\' in name:
		raise HTTPException(status_code=400, detail="Invalid filename: path traversal not allowed")

	# Validate against safe pattern
	if not SAFE_FILENAME_PATTERN.match(name):
		raise HTTPException(status_code=400, detail="Invalid filename: only alphanumeric, underscore, hyphen, and period allowed")

	return name


def sanitize_config_name(name: str) -> str:
	"""Sanitize a config/profile name to prevent path traversal.

	Raises HTTPException if name is invalid.
	"""
	if not name:
		raise HTTPException(status_code=400, detail="Name cannot be empty")

	# Check for path traversal attempts
	if '..' in name or '/' in name or '\\' in name:
		raise HTTPException(status_code=400, detail="Invalid name: path traversal not allowed")

	# Check for safe pattern (without extension)
	if not re.match(r'^[\w\-]+$', name):
		raise HTTPException(status_code=400, detail="Invalid name: only alphanumeric, underscore, and hyphen allowed")

	return name


# TI Config file schemas
class TIConfigInfo(BaseModel):
	"""Info about a TI .cfg file."""
	name: str
	path: str
	size_bytes: int


class TIConfigParams(BaseModel):
	"""Parsed TI config parameters."""
	name: str
	# Computed parameters
	range_resolution_m: float
	max_range_m: float
	velocity_resolution_mps: float
	max_velocity_mps: float
	frame_rate_hz: float
	num_range_bins: int
	num_doppler_bins: int
	num_virtual_antennas: int
	bandwidth_mhz: float
	# Profile parameters
	start_freq_ghz: float
	adc_samples: int
	chirps_per_frame: int
	frame_period_ms: float
	# Feature flags
	clutter_removal_enabled: bool
	range_doppler_heatmap_enabled: bool
	range_azimuth_heatmap_enabled: bool
	# Raw commands count
	num_commands: int


def get_config_dir() -> Path:
	return Path(os.environ.get("AMBIENT_CONFIG_DIR", "configs"))


def get_profiles_file() -> Path:
	return get_config_dir() / "profiles.json"


async def load_profiles() -> dict[str, ConfigProfile]:
	"""Load saved config profiles."""
	path = get_profiles_file()
	if not path.exists():
		return {}
	try:
		async with aiofiles.open(path) as f:
			data = json.loads(await f.read())
		return {name: ConfigProfile(**profile) for name, profile in data.items()}
	except Exception:
		return {}


async def save_profiles(profiles: dict[str, ConfigProfile]):
	"""Save config profiles."""
	path = get_profiles_file()
	path.parent.mkdir(exist_ok=True)
	async with aiofiles.open(path, "w") as f:
		await f.write(json.dumps({name: p.model_dump() for name, p in profiles.items()}, indent=2))


@router.get("/profiles", response_model=list[ConfigProfile])
async def list_profiles():
	"""List all saved configuration profiles."""
	profiles = await load_profiles()

	# Add default profile if not exists
	if "default" not in profiles:
		profiles["default"] = ConfigProfile(
			name="default",
			description="Default vital signs configuration",
			chirp=ChirpParams(),
			frame=FrameParams(),
		)

	return list(profiles.values())


@router.get("/profiles/{name}", response_model=ConfigProfile)
async def get_profile(name: str):
	"""Get a specific configuration profile."""
	profiles = await load_profiles()
	if name not in profiles:
		if name == "default":
			return ConfigProfile(
				name="default",
				description="Default vital signs configuration",
				chirp=ChirpParams(),
				frame=FrameParams(),
			)
		raise HTTPException(status_code=404, detail="Profile not found")
	return profiles[name]


@router.post("/profiles", response_model=ConfigProfile)
async def create_profile(profile: ConfigProfile):
	"""Create a new configuration profile."""
	profiles = await load_profiles()
	if profile.name in profiles:
		raise HTTPException(status_code=400, detail="Profile already exists")
	profiles[profile.name] = profile
	await save_profiles(profiles)
	return profile


@router.put("/profiles/{name}", response_model=ConfigProfile)
async def update_profile(name: str, profile: ConfigProfile):
	"""Update an existing configuration profile."""
	profiles = await load_profiles()
	profile.name = name  # Ensure name matches
	profiles[name] = profile
	await save_profiles(profiles)
	return profile


@router.delete("/profiles/{name}")
async def delete_profile(name: str):
	"""Delete a configuration profile."""
	if name == "default":
		raise HTTPException(status_code=400, detail="Cannot delete default profile")
	profiles = await load_profiles()
	if name not in profiles:
		raise HTTPException(status_code=404, detail="Profile not found")
	del profiles[name]
	await save_profiles(profiles)
	return {"deleted": name}


@router.post("/flash")
async def flash_config(profile_name: str = "default"):
	"""Flash configuration to device."""
	state = get_app_state()

	if state.device.state.value not in ("configuring", "streaming"):
		raise HTTPException(status_code=400, detail="Device must be connected to flash config")

	profiles = await load_profiles()
	if profile_name not in profiles and profile_name != "default":
		raise HTTPException(status_code=404, detail="Profile not found")

	# Get the profile to flash
	if profile_name == "default":
		profile = ConfigProfile(
			name="default",
			description="Default vital signs configuration",
			chirp=ChirpParams(),
			frame=FrameParams(),
		)
	else:
		profile = profiles[profile_name]

	# Convert profile to ChirpConfig commands
	from ambient.sensor.config import ChirpConfig, FrameConfig, ProfileConfig

	chirp_config = ChirpConfig(
		profile=ProfileConfig(
			start_freq_ghz=profile.chirp.start_freq_ghz,
			idle_time_us=profile.chirp.idle_time_us,
			ramp_end_time_us=profile.chirp.ramp_end_time_us,
			freq_slope_mhz_us=profile.chirp.bandwidth_mhz / profile.chirp.ramp_end_time_us,
			adc_samples=profile.chirp.adc_samples,
			sample_rate_ksps=profile.chirp.sample_rate_ksps,
			rx_gain_db=profile.chirp.rx_gain_db,
		),
		frame=FrameConfig(
			num_loops=profile.frame.chirps_per_frame,
			frame_period_ms=profile.frame.frame_period_ms,
		),
	)

	# Stop, reconfigure with profile parameters, and restart
	sensor = state.device.sensor
	if sensor:
		sensor.stop()
		sensor.configure(chirp_config)
		sensor.start()
		state.device._config_name = profile_name

	return {"status": "ok", "profile": profile_name}


@router.get("/current")
async def get_current_config():
	"""Get currently active configuration."""
	state = get_app_state()
	return {
		"profile_name": state.device._config_name or "default",
		"state": state.device.state.value,
	}


@router.get("/validate")
async def validate_config():
	"""Validate the current application configuration.

	Returns validation errors if any config values are invalid.
	Useful for checking config before starting services.
	"""
	from ambient.config import get_config

	config = get_config()
	errors = config.validate()

	return {
		"valid": len(errors) == 0,
		"errors": errors,
		"config": {
			"sensor": {
				"cli_port": config.sensor.cli_port,
				"data_port": config.sensor.data_port,
				"cli_baud": config.sensor.cli_baud,
				"data_baud": config.sensor.data_baud,
				"auto_reconnect": config.sensor.auto_reconnect,
			},
			"api": {
				"host": config.api.host,
				"port": config.api.port,
				"log_level": config.api.log_level,
			},
			"streaming": {
				"max_queue_size": config.streaming.max_queue_size,
				"drop_policy": config.streaming.drop_policy,
				"max_heatmap_size": config.streaming.max_heatmap_size,
				"max_waveform_samples": config.streaming.max_waveform_samples,
				"vitals_interval_hz": config.streaming.vitals_interval_hz,
				"include_range_doppler": config.streaming.include_range_doppler,
				"include_waveforms": config.streaming.include_waveforms,
			},
			"performance": {
				"enabled": config.performance.enabled,
				"log_interval_frames": config.performance.log_interval_frames,
				"sample_rate": config.performance.sample_rate,
			},
			"chirp": {
				"enabled": config.chirp.enabled,
				"target_range_min_m": config.chirp.target_range_min_m,
				"target_range_max_m": config.chirp.target_range_max_m,
				"output_mode": config.chirp.output_mode,
			},
		},
	}


@router.get("/streaming")
async def get_streaming_config():
	"""Get current streaming configuration."""
	from ..tasks import streaming_config

	return {
		"include_range_doppler": streaming_config.include_range_doppler,
		"include_waveforms": streaming_config.include_waveforms,
		"max_heatmap_size": streaming_config.max_heatmap_size,
		"max_waveform_samples": streaming_config.max_waveform_samples,
		"max_phase_signal_samples": streaming_config.max_phase_signal_samples,
		"vitals_interval_hz": streaming_config.vitals_interval_hz,
	}


@router.put("/streaming")
async def update_streaming_config(update: StreamingConfigUpdate):
	"""Update streaming configuration at runtime.

	Changes take effect immediately without server restart.
	"""
	from ..tasks import streaming_config

	if update.include_range_doppler is not None:
		streaming_config.include_range_doppler = update.include_range_doppler
	if update.include_waveforms is not None:
		streaming_config.include_waveforms = update.include_waveforms
	if update.max_heatmap_size is not None:
		streaming_config.max_heatmap_size = update.max_heatmap_size
	if update.max_waveform_samples is not None:
		streaming_config.max_waveform_samples = update.max_waveform_samples
	if update.vitals_interval_hz is not None:
		streaming_config.vitals_interval_hz = update.vitals_interval_hz

	return {
		"status": "updated",
		"streaming": {
			"include_range_doppler": streaming_config.include_range_doppler,
			"include_waveforms": streaming_config.include_waveforms,
			"max_heatmap_size": streaming_config.max_heatmap_size,
			"max_waveform_samples": streaming_config.max_waveform_samples,
			"vitals_interval_hz": streaming_config.vitals_interval_hz,
		},
	}


# TI Visualizer Config Compatibility Endpoints
@router.get("/ti-configs", response_model=list[TIConfigInfo])
async def list_ti_configs():
	"""List all TI .cfg files in the config directory."""
	config_dir = get_config_dir()
	configs = []

	if config_dir.exists():
		for cfg_file in config_dir.glob("*.cfg"):
			configs.append(
				TIConfigInfo(
					name=cfg_file.stem,
					path=str(cfg_file),
					size_bytes=cfg_file.stat().st_size,
				)
			)

	return sorted(configs, key=lambda c: c.name)


@router.get("/ti-configs/{name}", response_model=TIConfigParams)
async def get_ti_config(name: str):
	"""Get parsed parameters from a TI .cfg file."""
	safe_name = sanitize_config_name(name)
	config_dir = get_config_dir()
	cfg_path = config_dir / f"{safe_name}.cfg"

	if not cfg_path.exists():
		raise HTTPException(status_code=404, detail=f"Config file not found: {name}.cfg")

	try:
		parsed = parse_config_file(cfg_path)
		return TIConfigParams(
			name=name,
			range_resolution_m=parsed.range_resolution_m,
			max_range_m=parsed.max_range_m,
			velocity_resolution_mps=parsed.velocity_resolution_mps,
			max_velocity_mps=parsed.max_velocity_mps,
			frame_rate_hz=parsed.frame_rate_hz,
			num_range_bins=parsed.num_range_bins,
			num_doppler_bins=parsed.num_doppler_bins,
			num_virtual_antennas=parsed.num_virtual_antennas,
			bandwidth_mhz=parsed.profile.bandwidth_mhz,
			start_freq_ghz=parsed.profile.start_freq_ghz,
			adc_samples=parsed.profile.adc_samples,
			chirps_per_frame=parsed.frame.num_chirps_per_frame,
			frame_period_ms=parsed.frame.frame_period_ms,
			clutter_removal_enabled=bool(parsed.clutter_removal.enabled),
			range_doppler_heatmap_enabled=bool(parsed.gui_monitor.range_doppler_heatmap),
			range_azimuth_heatmap_enabled=bool(parsed.gui_monitor.range_azimuth_heatmap),
			num_commands=len(parsed.raw_commands),
		)
	except Exception as e:
		raise HTTPException(status_code=400, detail=f"Failed to parse config: {e}")


@router.post("/ti-configs/upload")
async def upload_ti_config(file: UploadFile = File(...)):
	"""Upload a new TI .cfg file."""
	if not file.filename or not file.filename.endswith(".cfg"):
		raise HTTPException(status_code=400, detail="File must have .cfg extension")

	# Sanitize filename to prevent path traversal
	safe_filename = sanitize_filename(file.filename)
	if not safe_filename.endswith(".cfg"):
		raise HTTPException(status_code=400, detail="File must have .cfg extension")

	config_dir = get_config_dir()
	config_dir.mkdir(exist_ok=True)

	target_path = config_dir / safe_filename
	content = await file.read()

	# Validate by parsing
	try:
		content_str = content.decode("utf-8")
		parsed = parse_config_content(content_str)
	except Exception as e:
		raise HTTPException(status_code=400, detail=f"Invalid config file: {e}")

	# Save the file
	async with aiofiles.open(target_path, "wb") as f:
		await f.write(content)

	return {
		"status": "uploaded",
		"name": target_path.stem,
		"path": str(target_path),
		"num_commands": len(parsed.raw_commands),
	}


@router.post("/ti-configs/{name}/parse")
async def parse_ti_config(name: str):
	"""Parse a TI .cfg file and return all extracted parameters."""
	safe_name = sanitize_config_name(name)
	config_dir = get_config_dir()
	cfg_path = config_dir / f"{safe_name}.cfg"

	if not cfg_path.exists():
		raise HTTPException(status_code=404, detail=f"Config file not found: {name}.cfg")

	try:
		parsed = parse_config_file(cfg_path)
		return {
			"name": name,
			"computed": parsed.to_dict(),
			"channel": {
				"rx_channel_en": parsed.channel.rx_channel_en,
				"tx_channel_en": parsed.channel.tx_channel_en,
				"num_rx": parsed.channel.num_rx_channels,
				"num_tx": parsed.channel.num_tx_channels,
			},
			"profile": {
				"profile_id": parsed.profile.profile_id,
				"start_freq_ghz": parsed.profile.start_freq_ghz,
				"idle_time_us": parsed.profile.idle_time_us,
				"ramp_end_time_us": parsed.profile.ramp_end_time_us,
				"freq_slope_mhz_us": parsed.profile.freq_slope_mhz_us,
				"adc_samples": parsed.profile.adc_samples,
				"sample_rate_ksps": parsed.profile.sample_rate_ksps,
				"rx_gain_db": parsed.profile.rx_gain_db,
				"bandwidth_mhz": parsed.profile.bandwidth_mhz,
			},
			"frame": {
				"chirp_start_idx": parsed.frame.chirp_start_idx,
				"chirp_end_idx": parsed.frame.chirp_end_idx,
				"num_loops": parsed.frame.num_loops,
				"num_frames": parsed.frame.num_frames,
				"frame_period_ms": parsed.frame.frame_period_ms,
				"frame_rate_hz": parsed.frame.frame_rate_hz,
			},
			"gui_monitor": {
				"detected_objects": parsed.gui_monitor.detected_objects,
				"log_mag_range": parsed.gui_monitor.log_mag_range,
				"range_doppler_heatmap": parsed.gui_monitor.range_doppler_heatmap,
				"range_azimuth_heatmap": parsed.gui_monitor.range_azimuth_heatmap,
			},
			"cfar": {
				"range_mode": parsed.cfar_range.mode,
				"range_threshold_db": parsed.cfar_range.threshold_scale_db,
				"doppler_mode": parsed.cfar_doppler.mode if parsed.cfar_doppler else None,
				"doppler_threshold_db": parsed.cfar_doppler.threshold_scale_db if parsed.cfar_doppler else None,
			},
			"clutter_removal": {
				"enabled": bool(parsed.clutter_removal.enabled),
			},
			"aoa_fov": {
				"min_azimuth_deg": parsed.aoa_fov.min_azimuth_deg,
				"max_azimuth_deg": parsed.aoa_fov.max_azimuth_deg,
				"min_elevation_deg": parsed.aoa_fov.min_elevation_deg,
				"max_elevation_deg": parsed.aoa_fov.max_elevation_deg,
			},
			"raw_commands": parsed.raw_commands,
		}
	except Exception as e:
		raise HTTPException(status_code=400, detail=f"Failed to parse config: {e}")


@router.post("/ti-configs/{name}/apply")
async def apply_ti_config(name: str):
	"""Apply a TI .cfg file to the radar device.

	The device must be connected. This will stop the sensor, send all
	commands from the config file, and restart the sensor.
	"""
	safe_name = sanitize_config_name(name)
	state = get_app_state()

	if state.device.state.value not in ("configuring", "streaming"):
		raise HTTPException(
			status_code=400,
			detail="Device must be connected to apply config",
		)

	config_dir = get_config_dir()
	cfg_path = config_dir / f"{safe_name}.cfg"

	if not cfg_path.exists():
		raise HTTPException(status_code=404, detail=f"Config file not found: {name}.cfg")

	sensor = state.device.sensor
	if not sensor:
		raise HTTPException(status_code=400, detail="No sensor available")

	try:
		# Load the raw commands
		from ambient.sensor.config import load_config_file

		commands = load_config_file(cfg_path)

		# Stop sensor, send commands, start
		sensor.stop()

		# Send each command (excluding sensorStart/sensorStop)
		for cmd in commands:
			if cmd.strip() and not cmd.startswith("sensorStart") and not cmd.startswith("sensorStop"):
				response = sensor.send_command(cmd)
				if "Error" in response:
					raise HTTPException(
						status_code=400,
						detail=f"Command failed: {cmd} -> {response}",
					)

		# Start the sensor
		sensor.start()
		state.device._config_name = name

		return {
			"status": "applied",
			"config_name": name,
			"commands_sent": len(commands),
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to apply config: {e}")


@router.delete("/ti-configs/{name}")
async def delete_ti_config(name: str):
	"""Delete a TI .cfg file."""
	safe_name = sanitize_config_name(name)
	config_dir = get_config_dir()
	cfg_path = config_dir / f"{safe_name}.cfg"

	# Protect default configs
	if safe_name in ("working", "vital_signs", "vital_signs_chirp"):
		raise HTTPException(status_code=400, detail="Cannot delete built-in config")

	if not cfg_path.exists():
		raise HTTPException(status_code=404, detail=f"Config file not found: {name}.cfg")

	cfg_path.unlink()
	return {"status": "deleted", "name": name}
