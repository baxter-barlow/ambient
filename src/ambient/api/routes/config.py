"""Configuration management API routes."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import ConfigProfile, ChirpParams, FrameParams
from ..state import get_app_state

router = APIRouter(prefix="/api/config", tags=["config"])


def get_config_dir() -> Path:
	return Path(os.environ.get("AMBIENT_CONFIG_DIR", "configs"))


def get_profiles_file() -> Path:
	return get_config_dir() / "profiles.json"


def load_profiles() -> dict[str, ConfigProfile]:
	"""Load saved config profiles."""
	path = get_profiles_file()
	if not path.exists():
		return {}
	try:
		with open(path) as f:
			data = json.load(f)
		return {name: ConfigProfile(**profile) for name, profile in data.items()}
	except Exception:
		return {}


def save_profiles(profiles: dict[str, ConfigProfile]):
	"""Save config profiles."""
	path = get_profiles_file()
	path.parent.mkdir(exist_ok=True)
	with open(path, "w") as f:
		json.dump({name: p.model_dump() for name, p in profiles.items()}, f, indent=2)


@router.get("/profiles", response_model=list[ConfigProfile])
async def list_profiles():
	"""List all saved configuration profiles."""
	profiles = load_profiles()

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
	profiles = load_profiles()
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
	profiles = load_profiles()
	if profile.name in profiles:
		raise HTTPException(status_code=400, detail="Profile already exists")
	profiles[profile.name] = profile
	save_profiles(profiles)
	return profile


@router.put("/profiles/{name}", response_model=ConfigProfile)
async def update_profile(name: str, profile: ConfigProfile):
	"""Update an existing configuration profile."""
	profiles = load_profiles()
	profile.name = name  # Ensure name matches
	profiles[name] = profile
	save_profiles(profiles)
	return profile


@router.delete("/profiles/{name}")
async def delete_profile(name: str):
	"""Delete a configuration profile."""
	if name == "default":
		raise HTTPException(status_code=400, detail="Cannot delete default profile")
	profiles = load_profiles()
	if name not in profiles:
		raise HTTPException(status_code=404, detail="Profile not found")
	del profiles[name]
	save_profiles(profiles)
	return {"deleted": name}


@router.post("/flash")
async def flash_config(profile_name: str = "default"):
	"""Flash configuration to device."""
	state = get_app_state()

	if state.device.state.value not in ("configuring", "streaming"):
		raise HTTPException(status_code=400, detail="Device must be connected to flash config")

	profiles = load_profiles()
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
	from ambient.sensor.config import ChirpConfig, ProfileConfig, FrameConfig

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

	# Stop, reconfigure, and restart
	sensor = state.device.sensor
	if sensor:
		sensor.send_command("sensorStop")
		sensor.configure(chirp_config)
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
