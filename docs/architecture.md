# Architecture

## Pipeline

```
Sensor → Processing → Vitals → Storage
   ↓
 Frame    Range-FFT    Bandpass    HDF5
Parsing   Clutter RM   HR/RR Est   Parquet
```

## Modules

### sensor

Serial communication with IWR6843AOPEVM. Parses TLV frames (magic word + header + data). Two ports: CLI (config) and Data (frames).

### processing

- RangeFFT: ADC samples → range bins
- DopplerFFT: range data → velocity
- ClutterRemoval: MTI or moving average filter

### vitals

- BandpassFilter: isolate HR (0.8-3Hz) and RR (0.1-0.6Hz) bands
- HeartRateEstimator: FFT peak detection
- RespiratoryRateEstimator: FFT or peak counting

### storage

- HDF5Writer: raw frames + vitals (streaming, compressed)
- ParquetWriter: vitals only (pandas-friendly)
- DataReader: load either format

## Data Flow

```
USB Serial → FrameBuffer → RadarFrame
                              ↓
                       ProcessingPipeline
                              ↓
                         ProcessedFrame
                              ↓
                        VitalsExtractor
                              ↓
                          VitalSigns
```

## Frame Format

```
Magic (8B) | Header (32B) | TLV1 | TLV2 | ...

TLV: Type (4B) | Length (4B) | Data
```

TLV types: 1=detected points, 2=range profile, 5=range-Doppler
