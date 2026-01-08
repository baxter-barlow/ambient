# Custom CCS Firmware Feasibility Study

## Executive Summary

### Is Custom Firmware Feasible?

**Yes, but with significant caveats.** Custom firmware to output complex I/Q data from the IWR6843AOPEVM is technically feasible and the SDK provides full source code for modification. However, **the Vital Signs demo firmware already outputs complex Range-FFT data**, which may eliminate the need for custom development entirely.

### Estimated Effort

| Approach | Setup Time | Development Time | Total |
|----------|------------|------------------|-------|
| Use Vital Signs Demo (recommended) | 2-4 hours | 4-8 hours | 1-2 days |
| Minimal SDK modification | 8-16 hours | 16-40 hours | 1-2 weeks |
| Full custom data pipeline | 16-40 hours | 80-160 hours | 2-4 weeks |

### Recommended Approach

**Use the TI Vital Signs Demo firmware.** It already outputs complex Range-FFT data (4 bytes per bin: 2 bytes real, 2 bytes imaginary) via UART. This provides the phase information needed for vital signs detection without any custom firmware development.

### Go/No-Go Recommendation

| Path | Recommendation | Rationale |
|------|---------------|-----------|
| Vital Signs Demo | **GO** | Outputs complex data, minimal effort |
| Custom SDK Modification | **CONDITIONAL** | Only if specific requirements not met by VS demo |
| Full Custom Firmware | **NO-GO** | High effort, likely duplicates TI's work |

---

## Technical Deep Dive

### SDK Architecture Overview

The IWR6843 contains two customer-programmable processor cores:

```
┌─────────────────────────────────────────────────────────────┐
│                     IWR6843 Architecture                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────────────────┐   │
│  │ MSS (ARM R4F)    │    │ DSS (C674x DSP)              │   │
│  │ @ 200 MHz        │    │ @ 600 MHz                    │   │
│  │                  │    │                              │   │
│  │ • UART control   │◄──►│ • Signal processing          │   │
│  │ • CLI interface  │    │ • FFT (via HWA)             │   │
│  │ • Data output    │    │ • Detection algorithms       │   │
│  │ • Sensor config  │    │ • Clutter removal            │   │
│  └──────────────────┘    └──────────────────────────────┘   │
│           │                         │                        │
│           ▼                         ▼                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              L3 Memory (768KB)                        │   │
│  │              "Radar Cube" Storage                     │   │
│  │                                                       │   │
│  │    Complex 1D FFT output (Range bins × Chirps)        │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ▲                                   │
│                          │                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Hardware Accelerator (HWA)                    │   │
│  │         • 1D FFT with windowing                       │   │
│  │         • 2D FFT processing                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ▲                                   │
│                          │                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Radar Subsystem (not programmable)            │   │
│  │         • RF transceiver (60-64 GHz)                  │   │
│  │         • ADC (12/14/16-bit)                          │   │
│  │         • Controlled via mmWaveLink API only          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow - Where I/Q is Available

```
Raw ADC        1D FFT           2D FFT          Magnitude       TLV Output
(I/Q inter-    (Complex)        (Complex)       Calculation     (Current)
 leaved)
    │              │                │                │              │
    ▼              ▼                ▼                ▼              ▼
┌───────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐  ┌───────┐
│12-14  │    │           │    │           │    │           │  │uint16 │
│bit ADC│───►│ Range FFT │───►│Doppler FFT│───►│ |FFT|²    │─►│Log Mag│
│ I + Q │    │  (HWA)    │    │  (HWA)    │    │ = I²+Q²   │  │Profile│
└───────┘    └───────────┘    └───────────┘    └───────────┘  └───────┘
                  │                │
                  ▼                ▼
             ┌────────┐       ┌────────┐
             │Complex │       │Complex │
             │ Data   │       │ Data   │
             │AVAILABLE│      │AVAILABLE│
             │in L3   │       │(depends)│
             └────────┘       └────────┘
                  │
                  ├── Vital Signs Demo: Outputs this! ◄── USE THIS
                  │
                  └── OOB Demo: Only outputs magnitude
```

### Critical Finding: Vital Signs Demo Output

The TI Vital Signs demo **already outputs complex Range-FFT data** via UART:

```c
// From TI documentation - Vital Signs demo output format
// Each complex range FFT bin = 4 bytes:
typedef struct {
    int16_t real;  // 2 bytes - real component
    int16_t imag;  // 2 bytes - imaginary component
} ComplexRangeBin;

// Phase can be computed as:
// phase = atan2(imag, real)
```

This is precisely what's needed for vital signs phase extraction!

### SDK Source Code Locations

```
C:\ti\mmwave_sdk_03_xx_xx_xx\
├── packages\
│   └── ti\
│       ├── demo\
│       │   └── xwr68xx\
│       │       └── mmw\              ◄── OOB Demo source
│       │           ├── mss\
│       │           │   └── mss_main.c   ◄── UART output code here
│       │           ├── dss\
│       │           │   └── dss_main.c   ◄── DSP processing
│       │           └── common\
│       │
│       ├── datapath\
│       │   └── dpc\
│       │       └── objectdetection\
│       │           └── objdethwa\
│       │               └── src\
│       │                   └── objectdetection.c  ◄── DPC config
│       │
│       └── control\
│           └── mmwavelink\           ◄── Radar subsystem API
│
└── docs\
    └── mmwave_sdk_user_guide.pdf     ◄── Essential documentation
```

### Key Modification Points

If custom modification is needed, these are the specific locations:

1. **TLV Output** - `mss_main.c`:
   ```c
   void MmwDemo_transmitProcessedOutput(...)
   {
       // Add custom TLV type here
       // Access radar cube from L3 memory
       UART_writePolling(uartHandle, (uint8_t*)&L3_data_address, L3_data_length);
   }
   ```

2. **Custom TLV Type Definition**:
   ```c
   // In mmw_output.h or similar
   #define MMWDEMO_OUTPUT_MSG_COMPLEX_RANGE_FFT  0x500  // Custom TLV ID
   ```

3. **L3 Memory Access**:
   ```c
   // Radar cube address from gMmwMssMCB global variable
   // Or hardcoded from memory map (0x51000000 typically)
   ```

---

## Bandwidth Analysis

### UART Throughput Limits

| Baud Rate | Max Throughput | Notes |
|-----------|----------------|-------|
| 921,600 bps | ~92 KB/s | CP210x USB limit (standard) |
| 1,834,000 bps | ~183 KB/s | Custom driver required |
| 3,125,000 bps | ~312 KB/s | Hardware maximum |

### Data Rate Calculations

Assuming typical vital signs configuration:
- 256 range bins
- 20 fps frame rate (50ms period)
- Complex data = 4 bytes per bin (int16 real + int16 imag)

| Data Type | Calculation | Rate | UART Feasible? |
|-----------|-------------|------|----------------|
| 1D Range FFT (1 chirp) | 256 × 4 × 20 | **20.5 KB/s** | ✅ Yes |
| 1D Range FFT (all chirps) | 256 × 4 × 64 × 20 | 1.31 MB/s | ❌ No |
| Range-Doppler (full) | 256 × 64 × 4 × 10 | 6.55 MB/s | ❌ No (need LVDS) |
| Raw ADC (typical) | 256 × 64 × 4 × 2 × 20 | 26.2 MB/s | ❌ No (need LVDS) |

**Key Finding**: Streaming one range FFT per frame (20.5 KB/s) is well within UART limits. This is exactly what the Vital Signs demo does.

### Frame Timing Consideration

For UART streaming, the frame period must accommodate transfer time:

```
Frame period: 50ms (20 fps)
Active chirp time: ~10ms
Processing time: ~5ms
Available for UART: ~35ms

Data to transfer: 1024 bytes (256 bins × 4 bytes)
At 921600 baud: 1024 × 10 / 921600 = ~11ms

✅ Plenty of margin for UART transfer
```

---

## Development Environment

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Code Composer Studio | 8.3.x (recommended) | IDE and debugger |
| mmWave SDK | 3.5 or 3.6 LTS | Firmware source and libraries |
| ARM CGT | 16.9.6.LTS | ARM compiler (installed with SDK) |
| DSP CGT | 8.3.x | DSP compiler (installed with SDK) |
| XDCtools | 3.50.x | Build system (installed with SDK) |
| UniFlash | 6.x | Firmware flashing |

### Setup Instructions Outline

1. **Install Prerequisites**
   ```
   1. Download CCS 8.3 from TI
   2. Install mmWave SDK 3.5 or 3.6 LTS
      - Installer handles all toolchain dependencies
   3. Install UniFlash for device programming
   ```

2. **Verify Installation**
   ```bash
   # Check paths exist
   C:\ti\ccs83\
   C:\ti\mmwave_sdk_03_06_00_00\
   C:\ti\ti-cgt-arm_16.9.6.LTS\
   C:\ti\c6000_7.4.16\
   ```

3. **Import Demo Project**
   ```
   CCS: File → Import → CCS Projects
   Browse to: mmwave_sdk\packages\ti\demo\xwr68xx\mmw
   Import both MSS and DSS projects
   ```

4. **Build and Flash Workflow**
   ```
   1. Build MSS project → .xer4f binary
   2. Build DSS project → .xe674 binary
   3. Combine into meta-image
   4. Flash via UniFlash (SOP jumpers set for flash mode)
   5. Reset SOP jumpers for normal boot
   6. Test via CLI port
   ```

### Estimated Setup Time

| Task | Time |
|------|------|
| Download all tools | 1-2 hours |
| Install CCS + SDK | 1 hour |
| Configure and verify | 1-2 hours |
| Build first project | 1-2 hours |
| **Total** | **4-8 hours** |

---

## Implementation Sketch

### Option A: Use Vital Signs Demo (Recommended)

No firmware modification needed. Parse existing complex output:

```python
# Host-side parsing (Python)
def parse_vital_signs_complex_fft(tlv_data: bytes) -> np.ndarray:
    """Parse complex range FFT from Vital Signs demo TLV."""
    num_bins = len(tlv_data) // 4  # 4 bytes per complex bin

    complex_fft = np.zeros(num_bins, dtype=np.complex64)
    for i in range(num_bins):
        offset = i * 4
        real = struct.unpack('<h', tlv_data[offset:offset+2])[0]
        imag = struct.unpack('<h', tlv_data[offset+2:offset+4])[0]
        complex_fft[i] = complex(real, imag)

    return complex_fft

def extract_phase(complex_fft: np.ndarray, range_bin: int) -> float:
    """Extract phase at target range bin."""
    return np.angle(complex_fft[range_bin])
```

### Option B: Minimal SDK Modification

If custom TLV needed, add to `MmwDemo_transmitProcessedOutput()`:

```c
// In mss_main.c
#define MMWDEMO_OUTPUT_MSG_COMPLEX_1DFFT  0x500

void MmwDemo_transmitProcessedOutput(...)
{
    // ... existing TLV output code ...

    // Add complex 1D FFT output
    if (outputConfig & COMPLEX_1DFFT_ENABLED)
    {
        // Get pointer to radar cube in L3 memory
        cmplx16ReIm_t* radarCube = (cmplx16ReIm_t*)gMmwMssMCB.objDetObj.radarCubeAddr;

        // Output single chirp's range FFT (256 bins × 4 bytes)
        uint32_t numRangeBins = gMmwMssMCB.cfg.numRangeBins;
        uint32_t dataSize = numRangeBins * sizeof(cmplx16ReIm_t);

        // TLV header
        tl[tlvIdx].type = MMWDEMO_OUTPUT_MSG_COMPLEX_1DFFT;
        tl[tlvIdx].length = dataSize;
        UART_writePolling(uartHandle, (uint8_t*)&tl[tlvIdx], sizeof(MmwDemo_output_message_tl));

        // TLV payload
        UART_writePolling(uartHandle, (uint8_t*)radarCube, dataSize);

        tlvIdx++;
    }
}
```

### New TLV Format Specification

```
TLV Type: 0x500 (COMPLEX_1DFFT)
TLV Length: numRangeBins × 4 bytes

Payload format:
┌─────────┬─────────┬─────────┬─────────┬─────────────┐
│ Bin 0   │ Bin 1   │ Bin 2   │ ...     │ Bin N-1     │
│ Re│Im   │ Re│Im   │ Re│Im   │         │ Re│Im       │
│ 2B│2B   │ 2B│2B   │ 2B│2B   │         │ 2B│2B       │
└─────────┴─────────┴─────────┴─────────┴─────────────┘

Where:
- Re = int16_t (signed 16-bit real component)
- Im = int16_t (signed 16-bit imaginary component)
- Little-endian byte order
```

---

## Pros and Cons

### Custom Firmware Development

| Pros | Cons |
|------|------|
| Full control over data output | 1-4 weeks development time |
| Can optimize for specific use case | Steep SDK learning curve |
| No additional hardware cost | Maintenance burden for SDK updates |
| Deep understanding of radar DSP | Risk of introducing subtle bugs |
| Can add custom processing | May duplicate TI's existing work |
| Output exactly what you need | Firmware flashing complexity |

### Using Vital Signs Demo (Alternative)

| Pros | Cons |
|------|------|
| Already outputs complex data | Fixed output format |
| Minimal development effort | Less flexibility |
| TI-supported firmware | May include unneeded processing |
| Regular updates from TI | Still need to understand TLV format |
| Lower risk | Cannot modify internal algorithms |

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Bricking device | Low | Medium | Recovery via UniFlash, keep backup firmware |
| SDK version incompatibility | Medium | Medium | Pin to specific SDK version, test thoroughly |
| Breaking other functionality | Medium | Medium | Incremental changes, version control |
| UART timing issues | Low | Low | Conservative frame periods |
| Memory conflicts | Medium | High | Careful L3 memory management |

### Resource Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Time sink (scope creep) | High | High | Fixed timeboxes, clear requirements |
| SDK update breaks custom code | Medium | Medium | Document changes, maintain patches |
| Limited TI support for mods | High | Low | Self-reliance, community forums |
| Developer onboarding time | Medium | Medium | Document environment setup |

### Recovery Options

If device appears bricked:
1. Set SOP jumpers to flash mode (SOP0=1, SOP1=1, SOP2=0)
2. Use UniFlash to re-flash known-good firmware
3. Device has factory bootloader in ROM - recovery always possible

---

## Comparison with Alternatives

| Approach | I/Q Quality | Effort | Cost | Flexibility | Risk | Recommended? |
|----------|-------------|--------|------|-------------|------|--------------|
| **Vital Signs Demo** | Phase from complex FFT | Low (1-2 days) | $0 | Medium | Low | **YES** |
| Custom SDK Modification | Full 1D complex FFT | Medium (1-2 weeks) | $0 | High | Medium | Conditional |
| Full Custom Firmware | Configurable | High (2-4 weeks) | $0 | Highest | Medium-High | No |
| LVDS + DCA1000EVM | Raw ADC | Medium | ~$500 | Highest | Low | For research only |
| Different Hardware | Varies | Medium | $$$ | Varies | Low | Not needed |

---

## Alternative Recommendation

### When to Use Each Approach

**Use Vital Signs Demo When:**
- You need phase-based vital signs detection
- Development time is limited
- You want TI-supported firmware
- Your use case matches TI's vital signs lab

**Consider Custom SDK Modification When:**
- Vital Signs demo output format doesn't fit your pipeline
- You need specific data not in any TI demo
- You have SDK development experience
- You've exhausted demo-based options

**Use DCA1000EVM When:**
- You're doing research requiring raw ADC access
- You need to capture full radar cube for offline analysis
- Bandwidth requirements exceed UART capacity
- Cost is not a constraint

**Don't Bother With Custom Firmware When:**
- Vital Signs demo meets your needs
- You lack embedded development experience
- Time-to-market is critical
- The feature exists in a TI demo

### Final Recommendation for Ambient Project

1. **First**: Flash and test Vital Signs demo firmware
2. **Parse**: Implement TLV parser for complex Range-FFT output
3. **Evaluate**: Measure if phase extraction meets vital signs requirements
4. **Only Then**: Consider custom modification if specific gaps identified

The Vital Signs demo already provides exactly what's needed for chest displacement measurement via phase extraction. Custom firmware development is likely unnecessary.

---

## Links and References

### TI Official Documentation

- [mmWave SDK Download](https://www.ti.com/tool/MMWAVE-SDK)
- [mmWave SDK User Guide (PDF)](https://dr-download.ti.com/software-development/software-development-kit-sdk/MD-PIrUeCYr3X/03.06.00.00-LTS/mmwave_sdk_user_guide.pdf)
- [IWR6843 Product Page](https://www.ti.com/product/IWR6843)
- [Code Composer Studio Download](https://www.ti.com/tool/CCSTUDIO)
- [Introduction to DSP Subsystem in IWR6843 (SWRA621)](https://www.ti.com/lit/an/swra621/swra621.pdf)
- [DCA1000EVM User Guide](https://www.ti.com/tool/DCA1000EVM)

### TI E2E Forum Threads

- [Firmware modification to send 1D-FFT data over serial port](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/991012/iwr6843isk-ods-firmware-modification-pointers-to-send-a-part-of-1d-fft-data-over-to-the-serial-port)
- [Range profile value in mmWave demo](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1029571/iwr6843-what-is-the-value-range-profile)
- [Export raw data for vital sign lab](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/921635/iwr6843-how-to-export-the-raw-data-for-post-processing-in-vital-sign-lab)
- [Data format of sensor output for vital sign lab](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/923183/iwr6843-data-format-of-sensor-output-for-vital-sign-lab)
- [Setting up CCS build environment](https://e2e.ti.com/support/tools/code-composer-studio-group/ccs/f/code-composer-studio-forum/893020/ccs-iwr6843-setting-up-build-environment)
- [Maximum UART baud rate](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/738420/iwr1642-maximum-baud-rate)

### GitHub Projects

- [pymmw - Pythonic mmWave Toolbox](https://github.com/m6c7l/pymmw)
- [IWR6843 Read Data Python](https://github.com/kirkster96/IWR6843-Read-Data-Python-MMWAVE-SDK)
- [iwr6843aop_pub - ROS2 Driver](https://github.com/nhma20/iwr6843aop_pub)
- [mmwave_reader](https://github.com/GTEC-UDC/mmwave_reader)
- [OpenRadar Documentation](https://openradar.readthedocs.io/)

### Academic/Research

- [High precision vital signs detection using mmWave radar (Nature)](https://www.nature.com/articles/s41598-024-77683-1)
- [MathWorks mmWave Performance Guide](https://www.mathworks.com/help/radar/ug/performance-factors-mmWave.html)

---

## Appendix: Memory Map Reference

```
IWR6843 Memory Map (from TRM)

L3 Memory (Radar Cube):
  Base Address: 0x51000000
  Size: 768KB (0xC0000)
  Purpose: Store 1D FFT output (radar cube)

MSS TCMA (Program):
  Base Address: 0x00000000
  Size: 512KB

MSS TCMB (Data):
  Base Address: 0x08000000
  Size: 192KB

DSS L2:
  Base Address: 0x00800000
  Size: 256KB

HWA Local Memory:
  Base Address: 0x21000000
  Size: 32KB
```

---

*Document created: January 2026*
*Research status: Complete*
*Recommended action: Use Vital Signs Demo firmware*
