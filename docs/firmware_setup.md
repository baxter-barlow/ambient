# Firmware Setup Guide

This guide covers flashing the IWR6843AOPEVM with TI's Vital Signs demo firmware for accurate heart rate and respiratory rate detection.

## Overview

The **Vital Signs with People Tracking** demo firmware provides:
- True phase-based chest displacement measurement
- On-chip breathing and heart rate computation
- Confidence scores for detected vitals
- Pre-filtered waveforms for display

This replaces the Out-of-Box (OOB) demo which only outputs magnitude data.

## Prerequisites

- IWR6843AOPEVM board
- USB cable (micro-USB)
- Windows PC (UniFlash is Windows-only for mmWave devices)
- TI account (free registration)

## Step 1: Download TI Radar Toolbox

1. Go to https://www.ti.com/tool/RADAR-TOOLBOX
2. Click "Download" and sign in with your TI account
3. Download the latest version (e.g., `radar_toolbox_1_20_00_11`)
4. Extract to a known location (e.g., `C:\ti\radar_toolbox`)

## Step 2: Locate the Firmware Binary

Navigate to the vital signs demo:

```
radar_toolbox_1_20_00_11/
└── source/
    └── ti/
        └── examples/
            └── Medical/
                └── Vital_Signs_With_People_Tracking/
                    └── prebuilt_binaries/
                        └── iwr6843aopevm/
                            └── vital_signs_with_people_tracking_iwr6843aopevm.bin
```

If the `aopevm` variant is not present, check for `iwr6843aop` or `xwr68xx` variants.

## Step 3: Install UniFlash

1. Download UniFlash from https://www.ti.com/tool/UNIFLASH
2. Install with mmWave device support enabled
3. Launch UniFlash

## Step 4: Put Device in Flash Mode

The IWR6843AOPEVM has SOP (Sense on Power) jumpers that control boot mode:

1. **Disconnect USB** from the board
2. **Set SOP jumpers** for flashing mode:
   - SOP0: SHORT (jumper ON)
   - SOP1: SHORT (jumper ON)
   - SOP2: OPEN (jumper OFF)

   This configures SOP = 0b011 = Flash programming mode

3. **Connect USB** to the board
4. The device should enumerate as an XDS110 debug probe

## Step 5: Flash the Firmware

1. In UniFlash, click **"New Target Configuration"**
2. Select device: **IWR6843** (or IWR6843AOP if available)
3. Select connection: **XDS110 USB Debug Probe**
4. Click **"Start"**
5. In the Flash Image panel:
   - Click **"Browse"** and select the `.bin` file from Step 2
   - Set Load Address: `0x00000000` (or leave default)
6. Click **"Load Image"**
7. Wait for "Flash programming successful" message

## Step 6: Set Normal Boot Mode

After flashing:

1. **Disconnect USB**
2. **Set SOP jumpers** for normal operation:
   - SOP0: OPEN (jumper OFF)
   - SOP1: OPEN (jumper OFF)
   - SOP2: OPEN (jumper OFF)

   This configures SOP = 0b000 = Normal boot from flash

3. **Connect USB**
4. Two serial ports should appear (`/dev/ttyACM0` and `/dev/ttyACM1` on Linux)

## Step 6.1: Verify Boot Mode (Flash vs Run)

Use these quick checks to confirm the board is in the expected mode:

- **Flash mode (SOP = 0b011)**:
  - Board enumerates as **XDS110 debug probe**
  - CLI port typically **does not** respond to `version`
- **Run mode (SOP = 0b000)**:
  - Two serial ports appear (CLI + Data)
  - CLI responds to `version` and `chirp status`

If the CLI port responds but `chirp status` returns "Unknown command", the device is in run mode but likely running a non-chirp firmware build.

## Step 7: Verify Firmware

Connect to the CLI port and check the version:

```bash
# Using screen or minicom
screen /dev/ttyACM0 115200

# Or with Python
python -c "
import serial
s = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
s.write(b'version\n')
import time; time.sleep(0.3)
print(s.read(s.in_waiting or 200).decode())
s.close()
"
```

Expected output for vital signs firmware:
```
mmWave Demo Vital Signs
Platform: IWR6843AOP
Version: 3.x.x.x
```

If you see "Out Of Box Demo" or "mmWave Demo", you're still on OOB firmware.

## Using ambient with Vital Signs Firmware

Once flashed, ambient will automatically detect the vital signs TLV output:

```bash
# Start the backend - it will detect firmware type
make api

# In another terminal, start the dashboard
make dashboard
```

The dashboard will show:
- **Green "Firmware" badge** when using vital signs firmware
- **Yellow "Estimated" badge** when falling back to magnitude estimation

## Fallback: Staying on OOB Demo

If you prefer to stay on the Out-of-Box demo:

1. The magnitude-variation algorithm will be used (less accurate)
2. Heart rate detection will be unreliable
3. Respiratory rate detection will work for obvious breathing

To flash OOB demo instead:
```
radar_toolbox/source/ti/examples/Out_Of_Box_Demo/prebuilt_binaries/
```

## Troubleshooting

### "No device detected" in UniFlash
- Verify SOP jumpers are set for flash mode
- Try a different USB cable
- Check Device Manager (Windows) for XDS110

### Flash programming fails
- Ensure board is powered via USB (not just JTAG)
- Try clicking "Erase" before "Load Image"
- Reduce flash clock speed in UniFlash settings

### Serial ports not appearing after boot
- Verify SOP jumpers are set for normal mode
- Try power cycling the board
- Check `dmesg` on Linux for USB enumeration

### Firmware reports wrong version
- Ensure you flashed the correct binary for IWR6843AOPEVM
- The AOP variant requires AOP-specific binaries

### "Permission denied" on serial ports (Linux)
```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

## Configuration Files

The vital signs firmware uses different configuration parameters than OOB:

| Parameter | OOB Demo | Vital Signs Demo |
|-----------|----------|------------------|
| Frame rate | 30 FPS | 20 FPS |
| Range FFT | 256 | 256 |
| Doppler FFT | 64 | 256 |
| guiMonitor | standard | vital signs TLV enabled |

Use `configs/vital_signs.cfg` when running with vital signs firmware.

## References

- [TI Vital Signs Lab User Guide (TIDUEN3)](https://www.ti.com/lit/ug/tiduen3/tiduen3.pdf)
- [UniFlash User Guide](https://www.ti.com/lit/ug/spruin7e/spruin7e.pdf)
- [IWR6843AOPEVM User Guide](https://www.ti.com/lit/ug/swru546e/swru546e.pdf)
