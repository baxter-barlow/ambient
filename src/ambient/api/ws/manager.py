"""WebSocket connection manager with backpressure support."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class BroadcastConfig:
	"""Configuration for broadcast behavior."""

	max_queue_size: int = 100  # Max messages in queue before dropping
	drop_policy: str = "oldest"  # oldest, newest, or none
	batch_size: int = 1  # Number of frames to batch (1 = no batching)
	batch_timeout_ms: float = 50.0  # Max wait for batch fill
	parallel_sends: bool = True  # Send to clients in parallel
	max_payload_kb: int = 50  # Warn if payload exceeds this


@dataclass
class BroadcastMetrics:
	"""Metrics for broadcast performance."""

	messages_sent: int = 0
	messages_dropped: int = 0
	bytes_sent: int = 0
	send_errors: int = 0
	avg_send_time_ms: float = 0.0
	queue_depth: int = 0
	_send_times: list[float] = field(default_factory=list)

	def record_send(self, duration_ms: float, bytes_count: int) -> None:
		self.messages_sent += 1
		self.bytes_sent += bytes_count
		self._send_times.append(duration_ms)
		# Keep last 100 samples for average
		if len(self._send_times) > 100:
			self._send_times.pop(0)
		self.avg_send_time_ms = sum(self._send_times) / len(self._send_times)

	def record_drop(self) -> None:
		self.messages_dropped += 1

	def record_error(self) -> None:
		self.send_errors += 1

	def to_dict(self) -> dict[str, Any]:
		return {
			"messages_sent": self.messages_sent,
			"messages_dropped": self.messages_dropped,
			"bytes_sent": self.bytes_sent,
			"send_errors": self.send_errors,
			"avg_send_time_ms": round(self.avg_send_time_ms, 2),
			"queue_depth": self.queue_depth,
		}


class ConnectionManager:
	"""Manages WebSocket connections with backpressure support."""

	def __init__(self, config: BroadcastConfig | None = None):
		self._connections: dict[str, set[WebSocket]] = defaultdict(set)
		self._lock = asyncio.Lock()
		self.config = config or BroadcastConfig()
		self._metrics: dict[str, BroadcastMetrics] = defaultdict(BroadcastMetrics)
		self._queues: dict[str, asyncio.Queue] = {}
		self._workers: dict[str, asyncio.Task] = {}
		self._running = False

	def configure(self, max_queue_size: int | None = None, drop_policy: str | None = None, max_payload_kb: int | None = None) -> None:
		"""Update configuration values.

		Should be called before start() and before any connections are established.
		"""
		if max_queue_size is not None:
			self.config.max_queue_size = max_queue_size
		if drop_policy is not None:
			self.config.drop_policy = drop_policy
		if max_payload_kb is not None:
			self.config.max_payload_kb = max_payload_kb

	async def start(self) -> None:
		"""Start background broadcast workers."""
		self._running = True

	async def stop(self) -> None:
		"""Stop background workers."""
		self._running = False
		for task in self._workers.values():
			task.cancel()
			try:
				await task
			except asyncio.CancelledError:
				pass
		self._workers.clear()
		self._queues.clear()

	def _ensure_queue(self, channel: str) -> asyncio.Queue:
		"""Ensure a queue exists for the channel."""
		if channel not in self._queues:
			self._queues[channel] = asyncio.Queue(maxsize=self.config.max_queue_size)
		return self._queues[channel]

	def _ensure_worker(self, channel: str) -> None:
		"""Ensure a background worker exists for the channel."""
		if channel not in self._workers or self._workers[channel].done():
			self._workers[channel] = asyncio.create_task(
				self._broadcast_worker(channel),
				name=f"broadcast_worker_{channel}"
			)

	async def _broadcast_worker(self, channel: str) -> None:
		"""Background worker that processes broadcast queue."""
		queue = self._ensure_queue(channel)

		while self._running:
			try:
				message = await asyncio.wait_for(queue.get(), timeout=1.0)
				await self._do_broadcast(channel, message)
				queue.task_done()
				self._metrics[channel].queue_depth = queue.qsize()
			except asyncio.TimeoutError:
				continue
			except asyncio.CancelledError:
				break
			except Exception as e:
				logger.error(f"Broadcast worker error on {channel}: {e}")

	async def _do_broadcast(self, channel: str, message: dict[str, Any]) -> None:
		"""Actually send message to all connections."""
		async with self._lock:
			connections = list(self._connections[channel])

		if not connections:
			return

		metrics = self._metrics[channel]
		start_time = time.perf_counter()

		# Estimate payload size (rough)
		import json
		try:
			payload_str = json.dumps(message)
			payload_size = len(payload_str)
		except Exception:
			payload_size = 0
			payload_str = None

		if payload_size > self.config.max_payload_kb * 1024:
			logger.warning(
				f"Large payload on {channel}: {payload_size / 1024:.1f} KB "
				f"(limit: {self.config.max_payload_kb} KB)"
			)

		dead_connections = []

		if self.config.parallel_sends and len(connections) > 1:
			# Send to all clients in parallel
			async def send_to_client(ws: WebSocket) -> WebSocket | None:
				try:
					if payload_str:
						await ws.send_text(payload_str)
					else:
						await ws.send_json(message)
					return None
				except Exception:
					return ws

			results = await asyncio.gather(
				*[send_to_client(ws) for ws in connections],
				return_exceptions=True
			)
			dead_connections = [r for r in results if r is not None and isinstance(r, WebSocket)]
		else:
			# Sequential sends
			for ws in connections:
				try:
					if payload_str:
						await ws.send_text(payload_str)
					else:
						await ws.send_json(message)
				except Exception:
					dead_connections.append(ws)

		duration_ms = (time.perf_counter() - start_time) * 1000
		metrics.record_send(duration_ms, payload_size)

		# Record errors
		for _ in dead_connections:
			metrics.record_error()

		# Clean up dead connections
		if dead_connections:
			async with self._lock:
				for ws in dead_connections:
					self._connections[channel].discard(ws)
			logger.debug(f"Removed {len(dead_connections)} dead connections from {channel}")

	async def connect(self, websocket: WebSocket, channel: str = "default"):
		"""Accept and register a WebSocket connection."""
		await websocket.accept()
		async with self._lock:
			self._connections[channel].add(websocket)
		logger.info(f"WebSocket connected to channel '{channel}' ({len(self._connections[channel])} total)")

		# Ensure worker is running for this channel
		if self._running:
			self._ensure_queue(channel)
			self._ensure_worker(channel)

	async def disconnect(self, websocket: WebSocket, channel: str = "default"):
		"""Remove a WebSocket connection."""
		async with self._lock:
			self._connections[channel].discard(websocket)
		logger.info(f"WebSocket disconnected from channel '{channel}'")

	async def broadcast(self, channel: str, message: dict[str, Any]):
		"""Queue message for broadcast to all connections on a channel.

		If queue is full, applies drop policy.
		"""
		async with self._lock:
			if not self._connections[channel]:
				return

		# Add envelope if not present
		if "type" not in message:
			message = {"type": "data", "timestamp": time.time(), "payload": message}
		elif "timestamp" not in message:
			message["timestamp"] = time.time()

		# If not running with workers, broadcast directly (backward compat)
		if not self._running:
			await self._do_broadcast(channel, message)
			return

		queue = self._ensure_queue(channel)
		self._ensure_worker(channel)

		# Handle queue full condition
		if queue.full():
			metrics = self._metrics[channel]
			if self.config.drop_policy == "oldest":
				# Drop oldest message
				try:
					queue.get_nowait()
					queue.task_done()
					metrics.record_drop()
				except asyncio.QueueEmpty:
					pass
			elif self.config.drop_policy == "newest":
				# Drop this message
				metrics.record_drop()
				return
			elif self.config.drop_policy == "none":
				# Block until space available
				await queue.put(message)
				self._metrics[channel].queue_depth = queue.qsize()
				return

		try:
			queue.put_nowait(message)
			self._metrics[channel].queue_depth = queue.qsize()
		except asyncio.QueueFull:
			self._metrics[channel].record_drop()

	async def broadcast_immediate(self, channel: str, message: dict[str, Any]):
		"""Broadcast message immediately, bypassing queue.

		Use for high-priority messages like device state changes.
		"""
		if "type" not in message:
			message = {"type": "data", "timestamp": time.time(), "payload": message}
		elif "timestamp" not in message:
			message["timestamp"] = time.time()

		await self._do_broadcast(channel, message)

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

	def get_metrics(self, channel: str | None = None) -> dict[str, Any]:
		"""Get broadcast metrics for channel(s)."""
		if channel:
			return self._metrics[channel].to_dict()
		return {ch: m.to_dict() for ch, m in self._metrics.items()}

	def get_all_metrics(self) -> dict[str, Any]:
		"""Get aggregated metrics across all channels."""
		total = BroadcastMetrics()
		for m in self._metrics.values():
			total.messages_sent += m.messages_sent
			total.messages_dropped += m.messages_dropped
			total.bytes_sent += m.bytes_sent
			total.send_errors += m.send_errors
		return {
			"total": total.to_dict(),
			"by_channel": {ch: m.to_dict() for ch, m in self._metrics.items()},
			"connections": {ch: len(conns) for ch, conns in self._connections.items()},
		}


# Global manager instance
manager = ConnectionManager()


def get_ws_manager() -> ConnectionManager:
	"""Get the global WebSocket manager instance."""
	return manager
