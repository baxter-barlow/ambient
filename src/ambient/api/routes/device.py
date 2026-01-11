"""Device control API routes."""
from __future__ import annotations

import logging

import serial
from fastapi import APIRouter, HTTPException

from ...sensor.ports import list_serial_ports
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
	"""List available serial ports.

	Works cross-platform: Linux and macOS.
	Returns TI radar devices first if detected.
	"""
	ports = []

	for port_info in list_serial_ports():
		ports.append(SerialPort(
			device=port_info.device,
			description=port_info.description,
		))

	# Sort TI devices first, then by device path
	return sorted(ports, key=lambda p: (not any(x in p.description for x in ["XDS", "TI", "Texas"]), p.device))


@router.post("/verify-ports", response_model=PortVerifyResult)
async def verify_ports(request: PortVerifyRequest):
	"""Verify serial ports before connecting."""
	cli_result = PortStatus(path=request.cli_port, status="unknown", details="")
	data_result = PortStatus(path=request.data_port, status="unknown", details="")

	# Test CLI port
	import time
	ser = None
	try:
		ser = serial.Serial(request.cli_port, 115200, timeout=2)
		ser.reset_input_buffer()
		ser.write(b"version\n")
		time.sleep(0.3)
		response = ser.read(ser.in_waiting or 100)

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
	finally:
		if ser is not None:
			try:
				ser.close()
			except Exception:
				pass

	# Test Data port
	ser = None
	try:
		ser = serial.Serial(request.data_port, 921600, timeout=1)
		data_result.status = "ok"
		data_result.details = "Port accessible at 921600 baud"
	except serial.SerialException as e:
		data_result.status = "error"
		data_result.details = str(e)
	except Exception as e:
		data_result.status = "error"
		data_result.details = f"Unexpected error: {e}"
	finally:
		if ser is not None:
			try:
				ser.close()
			except Exception:
				pass

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
		"firmware": None,
	}

	# Get info about last processed data
	if device.pipeline and hasattr(device.pipeline, '_phase_history'):
		result["buffers"]["phase_history_length"] = len(device.pipeline._phase_history)

	if device.extractor:
		result["buffers"]["phase_buffer_length"] = len(device.extractor._phase_buffer)
		result["buffers"]["buffer_fullness"] = device.extractor.buffer_fullness

	# Get firmware info if connected
	if device.sensor and device.sensor.is_connected:
		try:
			result["firmware"] = device.sensor.detect_firmware()
		except Exception as e:
			result["firmware"] = {"type": "unknown", "error": str(e)}

	return result


@router.get("/firmware")
async def get_firmware_info():
	"""Get detected firmware information."""
	state = get_app_state()
	device = state.device

	if not device.sensor or not device.sensor.is_connected:
		raise HTTPException(status_code=400, detail="Device not connected")

	try:
		return device.sensor.detect_firmware()
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to detect firmware: {e}")


@router.get("/metrics")
async def get_performance_metrics():
	"""Get performance profiling metrics including latency and queue stats.

	Returns:
		- timing: Latency stats (mean, p50, p95, p99) for pipeline stages
		- queues: Queue depth and drop stats for each queue
		- frames: Total frame count and dropped frames
	"""
	from ambient.utils.profiler import get_profiler

	profiler = get_profiler()
	stats = profiler.get_stats()

	# Also get WebSocket manager stats
	from ..ws.manager import get_ws_manager

	manager = get_ws_manager()
	ws_stats = manager.get_all_metrics() if manager else {}

	return {
		"enabled": profiler.enabled,
		"frame_count": stats.get("frame_count", 0),
		"sampled_count": stats.get("sampled_count", 0),
		"dropped_frames": stats.get("dropped_frames", 0),
		"sample_rate": stats.get("sample_rate", 1.0),
		"timing": stats.get("timing", {}),
		"queues": stats.get("queues", {}),
		"websocket": ws_stats,
	}


@router.post("/metrics/reset")
async def reset_metrics():
	"""Reset all performance metrics."""
	from ambient.utils.profiler import get_profiler

	profiler = get_profiler()
	profiler.reset()
	return {"status": "ok", "message": "Metrics reset"}
