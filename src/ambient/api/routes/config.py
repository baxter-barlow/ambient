"""Configuration management API routes."""
from __future__ import annotations

import json
import os
from pathlib import Path

import aiofiles
from fastapi import APIRouter, HTTPException

from ..schemas import ChirpParams, ConfigProfile, FrameParams
from ..state import get_app_state

router = APIRouter(prefix="/api/config", tags=["config"])


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

	# Stop, reconfigure, and restart (use methods to reset buffers and state)
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
