"""Test runner WebSocket endpoint."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/tests")
async def tests_websocket(websocket: WebSocket):
	"""WebSocket endpoint for test output streaming."""
	await manager.connect(websocket, "tests")

	try:
		while True:
			data = await websocket.receive_json()
			msg_type = data.get("type")

			if msg_type == "ping":
				await manager.send_to(websocket, {"type": "pong"})

			elif msg_type == "run":
				# Run tests and stream output
				modules = data.get("modules", [])
				include_hardware = data.get("include_hardware", False)

				await run_tests_streaming(websocket, modules, include_hardware)

	except WebSocketDisconnect:
		logger.info("Tests WebSocket disconnected")
	except Exception as e:
		logger.error(f"Tests WebSocket error: {e}")
	finally:
		await manager.disconnect(websocket, "tests")


async def run_tests_streaming(websocket: WebSocket, modules: list[str], include_hardware: bool):
	"""Run pytest and stream output."""
	test_dir = Path(os.environ.get("AMBIENT_PROJECT_DIR", ".")) / "tests"

	cmd = ["python", "-m", "pytest", "-v", "--tb=short"]

	if modules:
		for module in modules:
			cmd.append(str(test_dir / f"{module}.py"))
	else:
		cmd.append(str(test_dir))

	if not include_hardware:
		cmd.extend(["-m", "not hardware"])

	await manager.send_to(websocket, {
		"type": "test_start",
		"timestamp": time.time(),
		"payload": {"command": " ".join(cmd)},
	})

	proc = await asyncio.create_subprocess_exec(
		*cmd,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.STDOUT,
		cwd=os.environ.get("AMBIENT_PROJECT_DIR", "."),
	)

	# Stream output line by line
	while True:
		line = await proc.stdout.readline()
		if not line:
			break

		await manager.send_to(websocket, {
			"type": "test_output",
			"timestamp": time.time(),
			"payload": {"line": line.decode().rstrip()},
		})

	await proc.wait()

	await manager.send_to(websocket, {
		"type": "test_complete",
		"timestamp": time.time(),
		"payload": {"returncode": proc.returncode},
	})
