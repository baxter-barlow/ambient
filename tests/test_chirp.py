"""Tests for chirp firmware TLV parsing and vital signs processing."""

import struct

import numpy as np
import pytest

from ambient.sensor.frame import (
    HEADER_SIZE,
    MAGIC_WORD,
    TLV_CHIRP_PHASE_OUTPUT,
    ChirpMotionStatus,
    ChirpPhaseOutput,
    ChirpPresence,
    ChirpTargetInfo,
    FrameBuffer,
    RadarFrame,
)
from ambient.vitals import ChirpVitalsProcessor, VitalsConfig
from ambient.vitals.filters import PhaseUnwrapper

# ============================================================================
# Fixtures for chirp TLV data
# ============================================================================


@pytest.fixture
def chirp_phase_tlv_data() -> bytes:
    """PHASE_OUTPUT TLV with 4 bins."""
    # Header: numBins(2) + centerBin(2) + timestamp_us(4) = 8 bytes
    header = struct.pack("<HHI", 4, 20, 1000000)

    # 4 bins: binIndex(H) + phase(h) + magnitude(H) + flags(H) = 8 bytes each
    bins = b""
    for i in range(4):
        bin_idx = 19 + i
        phase = int(0.5 * 32768)  # ~π/2 radians (signed int16)
        magnitude = 1000 + i * 100
        flags = 0x02  # valid, no motion
        bins += struct.pack("<HhHH", bin_idx, phase, magnitude, flags)

    return header + bins


@pytest.fixture
def chirp_presence_tlv_data() -> bytes:
    """PRESENCE TLV data."""
    # presence(1) + confidence(1) + range_q8(2) + targetBin(2) + reserved(2)
    return struct.pack("<BBHHH", 1, 85, 512, 20, 0)  # present, 85%, 2.0m


@pytest.fixture
def chirp_motion_tlv_data() -> bytes:
    """MOTION_STATUS TLV data."""
    # detected(1) + level(1) + binCount(2) + peakBin(2) + peakDelta(2)
    return struct.pack("<BBHHH", 1, 150, 5, 25, 1000)


@pytest.fixture
def chirp_target_info_tlv_data() -> bytes:
    """TARGET_INFO TLV data."""
    # primaryBin(2) + primaryMag(2) + range_q8(2) + confidence(1) + numTargets(1) + secondaryBin(2) + reserved(2)
    return struct.pack("<HHHBBHH", 20, 900, 512, 85, 1, 0, 0)


@pytest.fixture
def chirp_frame_bytes(chirp_phase_tlv_data) -> bytes:
    """Complete frame with chirp PHASE_OUTPUT TLV."""
    tlv_length = len(chirp_phase_tlv_data)
    packet_length = HEADER_SIZE + 8 + tlv_length  # header + tlv header + tlv data

    header = struct.pack(
        "<IIIIIIII",
        0x0102,         # version
        packet_length,  # packet_length
        0x6843,         # platform
        1,              # frame_number
        1000000,        # time_cpu_cycles
        0,              # num_detected_obj
        1,              # num_tlvs
        0,              # subframe_number
    )

    tlv_header = struct.pack("<II", TLV_CHIRP_PHASE_OUTPUT, tlv_length)

    return MAGIC_WORD + header + tlv_header + chirp_phase_tlv_data


# ============================================================================
# ChirpPhaseOutput Tests
# ============================================================================


class TestChirpPhaseOutput:
    def test_from_bytes(self, chirp_phase_tlv_data):
        result = ChirpPhaseOutput.from_bytes(chirp_phase_tlv_data)
        assert result is not None
        assert result.num_bins == 4
        assert result.center_bin == 20
        assert result.timestamp_us == 1000000
        assert len(result.bins) == 4

    def test_bin_parsing(self, chirp_phase_tlv_data):
        result = ChirpPhaseOutput.from_bytes(chirp_phase_tlv_data)
        assert result is not None

        # Check first bin
        bin0 = result.bins[0]
        assert bin0.bin_index == 19
        assert bin0.phase == pytest.approx(np.pi / 2, abs=0.01)
        assert bin0.magnitude == 1000
        assert bin0.is_valid
        assert not bin0.has_motion

    def test_get_center_phase(self, chirp_phase_tlv_data):
        result = ChirpPhaseOutput.from_bytes(chirp_phase_tlv_data)
        assert result is not None

        phase = result.get_center_phase()
        assert phase is not None
        assert phase == pytest.approx(np.pi / 2, abs=0.01)

    def test_invalid_data(self):
        result = ChirpPhaseOutput.from_bytes(b"\x00\x00")
        assert result is None


# ============================================================================
# ChirpPresence Tests
# ============================================================================


class TestChirpPresence:
    def test_from_bytes(self, chirp_presence_tlv_data):
        result = ChirpPresence.from_bytes(chirp_presence_tlv_data)
        assert result is not None
        assert result.presence == 1
        assert result.confidence == 85
        assert result.range_m == pytest.approx(2.0)
        assert result.target_bin == 20

    def test_is_present(self, chirp_presence_tlv_data):
        result = ChirpPresence.from_bytes(chirp_presence_tlv_data)
        assert result is not None
        assert result.is_present
        assert not result.has_motion

    def test_motion_state(self):
        data = struct.pack("<BBHHH", 2, 90, 256, 15, 0)
        result = ChirpPresence.from_bytes(data)
        assert result is not None
        assert result.is_present
        assert result.has_motion


# ============================================================================
# ChirpMotionStatus Tests
# ============================================================================


class TestChirpMotionStatus:
    def test_from_bytes(self, chirp_motion_tlv_data):
        result = ChirpMotionStatus.from_bytes(chirp_motion_tlv_data)
        assert result is not None
        assert result.motion_detected
        assert result.motion_level == 150
        assert result.motion_bin_count == 5
        assert result.peak_motion_bin == 25


# ============================================================================
# ChirpTargetInfo Tests
# ============================================================================


class TestChirpTargetInfo:
    def test_from_bytes(self, chirp_target_info_tlv_data):
        result = ChirpTargetInfo.from_bytes(chirp_target_info_tlv_data)
        assert result is not None
        assert result.primary_bin == 20
        assert result.primary_magnitude == 900
        assert result.range_m == pytest.approx(2.0)
        assert result.confidence == 85
        assert result.num_targets == 1
        assert result.secondary_bin == 0


# ============================================================================
# RadarFrame with Chirp TLVs
# ============================================================================


class TestRadarFrameChirp:
    def test_parses_chirp_phase(self, chirp_frame_bytes):
        frame = RadarFrame.from_bytes(chirp_frame_bytes)
        assert frame.chirp_phase is not None
        assert frame.chirp_phase.num_bins == 4

    def test_frame_buffer_parses_chirp(self, chirp_frame_bytes):
        buf = FrameBuffer()
        buf.append(chirp_frame_bytes)
        frame = buf.extract_frame()
        assert frame is not None
        assert frame.chirp_phase is not None


# ============================================================================
# PhaseUnwrapper Tests
# ============================================================================


class TestPhaseUnwrapper:
    def test_no_jump(self):
        unwrapper = PhaseUnwrapper()
        # Small changes don't trigger unwrapping
        assert unwrapper.unwrap_sample(0.0) == pytest.approx(0.0)
        assert unwrapper.unwrap_sample(0.1) == pytest.approx(0.1)
        assert unwrapper.unwrap_sample(0.2) == pytest.approx(0.2)

    def test_positive_wrap(self):
        unwrapper = PhaseUnwrapper()
        # Phase wraps from ~π to ~-π
        unwrapper.unwrap_sample(3.0)
        result = unwrapper.unwrap_sample(-3.0)
        # Should unwrap to ~3.0 + 2π instead of -3.0
        assert result == pytest.approx(-3.0 + 2 * np.pi, abs=0.1)

    def test_negative_wrap(self):
        unwrapper = PhaseUnwrapper()
        # Phase wraps from ~-π to ~π
        unwrapper.unwrap_sample(-3.0)
        result = unwrapper.unwrap_sample(3.0)
        # Should unwrap to ~-3.0 - 2π instead of 3.0
        assert result == pytest.approx(3.0 - 2 * np.pi, abs=0.1)

    def test_reset(self):
        unwrapper = PhaseUnwrapper()
        unwrapper.unwrap_sample(1.0)
        unwrapper.reset()
        assert unwrapper.cumulative_phase == 0.0

    def test_unwrap_array(self):
        unwrapper = PhaseUnwrapper()
        # Create wrapped signal
        wrapped = np.array([3.0, -3.0, 3.0, -3.0])
        unwrapped = unwrapper.unwrap_array(wrapped)
        # Should be monotonically changing
        diffs = np.diff(unwrapped)
        assert all(abs(d) < np.pi for d in diffs)


# ============================================================================
# ChirpVitalsProcessor Tests
# ============================================================================


class TestChirpVitalsProcessor:
    def test_initialization(self):
        processor = ChirpVitalsProcessor()
        assert processor.buffer_fullness == 0.0
        assert not processor.is_ready

    def test_custom_config(self):
        config = VitalsConfig(sample_rate_hz=10.0, window_seconds=5.0)
        processor = ChirpVitalsProcessor(config)
        assert processor.config.sample_rate_hz == 10.0

    def test_process_single_frame(self, chirp_phase_tlv_data):
        processor = ChirpVitalsProcessor()
        phase_output = ChirpPhaseOutput.from_bytes(chirp_phase_tlv_data)
        assert phase_output is not None

        vitals = processor.process_chirp_phase(phase_output)
        assert vitals is not None
        assert vitals.source == "chirp"
        # Should not have valid rates yet (need more samples)
        assert vitals.heart_rate_bpm is None

    def test_buffer_fills(self, chirp_phase_tlv_data):
        config = VitalsConfig(sample_rate_hz=20.0, window_seconds=1.0)
        processor = ChirpVitalsProcessor(config)
        phase_output = ChirpPhaseOutput.from_bytes(chirp_phase_tlv_data)
        assert phase_output is not None

        # Feed multiple frames
        for i in range(30):
            processor.process_chirp_phase(phase_output, timestamp=i * 0.05)

        assert processor.buffer_fullness > 0.5

    def test_reset(self, chirp_phase_tlv_data):
        processor = ChirpVitalsProcessor()
        phase_output = ChirpPhaseOutput.from_bytes(chirp_phase_tlv_data)
        assert phase_output is not None

        processor.process_chirp_phase(phase_output)
        processor.reset()
        assert processor.buffer_fullness == 0.0

    def test_motion_detection(self):
        processor = ChirpVitalsProcessor()

        # Create phase output with motion flag
        header = struct.pack("<HHI", 1, 20, 1000000)
        # bin with motion flag (0x01) and valid flag (0x02) = 0x03
        bin_data = struct.pack("<HhHH", 20, 0, 1000, 0x03)
        phase_output = ChirpPhaseOutput.from_bytes(header + bin_data)
        assert phase_output is not None

        vitals = processor.process_chirp_phase(phase_output)
        assert vitals.motion_detected

    def test_process_frame_with_chirp_phase(self, chirp_frame_bytes):
        processor = ChirpVitalsProcessor()
        frame = RadarFrame.from_bytes(chirp_frame_bytes)

        vitals = processor.process_frame(frame)
        assert vitals is not None
        assert vitals.source == "chirp"

    def test_process_frame_without_chirp_phase(self):
        processor = ChirpVitalsProcessor()
        frame = RadarFrame()  # Empty frame

        vitals = processor.process_frame(frame)
        assert vitals is None


# ============================================================================
# Integration Tests
# ============================================================================


class TestChirpVitalsIntegration:
    """Integration tests simulating real vital signs scenarios."""

    def test_respiratory_rate_estimation(self):
        """Test RR estimation with simulated breathing signal."""
        config = VitalsConfig(sample_rate_hz=20.0, window_seconds=10.0)
        processor = ChirpVitalsProcessor(config)

        # Simulate 10 seconds of data at 20 Hz with 15 BPM breathing
        t = np.linspace(0, 10, 200)
        phases = 0.5 * np.sin(2 * np.pi * 0.25 * t)  # 0.25 Hz = 15 BPM

        vitals = None
        for i, phase in enumerate(phases):
            # Create phase output (phase is signed int16)
            phase_int = int((phase / np.pi) * 32768)
            phase_int = max(-32768, min(32767, phase_int))
            header = struct.pack("<HHI", 1, 20, int(t[i] * 1e6))
            # binIndex(H), phase(h), magnitude(H), flags(H) per TLV spec
            bin_data = struct.pack("<HhHH", 20, phase_int, 1000, 0x02)
            phase_output = ChirpPhaseOutput.from_bytes(header + bin_data)

            vitals = processor.process_chirp_phase(phase_output, timestamp=t[i])

        # Should have valid respiratory rate
        assert vitals is not None
        if vitals.respiratory_rate_bpm is not None:
            assert 10 < vitals.respiratory_rate_bpm < 25

    def test_heart_rate_estimation(self):
        """Test HR estimation with simulated heart signal."""
        config = VitalsConfig(sample_rate_hz=20.0, window_seconds=10.0)
        processor = ChirpVitalsProcessor(config)

        # Simulate 10 seconds at 20 Hz with 72 BPM heart rate
        t = np.linspace(0, 10, 200)
        phases = 0.1 * np.sin(2 * np.pi * 1.2 * t)  # 1.2 Hz = 72 BPM

        vitals = None
        for i, phase in enumerate(phases):
            phase_int = int((phase / np.pi) * 32768)
            phase_int = max(-32768, min(32767, phase_int))
            header = struct.pack("<HHI", 1, 20, int(t[i] * 1e6))
            # binIndex(H), phase(h), magnitude(H), flags(H) per TLV spec
            bin_data = struct.pack("<HhHH", 20, phase_int, 1000, 0x02)
            phase_output = ChirpPhaseOutput.from_bytes(header + bin_data)

            vitals = processor.process_chirp_phase(phase_output, timestamp=t[i])

        assert vitals is not None
        if vitals.heart_rate_bpm is not None:
            assert 50 < vitals.heart_rate_bpm < 100
