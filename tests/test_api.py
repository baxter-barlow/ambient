"""Smoke tests for API routes."""

import pytest
from fastapi.testclient import TestClient

from ambient.api.main import app


@pytest.fixture
def client():
	return TestClient(app)


class TestHealthEndpoints:
	def test_root(self, client):
		resp = client.get("/")
		assert resp.status_code == 200
		data = resp.json()
		assert data["status"] == "ok"
		assert "service" in data

	def test_health(self, client):
		resp = client.get("/health")
		assert resp.status_code == 200
		data = resp.json()
		assert data["status"] == "healthy"
		assert "device_state" in data
		assert "recording" in data


class TestDeviceRoutes:
	def test_get_status(self, client):
		resp = client.get("/api/device/status")
		assert resp.status_code == 200
		data = resp.json()
		assert "state" in data
		assert data["state"] == "disconnected"

	def test_list_ports(self, client):
		resp = client.get("/api/device/ports")
		assert resp.status_code == 200
		assert isinstance(resp.json(), list)


class TestRecordingRoutes:
	def test_list_recordings(self, client):
		resp = client.get("/api/recordings")
		assert resp.status_code == 200
		assert isinstance(resp.json(), list)

	def test_recording_status(self, client):
		resp = client.get("/api/recordings/status")
		assert resp.status_code == 200
		data = resp.json()
		assert "is_recording" in data
		assert data["is_recording"] is False


class TestConfigRoutes:
	def test_list_profiles(self, client):
		resp = client.get("/api/config/profiles")
		assert resp.status_code == 200
		profiles = resp.json()
		assert isinstance(profiles, list)
		# Should have at least a default profile
		assert any(p["name"] == "default" for p in profiles)

	def test_flash_requires_connected_device(self, client):
		# Without a connected device, flash should fail
		resp = client.post("/api/config/flash?profile_name=default")
		assert resp.status_code == 400

	def test_flash_uses_sensor_stop_start(self, client, monkeypatch):
		"""Verify flash uses sensor.stop()/start() to reset buffers and state."""
		from unittest.mock import MagicMock

		from ambient.api.state import get_app_state

		# Create mock sensor
		mock_sensor = MagicMock()
		mock_sensor.stop = MagicMock()
		mock_sensor.start = MagicMock()
		mock_sensor.configure = MagicMock()

		# Set up app state with mock sensor in streaming state
		state = get_app_state()
		state.device._sensor = mock_sensor
		state.device._state = state.device._state.__class__("streaming")

		try:
			resp = client.post("/api/config/flash?profile_name=default")
			assert resp.status_code == 200

			# Verify stop/start methods were called, not raw CLI commands
			mock_sensor.stop.assert_called_once()
			mock_sensor.start.assert_called_once()
			mock_sensor.configure.assert_called_once()

			# Verify send_command was NOT called for sensorStop/sensorStart
			for call in mock_sensor.send_command.call_args_list:
				cmd = call[0][0] if call[0] else ""
				assert "sensorStop" not in cmd
				assert "sensorStart" not in cmd
		finally:
			# Cleanup
			state.device._sensor = None
			state.device._state = state.device._state.__class__("disconnected")

	def test_flash_uses_profile_parameters(self, client, monkeypatch):
		"""Verify flash applies selected profile parameters to configuration."""
		from unittest.mock import MagicMock

		from ambient.api.state import get_app_state
		from ambient.sensor.config import ChirpConfig

		# Create mock sensor that captures configure() argument
		mock_sensor = MagicMock()
		captured_config = []

		def capture_configure(cfg):
			captured_config.append(cfg)

		mock_sensor.configure = capture_configure
		mock_sensor.stop = MagicMock()
		mock_sensor.start = MagicMock()

		state = get_app_state()
		state.device._sensor = mock_sensor
		state.device._state = state.device._state.__class__("streaming")

		try:
			# Flash with default profile
			resp = client.post("/api/config/flash?profile_name=default")
			assert resp.status_code == 200

			# Verify configure was called with a ChirpConfig
			assert len(captured_config) == 1
			cfg = captured_config[0]
			assert isinstance(cfg, ChirpConfig)

			# Verify default profile parameters are used
			# Default ChirpParams has start_freq_ghz=60.0
			assert cfg.profile.start_freq_ghz == 60.0
			# Default FrameParams has chirps_per_frame=32
			assert cfg.frame.num_loops == 32

		finally:
			state.device._sensor = None
			state.device._state = state.device._state.__class__("disconnected")

	def test_flash_non_default_profile(self, client, monkeypatch):
		"""Verify flash applies custom profile parameters (not just defaults)."""
		from unittest.mock import MagicMock

		from ambient.api.state import get_app_state
		from ambient.sensor.config import ChirpConfig

		# First create a custom profile with different values
		custom_profile = {
			"name": "custom_test",
			"description": "Test profile with non-default values",
			"chirp": {
				"start_freq_ghz": 61.0,
				"bandwidth_mhz": 4000.0,
				"idle_time_us": 10.0,
				"ramp_end_time_us": 50.0,
				"adc_samples": 128,
				"sample_rate_ksps": 8000,
				"rx_gain_db": 25,
			},
			"frame": {
				"chirps_per_frame": 48,
				"frame_period_ms": 40.0,
			},
		}

		resp = client.post("/api/config/profiles", json=custom_profile)
		assert resp.status_code == 200

		mock_sensor = MagicMock()
		captured_config = []

		def capture_configure(cfg):
			captured_config.append(cfg)

		mock_sensor.configure = capture_configure
		mock_sensor.stop = MagicMock()
		mock_sensor.start = MagicMock()

		state = get_app_state()
		state.device._sensor = mock_sensor
		state.device._state = state.device._state.__class__("streaming")

		try:
			resp = client.post("/api/config/flash?profile_name=custom_test")
			assert resp.status_code == 200

			assert len(captured_config) == 1
			cfg = captured_config[0]
			assert isinstance(cfg, ChirpConfig)

			# Verify custom profile values (not defaults)
			assert cfg.profile.start_freq_ghz == 61.0
			assert cfg.profile.sample_rate_ksps == 8000
			assert cfg.profile.rx_gain_db == 25
			assert cfg.frame.num_loops == 48
			assert cfg.frame.frame_period_ms == 40.0

		finally:
			state.device._sensor = None
			state.device._state = state.device._state.__class__("disconnected")
			# Clean up the test profile
			client.delete("/api/config/profiles/custom_test")
