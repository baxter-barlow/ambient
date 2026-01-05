"""Device control API routes."""
from __future__ import annotations

import glob
import logging

import serial
from fastapi import APIRouter, HTTPException

from ..schemas import ConnectRequest, DeviceStatus, PortStatus, PortVerifyRequest, PortVerifyResult, SerialPort
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


@router.post("/verify-ports", response_model=PortVerifyResult)
async def verify_ports(request: PortVerifyRequest):
	"""Verify serial ports before connecting."""
	cli_result = PortStatus(path=request.cli_port, status="unknown", details="")
	data_result = PortStatus(path=request.data_port, status="unknown", details="")

	# Test CLI port
	try:
		ser = serial.Serial(request.cli_port, 115200, timeout=2)
		ser.reset_input_buffer()
		ser.write(b"version\n")
		import time
		time.sleep(0.3)
		response = ser.read(ser.in_waiting or 100)
		ser.close()

		if b"mmWave" in response or b"IWR" in response or b"SDK" in response:
			cli_result.status = "ok"
			cli_result.details = response.decode(errors="ignore").strip()[:80]
		elif response:
			cli_result.status = "warning"
			cli_result.details = f"Unexpected response: {response.decode(errors='ignore')[:40]}"
		else:
			cli_result.status = "warning"
			cli_result.details = "Port opened but no response to version query"
	except serial.SerialException as e:
		cli_result.status = "error"
		cli_result.details = str(e)
	except Exception as e:
		cli_result.status = "error"
		cli_result.details = f"Unexpected error: {e}"

	# Test Data port
	try:
		ser = serial.Serial(request.data_port, 921600, timeout=1)
		ser.close()
		data_result.status = "ok"
		data_result.details = "Port accessible at 921600 baud"
	except serial.SerialException as e:
		data_result.status = "error"
		data_result.details = str(e)
	except Exception as e:
		data_result.status = "error"
		data_result.details = f"Unexpected error: {e}"

	# Determine overall status
	if cli_result.status == "ok" and data_result.status == "ok":
		overall = "pass"
	elif cli_result.status == "error" or data_result.status == "error":
		overall = "fail"
	else:
		overall = "warning"

	return PortVerifyResult(cli_port=cli_result, data_port=data_result, overall=overall)


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


@router.get("/debug/signal-stats")
async def signal_stats():
	"""Return current signal statistics for debugging."""
	state = get_app_state()
	device = state.device

	result = {
		"device_state": device.state.value,
		"last_frame": None,
		"buffers": {
			"phase_history_length": 0,
			"frames_processed": device._frame_count,
		},
		"vitals": None,
	}

	# Get info about last processed data
	if device.pipeline and hasattr(device.pipeline, '_phase_history'):
		result["buffers"]["phase_history_length"] = len(device.pipeline._phase_history)

	if device.extractor:
		result["buffers"]["phase_buffer_length"] = len(device.extractor._phase_buffer)
		result["buffers"]["buffer_fullness"] = device.extractor.buffer_fullness

	return result
