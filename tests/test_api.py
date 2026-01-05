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
