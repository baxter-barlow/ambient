"""WebSocket connection manager."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
	"""Manages WebSocket connections across channels."""

	def __init__(self):
		self._connections: dict[str, set[WebSocket]] = defaultdict(set)
		self._lock = asyncio.Lock()

	async def connect(self, websocket: WebSocket, channel: str = "default"):
		"""Accept and register a WebSocket connection."""
		await websocket.accept()
		async with self._lock:
			self._connections[channel].add(websocket)
		logger.info(f"WebSocket connected to channel '{channel}' ({len(self._connections[channel])} total)")

	async def disconnect(self, websocket: WebSocket, channel: str = "default"):
		"""Remove a WebSocket connection."""
		async with self._lock:
			self._connections[channel].discard(websocket)
		logger.info(f"WebSocket disconnected from channel '{channel}'")

	async def broadcast(self, channel: str, message: dict[str, Any]):
		"""Broadcast message to all connections on a channel."""
		async with self._lock:
			connections = list(self._connections[channel])

		if not connections:
			return

		# Add envelope if not present
		if "type" not in message:
			message = {"type": "data", "timestamp": time.time(), "payload": message}
		elif "timestamp" not in message:
			message["timestamp"] = time.time()

		dead_connections = []
		for ws in connections:
			try:
				await ws.send_json(message)
			except Exception:
				dead_connections.append(ws)

		# Clean up dead connections
		if dead_connections:
			async with self._lock:
				for ws in dead_connections:
					self._connections[channel].discard(ws)

	async def send_to(self, websocket: WebSocket, message: dict[str, Any]):
		"""Send message to specific connection."""
		if "type" not in message:
			message = {"type": "data", "timestamp": time.time(), "payload": message}
		elif "timestamp" not in message:
			message["timestamp"] = time.time()

		try:
			await websocket.send_json(message)
		except Exception as e:
			logger.error(f"Failed to send message: {e}")

	def get_connection_count(self, channel: str = "default") -> int:
		"""Get number of connections on a channel."""
		return len(self._connections[channel])


# Global manager instance
manager = ConnectionManager()
