"""Algorithm parameter management API routes."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import AlgorithmParams, ParamPreset
from ..state import get_app_state

router = APIRouter(prefix="/api/params", tags=["params"])


def get_presets_file() -> Path:
	config_dir = Path(os.environ.get("AMBIENT_CONFIG_DIR", "configs"))
	return config_dir / "param_presets.json"


def load_presets() -> dict[str, ParamPreset]:
	"""Load saved parameter presets."""
	path = get_presets_file()
	if not path.exists():
		return {}
	try:
		with open(path) as f:
			data = json.load(f)
		return {name: ParamPreset(**preset) for name, preset in data.items()}
	except Exception:
		return {}


def save_presets(presets: dict[str, ParamPreset]):
	"""Save parameter presets."""
	path = get_presets_file()
	path.parent.mkdir(exist_ok=True)
	with open(path, "w") as f:
		json.dump({name: p.model_dump() for name, p in presets.items()}, f, indent=2)


@router.get("/presets", response_model=list[ParamPreset])
async def list_presets():
	"""List all saved parameter presets."""
	presets = load_presets()

	# Add default preset
	if "default" not in presets:
		presets["default"] = ParamPreset(
			name="default",
			description="Default vital signs parameters",
			params=AlgorithmParams(),
		)

	return list(presets.values())


@router.get("/current", response_model=AlgorithmParams)
async def get_current_params():
	"""Get current algorithm parameters."""
	state = get_app_state()
	return state.algorithm_params


@router.put("/current", response_model=AlgorithmParams)
async def update_current_params(params: AlgorithmParams):
	"""Update current algorithm parameters (live)."""
	state = get_app_state()
	state.algorithm_params = params

	# Update extractor if running
	if state.device.extractor:
		from ambient.vitals.extractor import VitalsConfig
		new_config = VitalsConfig(
			sample_rate_hz=state.device.extractor.config.sample_rate_hz,
			window_seconds=params.window_seconds,
			hr_freq_min_hz=params.hr_low_hz,
			hr_freq_max_hz=params.hr_high_hz,
			rr_freq_min_hz=params.rr_low_hz,
			rr_freq_max_hz=params.rr_high_hz,
		)
		state.device.extractor.config = new_config
		state.device.extractor._buffer_size = int(new_config.window_seconds * new_config.sample_rate_hz)
		state.device.extractor._hr_filter._low_freq_hz = params.hr_low_hz
		state.device.extractor._hr_filter._high_freq_hz = params.hr_high_hz
		state.device.extractor._rr_filter._low_freq_hz = params.rr_low_hz
		state.device.extractor._rr_filter._high_freq_hz = params.rr_high_hz

	# Update pipeline clutter method if changed
	if state.device.pipeline and params.clutter_method != state.device.pipeline.config.clutter_removal:
		state.device.pipeline.update_config(clutter_removal=params.clutter_method)

	return state.algorithm_params


@router.post("/presets", response_model=ParamPreset)
async def create_preset(preset: ParamPreset):
	"""Save current parameters as a preset."""
	presets = load_presets()
	if preset.name in presets:
		raise HTTPException(status_code=400, detail="Preset already exists")
	presets[preset.name] = preset
	save_presets(presets)
	return preset


@router.delete("/presets/{name}")
async def delete_preset(name: str):
	"""Delete a parameter preset."""
	if name == "default":
		raise HTTPException(status_code=400, detail="Cannot delete default preset")
	presets = load_presets()
	if name not in presets:
		raise HTTPException(status_code=404, detail="Preset not found")
	del presets[name]
	save_presets(presets)
	return {"deleted": name}


@router.post("/presets/{name}/apply", response_model=AlgorithmParams)
async def apply_preset(name: str):
	"""Apply a preset to current parameters."""
	presets = load_presets()
	if name not in presets and name != "default":
		raise HTTPException(status_code=404, detail="Preset not found")

	if name == "default":
		params = AlgorithmParams()
	else:
		params = presets[name].params

	state = get_app_state()
	state.algorithm_params = params
	return params
