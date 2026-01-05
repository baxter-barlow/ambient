"""Sensor data WebSocket endpoint."""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..state import get_app_state
from .manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/sensor")
async def sensor_websocket(websocket: WebSocket):
	"""WebSocket endpoint for sensor data streaming."""
	await manager.connect(websocket, "sensor")

	state = get_app_state()

	# Send current device state
	status = state.device.get_status()
	await manager.send_to(websocket, {
		"type": "device_state",
		"payload": status.model_dump(),
	})

	try:
		while True:
			# Keep connection alive, handle incoming messages
			data = await websocket.receive_json()

			# Handle client messages (e.g., pause/resume, time window)
			msg_type = data.get("type")
			if msg_type == "ping":
				await manager.send_to(websocket, {"type": "pong"})
			elif msg_type == "get_status":
				status = state.device.get_status()
				await manager.send_to(websocket, {
					"type": "device_state",
					"payload": status.model_dump(),
				})

	except WebSocketDisconnect:
		logger.info("Sensor WebSocket disconnected")
	except Exception as e:
		logger.error(f"Sensor WebSocket error: {e}")
	finally:
		await manager.disconnect(websocket, "sensor")
