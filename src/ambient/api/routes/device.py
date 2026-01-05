"""Device control API routes."""
from __future__ import annotations

import glob
import logging

from fastapi import APIRouter, HTTPException

from ..schemas import ConnectRequest, DeviceStatus, SerialPort
from ..state import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/device", tags=["device"])


@router.get("/status", response_model=DeviceStatus)
async def get_status():
	"""Get current device status."""
	state = get_app_state()
	return state.device.get_status()


@router.get("/ports", response_model=list[SerialPort])
async def list_ports():
	"""List available serial ports."""
	ports = []

	# Check /dev/ttyUSB* and /dev/ttyACM*
	for pattern in ["/dev/ttyUSB*", "/dev/ttyACM*"]:
		for path in sorted(glob.glob(pattern)):
			ports.append(SerialPort(device=path, description=path.split("/")[-1]))

	return ports


@router.post("/connect", response_model=DeviceStatus)
async def connect(request: ConnectRequest):
	"""Connect to radar sensor."""
	state = get_app_state()

	if state.device.state.value not in ("disconnected", "error"):
		raise HTTPException(status_code=400, detail=f"Cannot connect from state: {state.device.state.value}")

	success = await state.device.connect(
		cli_port=request.cli_port,
		data_port=request.data_port,
		config_name=request.config,
	)

	if not success:
		status = state.device.get_status()
		raise HTTPException(status_code=500, detail=status.error or "Connection failed")

	return state.device.get_status()


@router.post("/disconnect", response_model=DeviceStatus)
async def disconnect():
	"""Disconnect from radar sensor."""
	state = get_app_state()
	await state.device.disconnect()
	return state.device.get_status()


@router.post("/stop", response_model=DeviceStatus)
async def emergency_stop():
	"""Emergency stop - immediately halt all acquisition."""
	state = get_app_state()
	await state.device.emergency_stop()
	return state.device.get_status()
