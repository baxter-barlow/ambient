"""FastAPI application for ambient dashboard."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import config, device, params, recordings, tests
from .state import get_app_state
from .tasks import start_acquisition, stop_acquisition
from .ws import logs, sensor
from .ws import tests as ws_tests
from .ws.logs import setup_log_handler
from .ws.manager import manager

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
	"""Application lifespan handler."""
	logger.info("Starting ambient dashboard API")

	# Set up log handler for WebSocket streaming
	setup_log_handler()

	# Initialize state
	state = get_app_state()

	# Register state change callback to start/stop acquisition
	async def on_state_change(new_state):
		from .schemas import DeviceState
		if new_state == DeviceState.STREAMING:
			await start_acquisition(state, manager)
			# Broadcast state change
			status = state.device.get_status()
			await manager.broadcast("sensor", {
				"type": "device_state",
				"payload": status.model_dump(),
			})
		elif new_state in (DeviceState.DISCONNECTED, DeviceState.ERROR):
			await stop_acquisition(state)
			status = state.device.get_status()
			await manager.broadcast("sensor", {
				"type": "device_state",
				"payload": status.model_dump(),
			})

	# Wrap sync callback in async
	def sync_callback(new_state):
		import asyncio
		try:
			loop = asyncio.get_running_loop()
			asyncio.run_coroutine_threadsafe(on_state_change(new_state), loop)
		except RuntimeError:
			pass

	state.device.on_state_change(sync_callback)

	yield

	# Cleanup
	logger.info("Shutting down ambient dashboard API")
	await state.device.disconnect()


app = FastAPI(
	title="Ambient Dashboard API",
	description="API for mmWave radar sleep biometrics dashboard",
	version="0.1.0",
	lifespan=lifespan,
)

# CORS for development
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# REST routes
app.include_router(device.router)
app.include_router(recordings.router)
app.include_router(config.router)
app.include_router(params.router)
app.include_router(tests.router)

# WebSocket routes
app.include_router(sensor.router)
app.include_router(logs.router)
app.include_router(ws_tests.router)


@app.get("/")
async def root():
	"""Root endpoint."""
	return {"status": "ok", "service": "ambient-dashboard"}


@app.get("/health")
async def health():
	"""Health check endpoint."""
	state = get_app_state()
	return {
		"status": "healthy",
		"device_state": state.device.state.value,
		"recording": state.recording.is_recording,
	}


# Serve static frontend in production
dashboard_dist = Path(__file__).parent.parent.parent.parent.parent / "dashboard" / "dist"
if dashboard_dist.exists():
	app.mount("/", StaticFiles(directory=str(dashboard_dist), html=True), name="static")
