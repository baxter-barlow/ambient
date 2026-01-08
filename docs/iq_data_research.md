# I/Q Data Acquisition Options for IWR6843AOPEVM

## Executive Summary

The current "ambient" implementation uses TI's Out-of-Box (OOB) demo firmware, which only outputs **magnitude data** (not complex I/Q). This is a fundamental limitation for vital signs detection, which requires phase information to track sub-millimeter chest displacement.

**Key Finding**: The TI **Vital Signs Demo** firmware is the recommended path forward. It:
- Outputs pre-computed phase/displacement waveforms via TLV type `0x410`
- Runs entirely on the radar SoC (no external hardware needed)
- Is specifically designed for respiratory rate and heart rate detection
- Supports IWR6843AOPEVM directly

The magnitude-variation workaround currently in `pipeline.py` can detect breathing but lacks the sensitivity and accuracy of true phase-based detection.

---

## Option Comparison Table

| Option | Hardware Required | Complexity | Phase Quality | Latency | Cost |
|--------|------------------|------------|---------------|---------|------|
| **Vital Signs Demo** | None (firmware flash only) | Low | High (unwrapped phase) | Low | $0 |
| **LVDS + DCA1000EVM** | DCA1000EVM board | High | Raw ADC (highest) | Medium | ~$500 |
| **Custom CCS Firmware** | JTAG debugger | Very High | Configurable | Low | ~$100 |
| **Magnitude Variation** (current) | None | Already done | Poor (proxy only) | Low | $0 |

---

## Detailed Options

### Option 1: TI Vital Signs Demo (Recommended)

**Description**: Flash the IWR6843AOPEVM with TI's Vital Signs with People Tracking demo firmware. This demo performs on-chip phase extraction and outputs vital signs data via UART.

**Location in Radar Toolbox**:
```
radar_toolbox_1_20_00_11/source/ti/examples/Medical/Vital_Signs_With_People_Tracking/
```

**TLV Output Format**:
- TLV Type `0x410` (1040): Vital Signs output
- 136 bytes containing:
  - Unwrapped phase waveform
  - Breathing waveform (filtered)
  - Heart waveform (filtered)
  - Breathing rate (BPM)
  - Heart rate (BPM)
  - Confidence metrics

**Pros**:
- Zero additional hardware cost
- Low integration complexity
- Phase unwrapping handled on-chip
- Breathing/heart rate already computed
- Well-documented by TI

**Cons**:
- Less flexibility than raw ADC
- Algorithm parameters may need tuning
- Firmware must be reflashed

**Integration Steps**:
1. Download Radar Toolbox from TI
2. Flash vital signs binary via UniFlash
3. Update `frame.py` to parse TLV type `0x410`
4. Remove magnitude-variation workaround in `pipeline.py`

---

### Option 2: LVDS Raw ADC Streaming

**Description**: Stream raw ADC samples over LVDS to DCA1000EVM capture card. Provides complete control over signal processing.

**Hardware**:
- DCA1000EVM (~$500)
- 60-pin ribbon cable (included with DCA1000)
- Ethernet connection to host PC

**IWR6843AOPEVM Support**: Yes - the AOPEVM variant has the 60-pin LVDS connector (J5) exposed.

**Data Rate**: ~40 MB/s typical for vital signs configs

**Pros**:
- Full raw I/Q data access
- Maximum flexibility for custom algorithms
- Can capture data for offline analysis

**Cons**:
- Significant additional cost
- High bandwidth requirements
- Complex setup and synchronization
- Requires custom DSP pipeline

---

### Option 3: Custom CCS Firmware

**Description**: Modify the mmWave SDK source to output complex range FFT data via UART instead of just magnitude.

**Requirements**:
- Code Composer Studio (CCS)
- XDS110 JTAG debugger (~$100)
- mmWave SDK source code
- C/DSP programming expertise

**Pros**:
- Complete customization
- Can add phase output to existing OOB demo
- No recurring hardware cost

**Cons**:
- Steep learning curve
- Long development time
- Must maintain custom firmware

---

### Option 4: Magnitude Variation (Current Implementation)

**Description**: Current workaround in `pipeline.py` uses magnitude variation at target range bin as a proxy for displacement.

```python
# Current implementation in pipeline.py
magnitude = float(range_profile[bin_idx])
self._phase_history.append(magnitude)
mean_mag = np.mean(self._phase_history)
phase = (magnitude - mean_mag) * 0.1  # Scale to phase-like range
```

**Pros**:
- Already implemented
- No hardware or firmware changes

**Cons**:
- Low sensitivity (can't detect sub-mm motion)
- Affected by range bin power fluctuations
- Cannot measure true phase/displacement
- Heart rate detection unlikely

---

## Recommended Path Forward

### Immediate Action: Flash Vital Signs Demo

1. **Download TI Radar Toolbox**
   - URL: https://www.ti.com/tool/RADAR-TOOLBOX
   - Requires TI account (free)

2. **Locate Firmware**
   ```
   radar_toolbox/source/ti/examples/Medical/Vital_Signs_With_People_Tracking/
   └── prebuilt_binaries/
       └── iwr6843aopevm/
           └── vital_signs_with_people_tracking.bin
   ```

3. **Flash via UniFlash**
   - Set device to flashing mode (SOP jumpers)
   - Use UniFlash to program the .bin file

4. **Update Frame Parser**
   Add TLV type 0x410 parsing to `src/ambient/sensor/frame.py`:
   ```python
   TLV_TYPE_VITAL_SIGNS = 0x410  # 1040

   @dataclass
   class VitalSignsData:
       unwrapped_phase: float
       breathing_waveform: float
       heart_waveform: float
       breathing_rate: float
       heart_rate: float
       breathing_confidence: float
       heart_confidence: float
   ```

5. **Update Processing Pipeline**
   Replace magnitude-variation logic with direct vital signs consumption.

### Future Consideration: DCA1000EVM

If the vital signs demo doesn't meet requirements (e.g., need custom algorithms or research flexibility), invest in DCA1000EVM for raw ADC access.

---

## Links and References

### TI Official Resources
- [Radar Toolbox Download](https://www.ti.com/tool/RADAR-TOOLBOX)
- [IWR6843AOPEVM Product Page](https://www.ti.com/tool/IWR6843AOPEVM)
- [Vital Signs Lab User Guide (TIDUEN3)](https://www.ti.com/lit/ug/tiduen3/tiduen3.pdf)
- [mmWave SDK User Guide](https://www.ti.com/lit/ug/swru546e/swru546e.pdf)
- [DCA1000EVM User Guide](https://www.ti.com/lit/ug/spruij4a/spruij4a.pdf)

### GitHub Projects
- [mmVital-Signs](https://github.com/ConnectedSystemsLab/mmVital-Signs) - Phase-based vital signs with IWR6843
- [bigheadG/mmWave](https://github.com/bigheadG/mmWave) - Python library supporting vital signs TLV
- [nhma20/iwr6843aop_pub](https://github.com/nhma20/iwr6843aop_pub) - ROS driver for IWR6843AOPEVM
- [openradarinitiative/open_radar_initiative](https://github.com/openradarinitiative/open_radar_initiative) - Open radar platform

### Academic References
- TI Application Note: "Vital Signs Measurement Using Millimeter Wave Radars" (SWRA657)
- "Remote Monitoring of Breathing and Heartbeat Using mmWave Radar" - IEEE Sensors Journal

### Community Resources
- [TI E2E mmWave Forum](https://e2e.ti.com/support/sensors/f/sensors-forum)
- [TI mmWave Training Series](https://training.ti.com/mmwave-training-series)

---

## Appendix: TLV Type 0x410 Format

Based on TI vital signs demo source code:

```c
typedef struct VitalSignsOutput {
    float unwrappedPhasePeak;     // Unwrapped phase at target
    float breathingWaveform;       // Filtered breathing signal
    float heartWaveform;           // Filtered heart signal
    float breathingRateFft;        // Breathing rate from FFT (BPM)
    float heartRateFft;            // Heart rate from FFT (BPM)
    float breathingConfidence;     // 0-1 confidence score
    float heartConfidence;         // 0-1 confidence score
    uint32_t reserved[26];         // Padding to 136 bytes
} VitalSignsOutput_t;
```

Total size: 136 bytes (verified in multiple sources)
