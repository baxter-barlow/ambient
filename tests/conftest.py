"""Pytest fixtures."""

import struct

import numpy as np
import pytest


@pytest.fixture
def sample_frame_bytes() -> bytes:
	"""Valid radar frame with 3 detected points."""
	magic = bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07])
	# packet_length = magic(8) + header(32) + tlv_header(8) + points(48) = 96
	header = struct.pack(
		"<IIIIIIII",
		0x0102,     # version
		96,         # packet_length (must match actual frame size)
		0x6843,     # platform
		1,          # frame_number
		1000000,    # time_cpu_cycles
		3,          # num_detected_obj
		1,          # num_tlvs
		0,          # subframe_number
	)
	tlv = struct.pack("<II", 1, 48)  # type=1, length=48 (3 points * 16 bytes)
	points = b""
	for i in range(3):
		points += struct.pack("<ffff", 1.0 + i, 0.5 + i * 0.2, 0.1, 0.0)
	return magic + header + tlv + points


@pytest.fixture
def sample_phase_signal() -> np.ndarray:
	"""Phase signal with 15 BPM respiratory + 60 BPM heart rate."""
	t = np.linspace(0, 10, 200)  # 20 Hz for 10s
	rr = 0.5 * np.sin(2 * np.pi * 0.25 * t)   # 15 BPM
	hr = 0.1 * np.sin(2 * np.pi * 1.0 * t)    # 60 BPM
	return (rr + hr + 0.05 * np.random.randn(len(t))).astype(np.float32)


@pytest.fixture
def sample_range_profile() -> np.ndarray:
	"""Range profile with target at bin 20."""
	profile = np.random.rand(128).astype(np.float32) * 10
	profile[20] = 100  # target
	return profile
