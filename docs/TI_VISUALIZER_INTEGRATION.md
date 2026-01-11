# TI mmWave Radar Visualizer Integration Guide

## For AMBIENT Developers

This document provides a comprehensive technical reference for integrating features from TI's Radar Toolbox Visualizer into the AMBIENT project. It covers the TI visualizer architecture, data formats, signal processing algorithms, and specific implementation details that can enhance AMBIENT's capabilities.

---

## Table of Contents

1. [Overview & Key Differences](#1-overview--key-differences)
2. [TLV Frame Format Reference](#2-tlv-frame-format-reference)
3. [Vital Signs Algorithm Deep Dive](#3-vital-signs-algorithm-deep-dive)
4. [TLV Parsing Implementation](#4-tlv-parsing-implementation)
5. [Multi-Patient Vital Signs Support](#5-multi-patient-vital-signs-support)
6. [3D Point Cloud Visualization](#6-3d-point-cloud-visualization)
7. [Configuration File Format](#7-configuration-file-format)
8. [Signal Processing Pipeline](#8-signal-processing-pipeline)
9. [Quality Metrics & Validation](#9-quality-metrics--validation)
10. [Integration Recommendations](#10-integration-recommendations)

---

## 1. Overview & Key Differences

### TI Visualizer Stack
- **Frontend**: PySide6/Qt with PyQtGraph
- **Backend**: Monolithic Python application
- **Communication**: Direct serial via pyserial
- **Visualization**: PyQtGraph (2D), PyQtGraph.opengl (3D)

### AMBIENT Stack (Already Implemented)
- **Frontend**: React + TypeScript + uplot
- **Backend**: FastAPI with WebSocket streaming
- **Communication**: Async serial with frame buffering
- **Visualization**: uplot (2D), potential Three.js (3D)

### Key Features in TI Visualizer That May Enhance AMBIENT

| Feature | TI Implementation | AMBIENT Status | Priority |
|---------|-------------------|----------------|----------|
| Vital Signs TLV (1040) | Full parsing | May be partial | High |
| Multi-patient tracking | Up to 2 patients | Single target | Medium |
| 3D Point Cloud | PyQtGraph OpenGL | Not implemented | Medium |
| Point persistence | Configurable frames | Not implemented | Low |
| Fall detection | Variance-based | Not implemented | Low |
| Range profile plot | Real-time FFT | Implemented | Done |
| Tracked objects | Up to 20 tracks | Partial | Medium |

---

## 2. TLV Frame Format Reference

### Frame Header Structure (40 bytes)

The TI radar outputs frames with a fixed header followed by variable TLVs.

```python
# Frame header format (little-endian)
FRAME_HEADER_FORMAT = '<Q8I'  # 40 bytes total

# Fields:
# - magic_word: uint64 = 0x0708050603040102 (8 bytes)
# - version: uint32 (4 bytes)
# - total_packet_len: uint32 (4 bytes)
# - platform: uint32 (4 bytes)
# - frame_number: uint32 (4 bytes)
# - time_cpu_cycles: uint32 (4 bytes)
# - num_detected_obj: uint32 (4 bytes)
# - num_tlvs: uint32 (4 bytes)
# - subframe_number: uint32 (4 bytes)
```

**Python Implementation** (from TI's `parseTLVs.py`):

```python
import struct

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'

def parse_frame_header(data: bytes) -> dict:
    """Parse 40-byte frame header."""
    if len(data) < 40:
        return None

    magic = data[0:8]
    if magic != MAGIC_WORD:
        return None

    header = struct.unpack('<Q8I', data[:40])
    return {
        'magic': header[0],
        'version': header[1],
        'total_packet_len': header[2],
        'platform': header[3],
        'frame_number': header[4],
        'time_cpu_cycles': header[5],
        'num_detected_obj': header[6],
        'num_tlvs': header[7],
        'subframe_number': header[8]
    }
```

### TLV Header Structure (8 bytes)

Each TLV has a type and length header:

```python
TLV_HEADER_FORMAT = '<2I'  # 8 bytes

def parse_tlv_header(data: bytes) -> tuple:
    """Returns (tlv_type, tlv_length)."""
    return struct.unpack('<2I', data[:8])
```

### Complete TLV Type Reference

```python
# Standard mmWave Demo TLVs
TLV_TYPES = {
    # Detected Points & Objects
    1: 'DETECTED_POINTS',           # Point cloud (x, y, z, doppler)
    2: 'RANGE_PROFILE',             # 1D range FFT magnitude
    3: 'NOISE_PROFILE',             # Noise floor per range bin
    4: 'AZIMUTH_STATIC_HEATMAP',    # 2D azimuth vs range
    5: 'RANGE_DOPPLER_HEATMAP',     # 2D range vs doppler
    6: 'STATS',                     # Performance statistics
    7: 'DETECTED_POINTS_SIDE_INFO', # SNR, noise per point
    8: 'AZIMUTH_ELEVATION_HEATMAP', # 3D heatmap
    9: 'TEMPERATURE_STATS',         # Device temperature

    # Tracking TLVs
    20: 'POINT_CLOUD_2D',           # Compressed 2D points

    # People Tracking Demo
    250: 'TRACKED_OBJECTS_3D',       # Track output (x, y, z, vx, vy, vz)
    251: 'TARGET_LIST_2D',           # 2D track list
    252: 'TARGET_INDEX',             # Point-to-track association
    253: 'COMPRESSED_POINTS',        # Spherical compressed points
    254: 'PRESENCE_INDICATION',      # Binary presence

    # Vital Signs TLVs (CRITICAL FOR AMBIENT)
    1040: 'VITAL_SIGNS',             # HR, RR, waveforms

    # Extended/Custom TLVs
    1010: 'GESTURE_FEATURES_6843',
    1020: 'GESTURE_OUTPUT_PROB_6843',
    1021: 'GESTURE_CLASSIFIER_6843',

    # Chirp-specific (already in AMBIENT)
    0x0500: 'CHIRP_RANGE_FFT',       # Complex range FFT
    0x0510: 'CHIRP_TARGET_IQ',       # Target I/Q
    0x0520: 'CHIRP_PHASE_OUTPUT',    # Phase + magnitude
    0x0540: 'CHIRP_PRESENCE',        # Presence detection
    0x0550: 'CHIRP_MOTION',          # Motion status
    0x0560: 'CHIRP_TARGET_INFO',     # Target info
}
```

---

## 3. Vital Signs Algorithm Deep Dive

### TI's Firmware-Side Processing

The TI vital signs firmware performs extensive on-device processing before sending data. Here's the complete algorithm:

#### 3.1 Range-Angle Selection

```
Input: 6 virtual antennas × N range bins × 128 frames
Processing:
  1. DC Removal: Subtract 30-frame rolling mean
  2. 2D FFT: Azimuth (16-pt) + Elevation (16-pt)
  3. Peak Selection: Choose 9 best angle bins

Output: 5 range bins × 9 angles × 128 frames
```

#### 3.2 Phase Extraction & Unwrapping

```c
// From vitalsign.c - Phase unwrapping algorithm
float compute_phase_unwrap(float phase, float phase_prev, float *correction_cum) {
    float diff_phase = phase - phase_prev;
    float mod_factor = 0;

    // Detect 2π wrapping
    if (diff_phase > PI) {
        mod_factor = 1.0f;
    } else if (diff_phase < -PI) {
        mod_factor = -1.0f;
    }

    // Apply correction
    float diff_phase_mod = diff_phase - mod_factor * 2 * PI;
    float diff_correction = diff_phase_mod - diff_phase;
    *correction_cum += diff_correction;

    return phase + *correction_cum;
}
```

**Python equivalent for AMBIENT**:

```python
import numpy as np

class PhaseUnwrapper:
    """Phase unwrapping with cumulative correction tracking."""

    def __init__(self):
        self.prev_phase = 0.0
        self.correction_cum = 0.0

    def unwrap(self, phase: float) -> float:
        """Unwrap a single phase sample."""
        diff = phase - self.prev_phase

        # Detect wrapping
        if diff > np.pi:
            mod_factor = 1.0
        elif diff < -np.pi:
            mod_factor = -1.0
        else:
            mod_factor = 0.0

        # Apply correction
        diff_mod = diff - mod_factor * 2 * np.pi
        self.correction_cum += diff_mod - diff

        self.prev_phase = phase
        return phase + self.correction_cum

    def reset(self):
        self.prev_phase = 0.0
        self.correction_cum = 0.0
```

#### 3.3 FFT-Based Rate Estimation

```c
// TI's vital signs rate extraction
#define FFT_SIZE 512
#define SPECTRUM_MULT_FACTOR 0.882  // Converts bin index to BPM

// Frequency bands (bin indices)
#define BREATH_INDEX_START 3    // ~0.46 Hz
#define BREATH_INDEX_END   50   // ~7.5 Hz
#define HEART_INDEX_START  68   // ~10.2 Hz
#define HEART_INDEX_END    128  // ~19.2 Hz

// Peak detection with 3-sample smoothing
for (int i = BREATH_INDEX_START; i < BREATH_INDEX_END; i++) {
    float value = spectrum[i-1] + spectrum[i] + spectrum[i+1];
    if (value > breath_peak_value) {
        breath_peak_value = value;
        breath_peak_idx = i;
    }
}

float breath_rate_bpm = breath_peak_idx * SPECTRUM_MULT_FACTOR;
```

**Key insight**: TI uses 3-sample smoothing during peak detection to reduce noise sensitivity.

#### 3.4 Heart Rate Harmonic Enhancement

TI uses a clever technique for heart rate: **Decimated Spectrum Product**

```c
// Heart rate uses harmonic relationship (f and 2f)
float decimated_product[128];
for (int i = 0; i < 128; i++) {
    // Multiply frequency bin with its double
    decimated_product[i] = spectrum[2*i] * spectrum[i];
}

// Find peak in product spectrum
// This enhances true heart rate by requiring both fundamental and harmonic
```

**Python implementation**:

```python
def extract_heart_rate_harmonic(spectrum: np.ndarray, sample_rate: float) -> tuple:
    """
    Extract heart rate using harmonic product spectrum.

    The heart signal has energy at both f (fundamental) and 2f (harmonic).
    Multiplying spectrum[i] * spectrum[2*i] enhances the true HR peak.
    """
    n = len(spectrum) // 2

    # Create decimated product spectrum
    decimated = spectrum[:n] * spectrum[::2][:n]

    # Find peak in heart rate range (0.8-3.0 Hz = 48-180 BPM)
    freq_resolution = sample_rate / len(spectrum)
    hr_start_bin = int(0.8 / freq_resolution)
    hr_end_bin = int(3.0 / freq_resolution)

    # Constrain to valid range
    hr_start_bin = max(0, min(hr_start_bin, n-1))
    hr_end_bin = max(0, min(hr_end_bin, n-1))

    if hr_start_bin >= hr_end_bin:
        return None, 0.0

    # Find peak with 3-sample smoothing
    best_idx = hr_start_bin
    best_value = 0.0

    for i in range(hr_start_bin + 1, hr_end_bin - 1):
        value = decimated[i-1] + decimated[i] + decimated[i+1]
        if value > best_value:
            best_value = value
            best_idx = i

    heart_rate_hz = best_idx * freq_resolution
    heart_rate_bpm = heart_rate_hz * 60.0

    # Quality metric: ratio of peak to noise floor
    noise_floor = np.median(decimated)
    snr = best_value / (noise_floor + 1e-10)

    return heart_rate_bpm, snr
```

#### 3.5 Breathing Deviation (Presence Detection)

```python
def compute_breathing_deviation(phase_buffer: list, window_size: int = 40) -> float:
    """
    Compute variance of recent phase samples to detect patient presence.

    Returns:
        deviation: Variance metric
            >= 0.02: Patient present and breathing
            < 0.02:  Holding breath or no patient
            == 0:    No patient detected
    """
    if len(phase_buffer) < window_size:
        return 0.0

    recent = phase_buffer[-window_size:]

    # Variance = E[X²] - E[X]²
    mean = sum(recent) / len(recent)
    mean_sq = sum(x*x for x in recent) / len(recent)
    variance = mean_sq - mean * mean

    return variance
```

---

## 4. TLV Parsing Implementation

### 4.1 Vital Signs TLV (Type 1040) - CRITICAL

This is the most important TLV for vital signs monitoring. AMBIENT should implement this parser:

```python
import struct
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VitalSignsTLV:
    """Parsed Vital Signs TLV (Type 1040) from TI firmware."""
    patient_id: int
    range_bin: int
    breathing_deviation: float
    heart_rate_bpm: float
    breathing_rate_bpm: float
    heart_waveform: List[float]    # 15 samples
    breath_waveform: List[float]   # 15 samples

def parse_vital_signs_tlv(data: bytes) -> Optional[VitalSignsTLV]:
    """
    Parse TI Vital Signs TLV (Type 1040).

    Structure: 2H 33f (2 unsigned shorts + 33 floats = 136 bytes)

    Layout:
        Offset 0:   patient_id (uint16)
        Offset 2:   range_bin (uint16)
        Offset 4:   breathing_deviation (float32)
        Offset 8:   heart_rate (float32)
        Offset 12:  breathing_rate (float32)
        Offset 16:  heart_waveform[15] (15 × float32 = 60 bytes)
        Offset 76:  breath_waveform[15] (15 × float32 = 60 bytes)

    Total: 136 bytes
    """
    if len(data) < 136:
        return None

    # Parse header
    patient_id, range_bin = struct.unpack('<2H', data[0:4])

    # Parse vitals data (33 floats starting at offset 4)
    vitals_data = struct.unpack('<33f', data[4:136])

    return VitalSignsTLV(
        patient_id=patient_id,
        range_bin=range_bin,
        breathing_deviation=vitals_data[0],
        heart_rate_bpm=vitals_data[1],
        breathing_rate_bpm=vitals_data[2],
        heart_waveform=list(vitals_data[3:18]),    # indices 3-17
        breath_waveform=list(vitals_data[18:33])   # indices 18-32
    )
```

### 4.2 Detected Points TLV (Type 1)

```python
@dataclass
class DetectedPoint:
    x: float
    y: float
    z: float
    doppler: float

def parse_detected_points_tlv(data: bytes, num_points: int) -> List[DetectedPoint]:
    """
    Parse Detected Points TLV (Type 1).

    Each point: 4 × float32 = 16 bytes
    """
    points = []
    offset = 0
    point_size = 16

    for _ in range(num_points):
        if offset + point_size > len(data):
            break

        x, y, z, doppler = struct.unpack('<4f', data[offset:offset+point_size])
        points.append(DetectedPoint(x=x, y=y, z=z, doppler=doppler))
        offset += point_size

    return points
```

### 4.3 Detected Points Side Info TLV (Type 7)

```python
@dataclass
class PointSideInfo:
    snr: int      # Signal-to-noise ratio (dB)
    noise: int    # Noise level

def parse_side_info_tlv(data: bytes, num_points: int) -> List[PointSideInfo]:
    """
    Parse Side Info TLV (Type 7).

    Each entry: 2 × int16 = 4 bytes
    """
    info = []
    offset = 0
    entry_size = 4

    for _ in range(num_points):
        if offset + entry_size > len(data):
            break

        snr, noise = struct.unpack('<2h', data[offset:offset+entry_size])
        info.append(PointSideInfo(snr=snr, noise=noise))
        offset += entry_size

    return info
```

### 4.4 Tracked Objects TLV (Type 250)

```python
@dataclass
class TrackedObject:
    track_id: int
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    ax: float    # acceleration x
    ay: float    # acceleration y
    az: float    # acceleration z

def parse_tracked_objects_tlv(data: bytes) -> List[TrackedObject]:
    """
    Parse Tracked Objects 3D TLV (Type 250).

    Header: 2 × uint16 (num_tracks, padding)
    Each track: 40 bytes (1 uint32 + 9 float32)
    """
    if len(data) < 4:
        return []

    num_tracks = struct.unpack('<H', data[0:2])[0]
    tracks = []
    offset = 4  # Skip header
    track_size = 40

    for _ in range(num_tracks):
        if offset + track_size > len(data):
            break

        track_data = struct.unpack('<I9f', data[offset:offset+track_size])
        tracks.append(TrackedObject(
            track_id=track_data[0],
            x=track_data[1],
            y=track_data[2],
            z=track_data[3],
            vx=track_data[4],
            vy=track_data[5],
            vz=track_data[6],
            ax=track_data[7],
            ay=track_data[8],
            az=track_data[9]
        ))
        offset += track_size

    return tracks
```

### 4.5 Compressed Points TLV (Type 253)

TI uses spherical compression to reduce bandwidth:

```python
@dataclass
class CompressedPoint:
    elevation: float    # degrees
    azimuth: float      # degrees
    doppler: float      # m/s
    range_val: float    # meters
    snr: float          # dB

def parse_compressed_points_tlv(data: bytes, params: dict) -> List[CompressedPoint]:
    """
    Parse Spherical Compressed Points TLV (Type 253).

    Unit conversion values come from preceding TLV or config.

    Structure per point: 5 × int16 = 10 bytes
    """
    # Unit conversion parameters (from config or TLV 254 header)
    elev_unit = params.get('elevation_unit', 0.01)  # degrees per LSB
    azim_unit = params.get('azimuth_unit', 0.01)
    doppler_unit = params.get('doppler_unit', 0.01)
    range_unit = params.get('range_unit', 0.01)
    snr_unit = params.get('snr_unit', 0.5)

    points = []
    offset = 0
    point_size = 10

    while offset + point_size <= len(data):
        raw = struct.unpack('<5h', data[offset:offset+point_size])

        points.append(CompressedPoint(
            elevation=raw[0] * elev_unit,
            azimuth=raw[1] * azim_unit,
            doppler=raw[2] * doppler_unit,
            range_val=raw[3] * range_unit,
            snr=raw[4] * snr_unit
        ))
        offset += point_size

    return points
```

### 4.6 Complete Frame Parser

```python
from typing import Dict, Any

class TIFrameParser:
    """Complete frame parser for TI mmWave radar."""

    MAGIC_WORD = bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07])

    def __init__(self):
        self.buffer = bytearray()
        self.compression_params = {}

    def add_data(self, data: bytes):
        """Add received data to buffer."""
        self.buffer.extend(data)

    def parse_frames(self) -> List[Dict[str, Any]]:
        """Parse all complete frames from buffer."""
        frames = []

        while True:
            # Find magic word
            idx = self.buffer.find(self.MAGIC_WORD)
            if idx == -1:
                break

            # Discard data before magic word
            if idx > 0:
                self.buffer = self.buffer[idx:]

            # Check if we have full header
            if len(self.buffer) < 40:
                break

            # Parse header
            header = self._parse_header(bytes(self.buffer[:40]))
            if header is None:
                self.buffer = self.buffer[8:]  # Skip bad magic
                continue

            # Check if we have full frame
            total_len = header['total_packet_len']
            if len(self.buffer) < total_len:
                break

            # Extract and parse frame
            frame_data = bytes(self.buffer[:total_len])
            self.buffer = self.buffer[total_len:]

            frame = self._parse_frame(header, frame_data)
            if frame:
                frames.append(frame)

        return frames

    def _parse_header(self, data: bytes) -> Optional[Dict]:
        """Parse 40-byte frame header."""
        values = struct.unpack('<Q8I', data)
        return {
            'magic': values[0],
            'version': values[1],
            'total_packet_len': values[2],
            'platform': values[3],
            'frame_number': values[4],
            'time_cpu_cycles': values[5],
            'num_detected_obj': values[6],
            'num_tlvs': values[7],
            'subframe_number': values[8]
        }

    def _parse_frame(self, header: Dict, data: bytes) -> Dict[str, Any]:
        """Parse complete frame including all TLVs."""
        frame = {
            'frame_number': header['frame_number'],
            'num_detected_obj': header['num_detected_obj'],
            'timestamp': header['time_cpu_cycles'],
            'tlvs': {}
        }

        offset = 40  # Start after header

        for _ in range(header['num_tlvs']):
            if offset + 8 > len(data):
                break

            tlv_type, tlv_len = struct.unpack('<2I', data[offset:offset+8])
            offset += 8

            if offset + tlv_len > len(data):
                break

            tlv_data = data[offset:offset+tlv_len]
            offset += tlv_len

            # Parse known TLV types
            parsed = self._parse_tlv(tlv_type, tlv_data, header['num_detected_obj'])
            if parsed is not None:
                frame['tlvs'][tlv_type] = parsed

        return frame

    def _parse_tlv(self, tlv_type: int, data: bytes, num_points: int) -> Any:
        """Parse individual TLV by type."""

        if tlv_type == 1:  # Detected Points
            return parse_detected_points_tlv(data, num_points)

        elif tlv_type == 2:  # Range Profile
            num_bins = len(data) // 2
            return list(struct.unpack(f'<{num_bins}H', data))

        elif tlv_type == 5:  # Range-Doppler Heatmap
            # Returns 2D array (range × doppler)
            return self._parse_heatmap(data)

        elif tlv_type == 7:  # Side Info
            return parse_side_info_tlv(data, num_points)

        elif tlv_type == 250:  # Tracked Objects
            return parse_tracked_objects_tlv(data)

        elif tlv_type == 253:  # Compressed Points
            return parse_compressed_points_tlv(data, self.compression_params)

        elif tlv_type == 1040:  # Vital Signs
            return parse_vital_signs_tlv(data)

        # Add more TLV parsers as needed

        return None  # Unknown TLV type

    def _parse_heatmap(self, data: bytes) -> np.ndarray:
        """Parse 2D heatmap data."""
        # Typically uint16 values, reshape based on config
        values = np.frombuffer(data, dtype=np.uint16)
        # Reshape requires knowing dimensions from config
        return values
```

---

## 5. Multi-Patient Vital Signs Support

TI's visualizer supports up to 2 patients simultaneously. Here's how to implement this:

### 5.1 Patient Data Structure

```python
from dataclasses import dataclass, field
from typing import List, Optional
from collections import deque

@dataclass
class PatientVitals:
    """Vital signs data for a single patient."""
    patient_id: int
    range_bin: int = 0

    # Current values
    heart_rate_bpm: Optional[float] = None
    breathing_rate_bpm: Optional[float] = None
    breathing_deviation: float = 0.0

    # Status
    status: str = "No Patient Detected"  # "Presence", "Holding Breath", "No Patient Detected"

    # Waveform history (for plotting)
    heart_waveform: deque = field(default_factory=lambda: deque(maxlen=150))
    breath_waveform: deque = field(default_factory=lambda: deque(maxlen=150))

    # Heart rate median filter (TI uses 10-sample median)
    heart_rate_history: deque = field(default_factory=lambda: deque(maxlen=10))

    def update_from_tlv(self, tlv: VitalSignsTLV):
        """Update patient data from parsed TLV."""
        self.range_bin = tlv.range_bin
        self.breathing_deviation = tlv.breathing_deviation

        # Extend waveforms
        self.heart_waveform.extend(tlv.heart_waveform)
        self.breath_waveform.extend(tlv.breath_waveform)

        # Update status based on breathing deviation
        if tlv.breathing_deviation == 0:
            self.status = "No Patient Detected"
            self.heart_rate_bpm = None
            self.breathing_rate_bpm = None
        elif tlv.breathing_deviation >= 0.02:
            self.status = "Presence"
            self.breathing_rate_bpm = tlv.breathing_rate_bpm if tlv.breathing_rate_bpm > 0 else None

            # Median filter for heart rate
            if tlv.heart_rate_bpm > 0:
                self.heart_rate_history.append(tlv.heart_rate_bpm)
                self.heart_rate_bpm = self._median(list(self.heart_rate_history))
        else:
            self.status = "Holding Breath"
            self.breathing_rate_bpm = None
            # Still update heart rate
            if tlv.heart_rate_bpm > 0:
                self.heart_rate_history.append(tlv.heart_rate_bpm)
                self.heart_rate_bpm = self._median(list(self.heart_rate_history))

    @staticmethod
    def _median(values: List[float]) -> float:
        """Compute median of values."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n % 2 == 0:
            return (sorted_vals[n//2 - 1] + sorted_vals[n//2]) / 2
        return sorted_vals[n//2]
```

### 5.2 Multi-Patient Manager

```python
class MultiPatientVitalsManager:
    """Manages vital signs for multiple patients."""

    MAX_PATIENTS = 2

    def __init__(self):
        self.patients: Dict[int, PatientVitals] = {}
        self.max_tracks = 5  # From trackingCfg

    def configure(self, max_tracks: int):
        """Configure from trackingCfg command."""
        self.max_tracks = min(max_tracks, self.MAX_PATIENTS)

        # Initialize patient slots
        for i in range(self.max_tracks):
            if i not in self.patients:
                self.patients[i] = PatientVitals(patient_id=i)

    def update(self, tlv: VitalSignsTLV):
        """Update patient data from vital signs TLV."""
        patient_id = tlv.patient_id

        if patient_id >= self.max_tracks:
            return  # Invalid patient ID

        if patient_id not in self.patients:
            self.patients[patient_id] = PatientVitals(patient_id=patient_id)

        self.patients[patient_id].update_from_tlv(tlv)

    def get_all_vitals(self) -> List[dict]:
        """Get vitals data for all patients (for WebSocket broadcast)."""
        result = []
        for i in range(self.max_tracks):
            if i in self.patients:
                p = self.patients[i]
                result.append({
                    'patient_id': p.patient_id,
                    'status': p.status,
                    'heart_rate_bpm': p.heart_rate_bpm,
                    'breathing_rate_bpm': p.breathing_rate_bpm,
                    'breathing_deviation': p.breathing_deviation,
                    'range_bin': p.range_bin,
                    'heart_waveform': list(p.heart_waveform)[-15:],  # Last 15 samples
                    'breath_waveform': list(p.breath_waveform)[-15:],
                })
        return result
```

---

## 6. 3D Point Cloud Visualization

### 6.1 Point Persistence

TI's visualizer accumulates points across multiple frames for a denser display:

```python
from collections import deque
from dataclasses import dataclass
from typing import List
import numpy as np

@dataclass
class Point3D:
    x: float
    y: float
    z: float
    doppler: float
    snr: float
    track_id: Optional[int] = None

class PointCloudAccumulator:
    """Accumulates point clouds across multiple frames."""

    def __init__(self, num_persistent_frames: int = 10):
        self.num_persistent_frames = num_persistent_frames
        self.frame_history: deque = deque(maxlen=num_persistent_frames)

    def add_frame(self, points: List[Point3D]):
        """Add a new frame of points."""
        self.frame_history.append(points)

    def get_accumulated_cloud(self) -> np.ndarray:
        """Get all accumulated points as numpy array."""
        all_points = []

        for frame_idx, frame_points in enumerate(self.frame_history):
            age = len(self.frame_history) - frame_idx - 1  # 0 = newest

            for p in frame_points:
                all_points.append([
                    p.x, p.y, p.z,
                    p.doppler, p.snr,
                    age  # For color fading
                ])

        if not all_points:
            return np.empty((0, 6))

        return np.array(all_points)

    def set_persistence(self, num_frames: int):
        """Update persistence setting."""
        self.num_persistent_frames = num_frames
        self.frame_history = deque(
            list(self.frame_history)[-num_frames:],
            maxlen=num_frames
        )
```

### 6.2 Frontend Implementation (Three.js)

For AMBIENT's React frontend, here's a Three.js point cloud component:

```typescript
// components/charts/PointCloud3D.tsx
import { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

interface Point3DData {
  x: number;
  y: number;
  z: number;
  doppler: number;
  snr: number;
  age: number;
}

interface PointCloud3DProps {
  points: Point3DData[];
  colorMode: 'snr' | 'height' | 'doppler' | 'age';
  xRange: [number, number];
  yRange: [number, number];
  zRange: [number, number];
}

export function PointCloud3D({
  points,
  colorMode,
  xRange = [-6, 6],
  yRange = [0, 10],
  zRange = [-3, 3]
}: PointCloud3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const pointsRef = useRef<THREE.Points | null>(null);

  // Initialize Three.js scene
  useEffect(() => {
    if (!containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a2e);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 5, 10);
    camera.lookAt(0, 0, 0);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    containerRef.current.appendChild(renderer.domElement);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Grid helper
    const gridHelper = new THREE.GridHelper(20, 20, 0x444444, 0x222222);
    scene.add(gridHelper);

    // Axis helper
    const axesHelper = new THREE.AxesHelper(5);
    scene.add(axesHelper);

    // Bounding box
    const boxGeometry = new THREE.BoxGeometry(
      xRange[1] - xRange[0],
      zRange[1] - zRange[0],
      yRange[1] - yRange[0]
    );
    const boxEdges = new THREE.EdgesGeometry(boxGeometry);
    const boxLines = new THREE.LineSegments(
      boxEdges,
      new THREE.LineBasicMaterial({ color: 0x4a9eff })
    );
    boxLines.position.set(
      (xRange[0] + xRange[1]) / 2,
      (zRange[0] + zRange[1]) / 2,
      (yRange[0] + yRange[1]) / 2
    );
    scene.add(boxLines);

    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Cleanup
    return () => {
      renderer.dispose();
      containerRef.current?.removeChild(renderer.domElement);
    };
  }, []);

  // Update points
  useEffect(() => {
    if (!sceneRef.current || points.length === 0) return;

    // Remove old points
    if (pointsRef.current) {
      sceneRef.current.remove(pointsRef.current);
      pointsRef.current.geometry.dispose();
      (pointsRef.current.material as THREE.Material).dispose();
    }

    // Create new point cloud
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(points.length * 3);
    const colors = new Float32Array(points.length * 3);

    points.forEach((p, i) => {
      // Position (swap y/z for Three.js coordinate system)
      positions[i * 3] = p.x;
      positions[i * 3 + 1] = p.z;  // Height
      positions[i * 3 + 2] = p.y;  // Depth

      // Color based on mode
      const color = getPointColor(p, colorMode);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    });

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
      size: 0.1,
      vertexColors: true,
      transparent: true,
      opacity: 0.8
    });

    const pointsMesh = new THREE.Points(geometry, material);
    sceneRef.current.add(pointsMesh);
    pointsRef.current = pointsMesh;

  }, [points, colorMode]);

  return <div ref={containerRef} style={{ width: '100%', height: '400px' }} />;
}

function getPointColor(point: Point3DData, mode: string): THREE.Color {
  const color = new THREE.Color();

  switch (mode) {
    case 'snr':
      // Green (low SNR) to Red (high SNR)
      const snrNorm = Math.min(1, Math.max(0, point.snr / 30));
      color.setHSL(0.33 - snrNorm * 0.33, 1, 0.5);
      break;

    case 'height':
      // Blue (low) to Red (high)
      const heightNorm = (point.z + 3) / 6;  // Assuming z in [-3, 3]
      color.setHSL(0.66 - heightNorm * 0.66, 1, 0.5);
      break;

    case 'doppler':
      // Blue (approaching) to Red (receding)
      const dopplerNorm = (point.doppler + 5) / 10;  // Assuming doppler in [-5, 5]
      color.setHSL(0.66 - dopplerNorm * 0.66, 1, 0.5);
      break;

    case 'age':
      // Bright (new) to dim (old)
      const ageNorm = Math.min(1, point.age / 10);
      color.setHSL(0.5, 1, 0.7 - ageNorm * 0.4);
      break;

    default:
      color.setHex(0x4ecdc4);
  }

  return color;
}
```

---

## 7. Configuration File Format

### 7.1 TI Config File Structure

TI config files are line-based commands sent to the radar CLI port:

```
% Comments start with %
sensorStop
flushCfg
dfeDataOutputMode 1
channelCfg 15 5 0
adcCfg 2 1
adcbufCfg -1 0 1 1 1
profileCfg 0 60 567 7 57.14 0 0 70 1 256 5209 0 0 30
chirpCfg 0 0 0 0 0 0 0 1
chirpCfg 1 1 0 0 0 0 0 4
frameCfg 0 1 16 0 50 1 0
lowPower 0 0
guiMonitor -1 1 1 0 0 0 1
cfarCfg -1 0 2 8 4 3 0 15 1
cfarCfg -1 1 0 4 2 3 1 15 1
multiObjBeamForming -1 1 0.5
clutterRemoval -1 0
calibDcRangeSig -1 0 -5 8 256
extendedMaxVelocity -1 0
bpmCfg -1 0 0 1
lvdsStreamCfg -1 0 0 0
compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0
measureRangeBiasAndRxChanPhase 0 1.5 0.2
CQRxSatMonitor 0 3 5 121 0
CQSigImgMonitor 0 127 4
analogMonitor 0 0
aoaFovCfg -1 -90 90 -90 90
cfarFovCfg -1 0 0 8.92
cfarFovCfg -1 1 -1 1.00
calibData 0 0 0
sensorStart
```

### 7.2 Key Configuration Commands

```python
# Configuration command parsers
CONFIG_COMMANDS = {
    'channelCfg': {
        'args': ['rx_mask', 'tx_mask', 'cascading'],
        'help': 'Configure RX/TX antenna channels'
    },
    'profileCfg': {
        'args': ['id', 'start_freq', 'idle_time', 'adc_start', 'ramp_end',
                 'tx0_power', 'tx1_power', 'tx2_power', 'tx0_phase',
                 'freq_slope', 'tx_start_time', 'adc_samples', 'sample_rate',
                 'hpf1', 'hpf2'],
        'help': 'Chirp profile configuration'
    },
    'frameCfg': {
        'args': ['chirp_start', 'chirp_end', 'num_loops', 'num_frames',
                 'frame_period_ms', 'trigger_select', 'trigger_delay'],
        'help': 'Frame configuration'
    },
    'guiMonitor': {
        'args': ['subframe', 'detected_obj', 'log_mag_range', 'noise_profile',
                 'range_azimuth', 'range_doppler', 'stats'],
        'help': 'Enable/disable TLV outputs'
    },
    'cfarCfg': {
        'args': ['subframe', 'proc_direction', 'mode', 'noise_win', 'guard_len',
                 'div_shift', 'cyclic_mode', 'threshold_scale', 'peak_grouping'],
        'help': 'CFAR detection configuration'
    },
    'trackingCfg': {
        'args': ['enable', 'max_tracks', 'reserved1', 'reserved2', 'reserved3',
                 'reserved4', 'association_snr', 'forget_snr', 'forget_time'],
        'help': 'Object tracking configuration'
    },
    'vitalsCfg': {
        'args': ['subframe', 'enable', 'range_start', 'range_end', 'reserved'],
        'help': 'Vital signs monitoring configuration'
    }
}
```

### 7.3 Config Parser for AMBIENT

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import re

@dataclass
class RadarConfig:
    """Parsed radar configuration."""

    # Channel configuration
    rx_channels: int = 15  # Bitmask
    tx_channels: int = 5   # Bitmask

    # Profile
    start_freq_ghz: float = 60.0
    freq_slope_mhz_us: float = 70.0
    adc_samples: int = 256
    sample_rate_ksps: int = 5209

    # Frame
    chirps_per_frame: int = 16
    frame_period_ms: float = 50.0

    # CFAR
    cfar_threshold_db: float = 15.0

    # Tracking
    max_tracks: int = 5
    tracking_enabled: bool = True

    # Vitals
    vitals_enabled: bool = False
    vitals_range_start_m: float = 0.1
    vitals_range_end_m: float = 4.5

    # GUI Monitor (TLV enables)
    tlv_detected_points: bool = True
    tlv_range_profile: bool = True
    tlv_range_doppler: bool = False

    # Raw commands (for pass-through)
    raw_commands: List[str] = field(default_factory=list)

def parse_config_file(filepath: str) -> RadarConfig:
    """Parse TI radar configuration file."""
    config = RadarConfig()

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('%'):
                continue

            # Store raw command
            config.raw_commands.append(line)

            # Parse known commands
            parts = line.split()
            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            try:
                if cmd == 'channelCfg':
                    config.rx_channels = int(args[0])
                    config.tx_channels = int(args[1])

                elif cmd == 'profileCfg':
                    config.start_freq_ghz = float(args[1])
                    config.freq_slope_mhz_us = float(args[9])
                    config.adc_samples = int(args[11])
                    config.sample_rate_ksps = int(args[12])

                elif cmd == 'frameCfg':
                    config.chirps_per_frame = int(args[2])
                    config.frame_period_ms = float(args[4])

                elif cmd == 'cfarCfg' and args[1] == '0':  # Range CFAR
                    config.cfar_threshold_db = float(args[7])

                elif cmd == 'trackingCfg':
                    config.tracking_enabled = int(args[0]) == 1
                    config.max_tracks = int(args[1])

                elif cmd == 'guiMonitor':
                    config.tlv_detected_points = int(args[1]) == 1
                    config.tlv_range_profile = int(args[2]) == 1
                    config.tlv_range_doppler = int(args[5]) == 1

                elif cmd == 'vitalsCfg':
                    config.vitals_enabled = int(args[1]) == 1
                    config.vitals_range_start_m = float(args[2])
                    config.vitals_range_end_m = float(args[3])

            except (IndexError, ValueError):
                pass  # Ignore parsing errors, keep raw command

    return config
```

---

## 8. Signal Processing Pipeline

### 8.1 Complete Processing Chain

```python
import numpy as np
from scipy import signal
from typing import Optional, Tuple

class VitalsProcessor:
    """
    Complete vital signs processing pipeline.

    Implements TI's algorithm with enhancements for AMBIENT.
    """

    def __init__(
        self,
        sample_rate: float = 20.0,
        window_seconds: float = 10.0,
        hr_range: Tuple[float, float] = (0.8, 3.0),  # Hz (48-180 BPM)
        rr_range: Tuple[float, float] = (0.1, 0.6),  # Hz (6-36 BPM)
    ):
        self.sample_rate = sample_rate
        self.window_size = int(sample_rate * window_seconds)
        self.hr_range = hr_range
        self.rr_range = rr_range

        # Phase unwrapper
        self.phase_unwrapper = PhaseUnwrapper()

        # Buffers
        self.phase_buffer = np.zeros(self.window_size)
        self.buffer_idx = 0
        self.samples_received = 0

        # Filters (Butterworth bandpass, order 4)
        self.hr_filter = self._create_bandpass(hr_range[0], hr_range[1])
        self.rr_filter = self._create_bandpass(rr_range[0], rr_range[1])

        # Filter states
        self.hr_zi = None
        self.rr_zi = None

    def _create_bandpass(self, low: float, high: float) -> Tuple:
        """Create Butterworth bandpass filter coefficients."""
        nyquist = self.sample_rate / 2
        low_norm = low / nyquist
        high_norm = min(high / nyquist, 0.99)  # Avoid edge effects

        b, a = signal.butter(4, [low_norm, high_norm], btype='band')
        return (b, a)

    def add_sample(self, phase: float) -> Optional[dict]:
        """
        Add a phase sample and return vitals if enough data.

        Args:
            phase: Raw phase value (radians, may be wrapped)

        Returns:
            Vitals dict if estimation possible, None otherwise
        """
        # Unwrap phase
        unwrapped = self.phase_unwrapper.unwrap(phase)

        # Add to circular buffer
        self.phase_buffer[self.buffer_idx] = unwrapped
        self.buffer_idx = (self.buffer_idx + 1) % self.window_size
        self.samples_received += 1

        # Need at least 5 seconds of data
        if self.samples_received < self.sample_rate * 5:
            return None

        return self.estimate_vitals()

    def estimate_vitals(self) -> dict:
        """Estimate heart rate and respiratory rate from buffer."""

        # Reorder buffer to chronological order
        if self.samples_received >= self.window_size:
            phase_signal = np.roll(self.phase_buffer, -self.buffer_idx)
        else:
            phase_signal = self.phase_buffer[:self.samples_received]

        # Compute phase differences (velocity proxy)
        phase_diff = np.diff(phase_signal)

        # Apply bandpass filters
        hr_filtered = signal.filtfilt(*self.hr_filter, phase_diff)
        rr_filtered = signal.filtfilt(*self.rr_filter, phase_diff)

        # FFT for rate estimation
        hr_bpm, hr_snr, hr_confidence = self._estimate_rate(
            hr_filtered, self.hr_range, use_harmonic=True
        )
        rr_bpm, rr_snr, rr_confidence = self._estimate_rate(
            rr_filtered, self.rr_range, use_harmonic=False
        )

        # Compute breathing deviation (presence indicator)
        breathing_deviation = np.var(rr_filtered[-40:]) if len(rr_filtered) >= 40 else 0

        # Motion detection
        phase_stability = np.std(np.diff(phase_signal[-20:])) if len(phase_signal) >= 20 else 1.0
        motion_detected = phase_stability > 0.5

        # Compute overall quality
        signal_quality = min(hr_confidence, rr_confidence)
        if motion_detected:
            signal_quality *= 0.5

        return {
            'heart_rate_bpm': hr_bpm if hr_confidence > 0.3 else None,
            'hr_confidence': hr_confidence,
            'hr_snr_db': hr_snr,
            'respiratory_rate_bpm': rr_bpm if rr_confidence > 0.3 else None,
            'rr_confidence': rr_confidence,
            'rr_snr_db': rr_snr,
            'breathing_deviation': breathing_deviation,
            'motion_detected': motion_detected,
            'phase_stability': phase_stability,
            'signal_quality': signal_quality,
            'unwrapped_phase': phase_signal[-1] if len(phase_signal) > 0 else 0,
            'heart_waveform': hr_filtered[-150:].tolist(),
            'breath_waveform': rr_filtered[-150:].tolist(),
            'phase_signal': phase_diff[-200:].tolist(),
        }

    def _estimate_rate(
        self,
        filtered_signal: np.ndarray,
        freq_range: Tuple[float, float],
        use_harmonic: bool = False
    ) -> Tuple[float, float, float]:
        """
        Estimate rate from filtered signal using FFT.

        Args:
            filtered_signal: Bandpass filtered phase signal
            freq_range: (low_hz, high_hz) frequency range
            use_harmonic: Use harmonic product spectrum (for heart rate)

        Returns:
            (rate_bpm, snr_db, confidence)
        """
        if len(filtered_signal) < 64:
            return 0.0, 0.0, 0.0

        # Zero-pad to power of 2
        n_fft = 512
        padded = np.zeros(n_fft)
        padded[:len(filtered_signal)] = filtered_signal

        # Apply window
        window = signal.windows.hann(len(filtered_signal))
        padded[:len(filtered_signal)] *= window

        # FFT
        spectrum = np.abs(np.fft.rfft(padded))
        freqs = np.fft.rfftfreq(n_fft, 1/self.sample_rate)

        # Find frequency range indices
        low_idx = np.searchsorted(freqs, freq_range[0])
        high_idx = np.searchsorted(freqs, freq_range[1])

        if low_idx >= high_idx:
            return 0.0, 0.0, 0.0

        # Harmonic product spectrum for heart rate
        if use_harmonic and len(spectrum) >= high_idx * 2:
            # Multiply spectrum with decimated version
            max_idx = min(len(spectrum), high_idx * 2)
            decimated = spectrum[:max_idx:2]
            product_len = min(len(spectrum[:max_idx]), len(decimated))
            harmonic_spectrum = spectrum[:product_len] * decimated[:product_len]
            search_spectrum = harmonic_spectrum[low_idx:min(high_idx, product_len)]
        else:
            search_spectrum = spectrum[low_idx:high_idx]

        if len(search_spectrum) == 0:
            return 0.0, 0.0, 0.0

        # 3-sample smoothed peak detection (TI method)
        best_idx = 0
        best_value = 0

        for i in range(1, len(search_spectrum) - 1):
            value = search_spectrum[i-1] + search_spectrum[i] + search_spectrum[i+1]
            if value > best_value:
                best_value = value
                best_idx = i

        # Convert to Hz and BPM
        peak_freq = freqs[low_idx + best_idx]
        rate_bpm = peak_freq * 60.0

        # SNR calculation
        noise_floor = np.median(search_spectrum)
        peak_power = search_spectrum[best_idx]
        snr_db = 10 * np.log10(peak_power / (noise_floor + 1e-10))

        # Confidence from SNR
        confidence = min(1.0, max(0.0, (snr_db - 3) / 10))

        return rate_bpm, snr_db, confidence

    def reset(self):
        """Reset processor state."""
        self.phase_buffer.fill(0)
        self.buffer_idx = 0
        self.samples_received = 0
        self.phase_unwrapper.reset()
```

---

## 9. Quality Metrics & Validation

### 9.1 Signal Quality Indicators

```python
@dataclass
class VitalsQualityMetrics:
    """Quality metrics for vital signs estimation."""

    # SNR metrics
    hr_snr_db: float = 0.0
    rr_snr_db: float = 0.0

    # Confidence scores (0-1)
    hr_confidence: float = 0.0
    rr_confidence: float = 0.0

    # Stability metrics
    phase_stability: float = 0.0  # Lower is better
    motion_detected: bool = False

    # Presence detection
    breathing_deviation: float = 0.0
    patient_present: bool = False
    holding_breath: bool = False

    # Overall quality
    signal_quality: float = 0.0  # 0-1 composite score

def compute_quality_metrics(vitals: dict) -> VitalsQualityMetrics:
    """Compute quality metrics from vitals estimation."""

    metrics = VitalsQualityMetrics(
        hr_snr_db=vitals.get('hr_snr_db', 0),
        rr_snr_db=vitals.get('rr_snr_db', 0),
        hr_confidence=vitals.get('hr_confidence', 0),
        rr_confidence=vitals.get('rr_confidence', 0),
        phase_stability=vitals.get('phase_stability', 1),
        motion_detected=vitals.get('motion_detected', False),
        breathing_deviation=vitals.get('breathing_deviation', 0),
    )

    # Presence detection (TI thresholds)
    if metrics.breathing_deviation == 0:
        metrics.patient_present = False
        metrics.holding_breath = False
    elif metrics.breathing_deviation >= 0.02:
        metrics.patient_present = True
        metrics.holding_breath = False
    else:
        metrics.patient_present = True
        metrics.holding_breath = True

    # Composite quality score
    metrics.signal_quality = compute_composite_quality(metrics)

    return metrics

def compute_composite_quality(metrics: VitalsQualityMetrics) -> float:
    """Compute composite quality score (0-1)."""

    if not metrics.patient_present:
        return 0.0

    # Weight different factors
    quality = 1.0

    # SNR contribution (expect > 6 dB for good signal)
    hr_snr_factor = min(1.0, max(0.0, metrics.hr_snr_db / 12))
    rr_snr_factor = min(1.0, max(0.0, metrics.rr_snr_db / 10))
    quality *= (hr_snr_factor + rr_snr_factor) / 2

    # Confidence contribution
    quality *= (metrics.hr_confidence + metrics.rr_confidence) / 2

    # Motion penalty
    if metrics.motion_detected:
        quality *= 0.3

    # Stability contribution
    stability_factor = max(0.0, 1.0 - metrics.phase_stability)
    quality *= (0.5 + 0.5 * stability_factor)

    # Holding breath penalty
    if metrics.holding_breath:
        quality *= 0.7

    return min(1.0, max(0.0, quality))
```

---

## 10. Integration Recommendations

### 10.1 Priority Implementation Order

1. **High Priority** (Essential for vital signs):
   - [ ] Vital Signs TLV (1040) parser
   - [ ] Harmonic product spectrum for HR
   - [ ] 3-sample smoothed peak detection
   - [ ] Multi-patient support (if needed)

2. **Medium Priority** (Enhanced functionality):
   - [ ] Point cloud accumulation/persistence
   - [ ] Tracked objects TLV (250) parser
   - [ ] Compressed points TLV (253) parser
   - [ ] 3D visualization with Three.js

3. **Low Priority** (Nice to have):
   - [ ] Fall detection algorithm
   - [ ] Gesture recognition TLVs
   - [ ] Full config file parser

### 10.2 AMBIENT-Specific Modifications

**Backend (`src/ambient/sensor/frame.py`)**:
```python
# Add TLV 1040 to parse_tlv method
elif tlv_type == 1040:  # Vital Signs
    return self._parse_vital_signs_tlv(tlv_data)
```

**Backend (`src/ambient/vitals/extractor.py`)**:
```python
# Add harmonic product spectrum option
def estimate_heart_rate(self, phase_signal, use_harmonic=True):
    if use_harmonic:
        return self._harmonic_product_estimate(phase_signal)
    else:
        return self._simple_fft_estimate(phase_signal)
```

**Frontend (`dashboard/src/types/sensor.ts`)**:
```typescript
// Add multi-patient support
interface MultiPatientVitals {
  patients: PatientVitals[];
}

interface PatientVitals {
  patient_id: number;
  status: 'present' | 'holding_breath' | 'not_detected';
  heart_rate_bpm: number | null;
  respiratory_rate_bpm: number | null;
  // ... other fields
}
```

**API Schema (`src/ambient/api/schemas.py`)**:
```python
# Add vital signs TLV schema
class VitalSignsTLV(BaseModel):
    patient_id: int
    range_bin: int
    breathing_deviation: float
    heart_rate_bpm: float
    breathing_rate_bpm: float
    heart_waveform: List[float]
    breath_waveform: List[float]
```

### 10.3 Testing Recommendations

1. **Use TI's vital signs config files**:
   - `vital_signs_AOP_2m.cfg` for close range
   - `vital_signs_AOP_6m.cfg` for extended range

2. **Validate against TI visualizer**:
   - Run both systems simultaneously
   - Compare HR/RR readings
   - Check waveform correlation

3. **Test edge cases**:
   - No patient present
   - Patient holding breath
   - Motion during measurement
   - Multiple patients (if supported)

---

## Appendix: File Locations in TI Toolbox

```
/home/baxter/mmwave/radar_toolbox_3_30_00_06/
├── tools/visualizers/Applications_Visualizer/
│   ├── common/
│   │   ├── parseTLVs.py           # TLV parsing reference
│   │   ├── gui_core.py            # Main GUI logic
│   │   ├── Demo_Classes/
│   │   │   ├── vital_signs.py     # Vital signs visualization
│   │   │   └── people_tracking.py # Point cloud & tracking
│   │   └── Common_Tabs/
│   │       ├── plot_3d.py         # 3D point cloud
│   │       └── plot_1d.py         # Range profile
│   └── Vital_Signs_Visualizer/    # Dedicated vitals app
│       ├── gui_main.py
│       └── configs/
│
└── source/ti/examples/Industrial_and_Personal_Electronics/
    └── Vital_Signs/
        ├── IWRL6432_Vital_Signs/src/6432/
        │   ├── vitalsign.c        # Firmware algorithm
        │   └── vitalsign.h        # Constants & defines
        └── Vital_Signs_With_People_Tracking/
            ├── prebuilt_binaries/
            │   └── vital_signs_tracking_6843AOP_demo.bin
            └── chirp_configs/
                └── vital_signs_AOP_2m.cfg
```

---

## Questions?

This document covers the core functionality. For specific implementation details or additional features, refer to the source files listed above or the TI mmWave SDK documentation.

**Document Version**: 1.0
**Last Updated**: January 2026
**Target AMBIENT Version**: 0.5.0+
