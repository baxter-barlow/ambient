# TLV Specification

Type-Length-Value (TLV) format specification for mmWave radar data frames.

## Frame Structure

```
+------------------+
| Magic Word (8)   |  0x0201 0x0403 0x0605 0x0807
+------------------+
| Header (32)      |
+------------------+
| TLV 1            |
+------------------+
| TLV 2            |
+------------------+
| ...              |
+------------------+
```

### Frame Header (40 bytes total, 32 after magic)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 8 | magic_word | Sync bytes: 02 01 04 03 06 05 08 07 |
| 8 | 4 | version | Platform version |
| 12 | 4 | packet_length | Total packet size in bytes |
| 16 | 4 | platform | Platform identifier (0x6843 = IWR6843) |
| 20 | 4 | frame_number | Sequential frame counter |
| 24 | 4 | time_cpu_cycles | CPU timestamp |
| 28 | 4 | num_detected_obj | Number of detected objects |
| 32 | 4 | num_tlvs | Number of TLVs in frame |
| 36 | 4 | subframe_number | Subframe index (usually 0) |

### TLV Header (8 bytes)

| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 4 | type | uint32 - TLV type identifier |
| 4 | 4 | length | uint32 - TLV data length (excluding header) |

---

## Standard TI TLV Types

### TLV Type 1: DETECTED_POINTS

Point cloud data from CFAR detection.

**Format (16 bytes per point):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 4 | x | float32 - X position (meters) |
| 4 | 4 | y | float32 - Y position (meters) |
| 8 | 4 | z | float32 - Z position (meters) |
| 12 | 4 | velocity | float32 - Doppler velocity (m/s) |

**Extended Format (24 bytes per point):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 4 | x | float32 |
| 4 | 4 | y | float32 |
| 8 | 4 | z | float32 |
| 12 | 4 | velocity | float32 |
| 16 | 4 | snr | float32 - Signal-to-noise ratio |
| 20 | 4 | noise | float32 - Noise level |

### TLV Type 2: RANGE_PROFILE

Range FFT magnitude profile.

**Format:**
- Array of uint16 magnitude values
- Number of bins = length / 2
- Values in linear scale (convert to dB: 20 * log10(value + 1))

### TLV Type 3: NOISE_PROFILE

Noise floor estimate per range bin.

**Format:** Same as RANGE_PROFILE

### TLV Type 5: RANGE_DOPPLER

2D range-Doppler heatmap.

**Format:**
- Array of uint16 magnitude values
- Row-major order
- Typically square (e.g., 64x64, 128x128)
- Convert to dB for visualization

### TLV Type 6: STATS

Frame statistics.

**Format (24 bytes):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 4 | interframe_proc_time | uint32 - Processing time (us) |
| 4 | 4 | transmit_out_time | uint32 |
| 8 | 4 | interframe_proc_margin | uint32 |
| 12 | 4 | interchirp_proc_margin | uint32 |
| 16 | 4 | active_frame_cpu_load | uint32 |
| 20 | 4 | interframe_cpu_load | uint32 |

---

## TI Vital Signs TLV (0x410 / 1040)

Output from TI Vital Signs demo firmware.

### 192-byte Format (Full)

| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 2 | range_bin_index | uint16 - Target range bin |
| 2 | 2 | reserved | uint16 |
| 4 | 4 | breathing_deviation | float32 - Chest displacement (mm) |
| 8 | 4 | heart_deviation | float32 - Heart displacement (mm) |
| 12 | 4 | breathing_rate | float32 - Breaths per minute |
| 16 | 4 | heart_rate | float32 - Beats per minute |
| 20 | 4 | breathing_confidence | float32 - 0.0 to 1.0 |
| 24 | 4 | heart_confidence | float32 - 0.0 to 1.0 |
| 28 | 80 | breathing_waveform | float32[20] - Filtered signal |
| 108 | 80 | heart_waveform | float32[20] - Filtered signal |
| 188 | 4 | unwrapped_phase | float32 - Phase (radians) |

### 136-byte Format (Compact)

Same structure but with 10-sample waveforms (40 bytes each).

---

## Chirp Custom TLV Types

### TLV Type 0x0500: COMPLEX_RANGE_FFT

Full I/Q data for all range bins.

**Header (8 bytes):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 2 | num_range_bins | uint16 |
| 2 | 2 | chirp_index | uint16 |
| 4 | 2 | rx_antenna | uint16 |
| 6 | 2 | reserved | uint16 |

**Data (4 bytes per bin):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 2 | imag | int16 - Imaginary part |
| 2 | 2 | real | int16 - Real part |

**Usage:**
```python
if frame.chirp_complex_fft:
    iq = frame.chirp_complex_fft.iq_data  # np.complex64 array
    magnitude = np.abs(iq)
    phase = np.angle(iq)
```

### TLV Type 0x0510: TARGET_IQ

I/Q for selected target bins only.

**Header (8 bytes):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 2 | num_bins | uint16 |
| 2 | 2 | center_bin | uint16 - Primary target bin |
| 4 | 4 | timestamp_us | uint32 - Microsecond timestamp |

**Per-Bin Data (8 bytes each):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 2 | bin_index | uint16 |
| 2 | 2 | imag | int16 |
| 4 | 2 | real | int16 |
| 6 | 2 | reserved | uint16 |

**Usage:**
```python
if frame.chirp_target_iq:
    for i, idx in enumerate(frame.chirp_target_iq.bin_indices):
        iq = frame.chirp_target_iq.iq_data[i]
        print(f"Bin {idx}: {iq}")
```

### TLV Type 0x0520: PHASE_OUTPUT (Primary)

Pre-computed phase and magnitude for vital signs extraction.

**Header (8 bytes):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 2 | num_bins | uint16 |
| 2 | 2 | center_bin | uint16 |
| 4 | 4 | timestamp_us | uint32 |

**Per-Bin Data (8 bytes each):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 2 | bin_index | uint16 |
| 2 | 2 | phase_q15 | int16 - Phase * 32768 / pi |
| 4 | 2 | magnitude | uint16 - Linear magnitude |
| 6 | 2 | flags | uint16 - Bit 0: motion, Bit 1: valid |

**Phase Conversion:**
```python
phase_radians = (phase_q15 / 32768.0) * np.pi
```

**Usage:**
```python
if frame.chirp_phase:
    phase = frame.chirp_phase.get_center_phase()
    for bin in frame.chirp_phase.bins:
        print(f"Bin {bin.bin_index}: phase={bin.phase:.2f}, mag={bin.magnitude}")
```

### TLV Type 0x0540: PRESENCE

Presence detection result.

**Format (8 bytes):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 1 | presence | uint8 - 0=absent, 1=present, 2=motion |
| 1 | 1 | confidence | uint8 - 0-100% |
| 2 | 2 | range_q8 | uint16 - Range * 256 (meters) |
| 4 | 2 | target_bin | uint16 |
| 6 | 2 | reserved | uint16 |

**Range Conversion:**
```python
range_meters = range_q8 / 256.0
```

**Usage:**
```python
if frame.chirp_presence:
    if frame.chirp_presence.is_present:
        print(f"Target at {frame.chirp_presence.range_m:.2f}m")
```

### TLV Type 0x0550: MOTION_STATUS

Motion detection status.

**Format (8 bytes):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 1 | detected | uint8 - Boolean |
| 1 | 1 | level | uint8 - Motion intensity 0-255 |
| 2 | 2 | bin_count | uint16 - Bins with motion |
| 4 | 2 | peak_bin | uint16 - Bin with most motion |
| 6 | 2 | peak_delta | uint16 - Peak motion magnitude |

**Usage:**
```python
if frame.chirp_motion:
    if frame.chirp_motion.motion_detected:
        print(f"Motion level: {frame.chirp_motion.motion_level}")
```

### TLV Type 0x0560: TARGET_INFO

Target selection metadata.

**Format (12 bytes):**
| Offset | Size | Field | Type |
|--------|------|-------|------|
| 0 | 2 | primary_bin | uint16 |
| 2 | 2 | primary_magnitude | uint16 |
| 4 | 2 | range_q8 | uint16 - Range * 256 |
| 6 | 1 | confidence | uint8 - 0-100% |
| 7 | 1 | num_targets | uint8 |
| 8 | 2 | secondary_bin | uint16 |
| 10 | 2 | reserved | uint16 |

---

## TLV Processing Example

```python
from ambient import RadarSensor
from ambient.vitals import ChirpVitalsProcessor

sensor = RadarSensor()
sensor.connect()
sensor.configure("configs/vital_signs.cfg")
sensor.start()

processor = ChirpVitalsProcessor()

for frame in sensor.stream():
    # Check for different TLV types
    if frame.vital_signs:
        # TI firmware vital signs
        print(f"HR: {frame.vital_signs.heart_rate:.0f} BPM")

    elif frame.chirp_phase:
        # Chirp firmware phase output
        vitals = processor.process_frame(frame)
        if vitals.is_valid():
            print(f"HR: {vitals.heart_rate_bpm:.0f} BPM")

    if frame.chirp_presence:
        if frame.chirp_presence.is_present:
            print(f"Person at {frame.chirp_presence.range_m:.1f}m")

    if frame.chirp_motion and frame.chirp_motion.motion_detected:
        print("Motion detected!")
```

---

## Byte Order

All multi-byte values are **little-endian** (Intel format).

```python
import struct
# Reading uint32 little-endian
value = struct.unpack("<I", data[0:4])[0]
# Reading int16 little-endian
value = struct.unpack("<h", data[0:2])[0]
```

---

## Verified TLV Status

| TLV | Type | Status | Notes |
|-----|------|--------|-------|
| DETECTED_POINTS | 1 | Verified | Both 16 and 24 byte formats |
| RANGE_PROFILE | 2 | Verified | uint16 array |
| NOISE_PROFILE | 3 | Verified | uint16 array |
| RANGE_DOPPLER | 5 | Verified | uint16 2D array |
| STATS | 6 | Verified | 24 bytes |
| VITAL_SIGNS | 0x410 | Verified | 136 and 192 byte formats |
| COMPLEX_RANGE_FFT | 0x0500 | Verified | Full I/Q |
| TARGET_IQ | 0x0510 | Verified | Selected bins I/Q |
| PHASE_OUTPUT | 0x0520 | Verified | Primary vital signs |
| PRESENCE | 0x0540 | Verified | Presence detection |
| MOTION_STATUS | 0x0550 | Verified | Motion detection |
| TARGET_INFO | 0x0560 | Verified | Target metadata |
