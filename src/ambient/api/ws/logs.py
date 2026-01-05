"""Log streaming WebSocket endpoint."""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..state import get_app_state
from .manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


class WebSocketLogHandler(logging.Handler):
	"""Log handler that broadcasts to WebSocket clients."""

	def __init__(self, ws_manager, channel: str = "logs"):
		super().__init__()
		self.ws_manager = ws_manager
		self.channel = channel
		self._loop = None

	def emit(self, record: logging.LogRecord):
		import asyncio
		import time

		try:
			msg = {
				"type": "log",
				"timestamp": time.time(),
				"payload": {
					"level": record.levelname,
					"logger": record.name,
					"message": self.format(record),
					"extra": {},
				},
			}

			# Store in buffer
			state = get_app_state()
			state.log_buffer.append(msg)

			# Try to broadcast (non-blocking)
			if self._loop is None:
				try:
					self._loop = asyncio.get_running_loop()
				except RuntimeError:
					return

			if self._loop and self._loop.is_running():
				asyncio.run_coroutine_threadsafe(
					self.ws_manager.broadcast(self.channel, msg),
					self._loop,
				)
		except Exception:
			pass


@router.websocket("/ws/logs")
async def logs_websocket(websocket: WebSocket):
	"""WebSocket endpoint for log streaming."""
	await manager.connect(websocket, "logs")

	state = get_app_state()

	# Send recent log history
	for log_entry in list(state.log_buffer)[-100:]:
		await manager.send_to(websocket, log_entry)

	try:
		while True:
			# Handle filter commands
			data = await websocket.receive_json()
			msg_type = data.get("type")

			if msg_type == "ping":
				await manager.send_to(websocket, {"type": "pong"})
			elif msg_type == "get_history":
				count = data.get("count", 100)
				for log_entry in list(state.log_buffer)[-count:]:
					await manager.send_to(websocket, log_entry)

	except WebSocketDisconnect:
		logger.info("Logs WebSocket disconnected")
	except Exception as e:
		logger.error(f"Logs WebSocket error: {e}")
	finally:
		await manager.disconnect(websocket, "logs")


def setup_log_handler():
	"""Set up WebSocket log handler."""
	handler = WebSocketLogHandler(manager, "logs")
	handler.setLevel(logging.DEBUG)
	handler.setFormatter(logging.Formatter("%(message)s"))

	# Add to root logger
	logging.getLogger().addHandler(handler)

	# Add to ambient loggers
	for name in ["ambient", "uvicorn"]:
		logging.getLogger(name).addHandler(handler)

	return handler
